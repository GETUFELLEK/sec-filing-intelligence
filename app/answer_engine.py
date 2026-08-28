from __future__ import annotations

from decimal import Decimal
from typing import NoReturn

from app.calculations import (
    absolute_change,
    operating_margin,
    percentage_change,
)
from app.fact_store import (
    AmbiguousFactError,
    FactNotFoundError,
    FactStore,
    load_sample_fact_store,
)
from app.llm_query_parser import (
    QueryClarificationRequired,
    UnsupportedQueryError,
    parse_query,
)
from app.schemas import (
    AnswerStatus,
    FactQuery,
    FinancialFact,
    FinancialQuery,
    MetricName,
    NumericAnswer,
    QueryOperation,
    QuestionType,
    SourceEvidence,
)
from app.validation import FinancialValidationError


def display_value(value) -> str:
    return getattr(value, "value", str(value))

def failure_answer(
    question: str,
    status: AnswerStatus,
    message: str,
) -> NumericAnswer:
    """
    Build a controlled response when the system cannot
    safely answer a question.
    """

    return NumericAnswer(
        status=status,
        question=question,
        answer_text=message,
        result_value=None,
        result_unit=None,
        calculation=None,
        evidence=[],
    )
def execute_query(
    query: FinancialQuery,
    store: FactStore,
) -> NumericAnswer:
    """
    Execute an already validated FinancialQuery.

    This function contains no LLM calls.
    """

    try:
        if query.question_type == QuestionType.NARRATIVE:
            return failure_answer(
                query.original_question,
                AnswerStatus.UNSUPPORTED,
                (
                    "Narrative retrieval is not implemented "
                    "in the current prototype yet."
                ),
            )

        return answer_numeric_query(
            store,
            query,
        )

    except AmbiguousFactError as exc:
        return failure_answer(
            query.original_question,
            AnswerStatus.AMBIGUOUS,
            (
                "I found multiple financial facts that could "
                f"answer this question. {exc}"
            ),
        )

    except FactNotFoundError as exc:
        return failure_answer(
            query.original_question,
            AnswerStatus.NOT_FOUND,
            (
                "I could not find a matching financial fact "
                f"in the current filing corpus. {exc}"
            ),
        )

    except FinancialValidationError as exc:
        return failure_answer(
            query.original_question,
            AnswerStatus.VALIDATION_FAILED,
            (
                "I found relevant data, but it could not be "
                f"safely used for this calculation. {exc}"
            ),
        )

    except UnsupportedQueryError as exc:
        return failure_answer(
            query.original_question,
            AnswerStatus.UNSUPPORTED,
            str(exc),
        )   
def fact_to_evidence(
    fact: FinancialFact,
) -> SourceEvidence:
    """
    Convert an internal FinancialFact into user-visible
    provenance information.
    """

    return SourceEvidence(
        source_file=fact.source_file,
        page_number=fact.page_number,
        statement_name=fact.statement_name,
        row_label=fact.row_label,
        column_label=fact.column_label,
        value_raw=fact.value_raw,
        scale=fact.scale,
        currency=fact.currency,
    )


def build_fact_query(
    query: FinancialQuery,
    *,
    metric: MetricName,
    year: int,
) -> FactQuery:
    """
    Translate validated user intent into an exact deterministic
    fact-store lookup.
    """

    return FactQuery(
        company=query.company,
        metric_normalized=metric.value,
        fiscal_year=year,
        fiscal_quarter=query.fiscal_quarter,
        period_type=query.period_type,
        duration_months=query.duration_months,
    )


def retrieve_fact(
    store: FactStore,
    query: FinancialQuery,
    *,
    metric: MetricName,
    year: int,
) -> FinancialFact:
    return store.get_one(
        build_fact_query(
            query,
            metric=metric,
            year=year,
        )
    )
def answer_lookup(
    store: FactStore,
    query: FinancialQuery,
) -> NumericAnswer:
    if query.metric is None:
        raise FinancialValidationError(
            "Lookup requires a metric."
        )

    if query.fiscal_year is None:
        raise FinancialValidationError(
            "Lookup requires a fiscal year."
        )

    fact = retrieve_fact(
        store,
        query,
        metric=query.metric,
        year=query.fiscal_year,
    )

    value = fact.reported_value

    if value is None:
        raise FinancialValidationError(
            "The requested fact has no reported numeric value."
        )

    answer_text = (
        f"{fact.company} reported "
        f"{fact.metric_raw} of "
        f"{fact.value_raw} {display_value(fact.scale)} "
        f"{fact.currency} for "
        f"{fact.column_label}."
    )

    return NumericAnswer(
        status=AnswerStatus.ANSWERED,
        question=query.original_question,
        answer_text=answer_text,
        result_value=value,
        result_unit=(
           f"{display_value(fact.currency)} "
           f"{display_value(fact.scale)}"
        ),
        evidence=[
            fact_to_evidence(fact)
        ],
    )
def answer_percentage_change(
    store: FactStore,
    query: FinancialQuery,
) -> NumericAnswer:
    if query.metric is None:
        raise FinancialValidationError(
            "Percentage change requires a metric."
        )

    if (
        query.fiscal_year is None
        or query.prior_year is None
    ):
        raise FinancialValidationError(
            "Percentage change requires "
            "current and prior years."
        )

    current = retrieve_fact(
        store,
        query,
        metric=query.metric,
        year=query.fiscal_year,
    )

    prior = retrieve_fact(
        store,
        query,
        metric=query.metric,
        year=query.prior_year,
    )

    result = percentage_change(
        current,
        prior,
    )

    direction = (
        "increased"
        if result > 0
        else "decreased"
        if result < 0
        else "was unchanged"
    )

    calculation = (
        f"(({current.value_raw} - "
        f"{prior.value_raw}) / "
        f"{prior.value_raw}) × 100 "
        f"= {result}%"
    )

    answer_text = (
    f"{current.metric_raw} {direction} "
    f"{abs(result)}% from "
    f"{prior.value_raw} {display_value(prior.scale)} "
    f"{display_value(prior.currency)} in "
    f"{prior.column_label} to "
    f"{current.value_raw} {display_value(current.scale)} "
    f"{display_value(current.currency)} in "
    f"{current.column_label}."
)

    return NumericAnswer(
        status=AnswerStatus.ANSWERED,
        question=query.original_question,
        answer_text=answer_text,
        result_value=result,
        result_unit="percent",
        calculation=calculation,
        evidence=[
            fact_to_evidence(current),
            fact_to_evidence(prior),
        ],
 
   )


def answer_absolute_change(
    store: FactStore,
    query: FinancialQuery,
) -> NumericAnswer:
    if query.metric is None:
        raise FinancialValidationError(
            "Absolute change requires a metric."
        )

    if (
        query.fiscal_year is None
        or query.prior_year is None
    ):
        raise FinancialValidationError(
            "Absolute change requires "
            "current and prior years."
        )

    current = retrieve_fact(
        store,
        query,
        metric=query.metric,
        year=query.fiscal_year,
    )

    prior = retrieve_fact(
        store,
        query,
        metric=query.metric,
        year=query.prior_year,
    )

    result = absolute_change(
        current,
        prior,
    )

    calculation = (
        f"{current.value_raw} - "
        f"{prior.value_raw} = "
        f"{result}"
    )

    answer_text = (
        f"{current.metric_raw} changed by "
        f"{result} {display_value(current.scale)} "
        f"{display_value(current.currency)}, from "
        f"{prior.value_raw} to "
        f"{current.value_raw}."
    )

    return NumericAnswer(
        status=AnswerStatus.ANSWERED,
        question=query.original_question,
        answer_text=answer_text,
        result_value=result,
        result_unit=(
            f" {display_value(current.scale)} "
            f"{display_value(current.currency)}"
        ),
        calculation=calculation,
        evidence=[
            fact_to_evidence(current),
            fact_to_evidence(prior),
        ],
    )
def answer_operating_margin(
    store: FactStore,
    query: FinancialQuery,
) -> NumericAnswer:
    if query.fiscal_year is None:
        raise FinancialValidationError(
            "Operating margin requires a fiscal year."
        )

    operating_income_fact = retrieve_fact(
        store,
        query,
        metric=MetricName.OPERATING_INCOME,
        year=query.fiscal_year,
    )

    revenue_fact = retrieve_fact(
        store,
        query,
        metric=MetricName.TOTAL_REVENUE,
        year=query.fiscal_year,
    )

    result = operating_margin(
        operating_income_fact,
        revenue_fact,
    )

    calculation = (
        f"({operating_income_fact.value_raw} / "
        f"{revenue_fact.value_raw}) × 100 "
        f"= {result}%"
    )

    answer_text = (
        # f"{operating_income_fact.company}'s "
        f"{operating_income_fact.company}'s "
        f"operating margin for "
        f"{operating_income_fact.column_label} "
        f"was {result}%, based on operating income of "
        f"{operating_income_fact.value_raw} "
        f"{display_value(operating_income_fact.scale)} "
        f"{display_value(operating_income_fact.currency)} "
        f"and total revenue of "
        f"{revenue_fact.value_raw} "
        f"{display_value(revenue_fact.scale)} "
        f"{display_value(revenue_fact.currency)}."

        # f"{revenue_fact.currency}."
    )

    return NumericAnswer(
        status=AnswerStatus.ANSWERED,
        question=query.original_question,
        answer_text=answer_text,
        result_value=result,
        result_unit="percent",
        calculation=calculation,
        evidence=[
            fact_to_evidence(
                operating_income_fact
            ),
            fact_to_evidence(
                revenue_fact
            ),
        ],
    )
def answer_numeric_query(
    store: FactStore,
    query: FinancialQuery,
) -> NumericAnswer:
    if query.question_type != QuestionType.NUMERIC:
        raise UnsupportedQueryError(
            "Numeric answer engine received "
            "a non-numeric query."
        )

    if query.operation == QueryOperation.LOOKUP:
        return answer_lookup(
            store,
            query,
        )

    if (
        query.operation
        == QueryOperation.PERCENTAGE_CHANGE
    ):
        return answer_percentage_change(
            store,
            query,
        )

    if (
        query.operation
        == QueryOperation.ABSOLUTE_CHANGE
    ):
        return answer_absolute_change(
            store,
            query,
        )

    if (
        query.operation
        == QueryOperation.OPERATING_MARGIN
    ):
        return answer_operating_margin(
            store,
            query,
        )

    raise UnsupportedQueryError(
        f"Unsupported operation: "
        f"{query.operation}"
    )
def answer_question(
    question: str,
    *,
    store: FactStore | None = None,
) -> NumericAnswer:
    """
    End-to-end question answering.
    """

    if store is None:
        store = load_sample_fact_store()

    try:
        query = parse_query(question)

    except QueryClarificationRequired as exc:
        return failure_answer(
            question,
            AnswerStatus.AMBIGUOUS,
            f"I need clarification before I can answer safely. {exc}",
        )

    except UnsupportedQueryError as exc:
        return failure_answer(
            question,
            AnswerStatus.UNSUPPORTED,
            str(exc),
        )

    return execute_query(
        query,
        store,
    )
if __name__ == "__main__":
    questions = [
        (
            "What was Tesla's Q1 2026 "
            "revenue growth year over year?"
        ),
        (
            "What was Tesla's net income "
            "in 2025?"
        ),
        (
            "What was Tesla's Q2 2026 "
            "operating margin?"
        ),
    ]

    store = load_sample_fact_store()

    for question in questions:
        print("\n" + "=" * 80)
        print("QUESTION")
        print(question)

        try:
            answer = answer_question(
                question,
                store=store,
            )

            print("\nANSWER")
            print(
                answer.model_dump_json(
                    indent=2
                )
            )

        except Exception as exc:
            print(
                f"\nERROR: {exc}"
            )                            