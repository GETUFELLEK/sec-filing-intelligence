from __future__ import annotations

import os

from openai import OpenAI

from app.schemas import (
    ComparisonType,
    FinancialQuery,
    LLMIntent,
    MetricName,
    PeriodType,
    QueryOperation,
    QuestionType,
)


SYSTEM_PROMPT = """
You are the intent-parsing component of an SEC filing
intelligence system.

Your ONLY job is to translate a user's natural-language
question into structured intent.

You must NOT:
- answer the financial question,
- provide financial values,
- perform arithmetic,
- estimate missing numbers,
- retrieve facts,
- invent periods,
- invent metrics.

The downstream system will retrieve and validate all financial
facts deterministically.

SUPPORTED COMPANY FOR THIS PROTOTYPE:
- Tesla, Inc.

SUPPORTED NUMERIC METRICS:
- total_revenue
- net_income
- gross_profit
- operating_income

SUPPORTED NUMERIC OPERATIONS:
- lookup
- percentage_change
- absolute_change
- operating_margin

RULES:

1. "Revenue", "total revenue", "revenues", and "top line"
   normally map to total_revenue when the user clearly refers
   to company-wide revenue.

2. Do NOT treat every occurrence of "sales" as total_revenue.
   If the question is ambiguous between total company revenue
   and a specific sales category, request clarification.

3. "Net income" maps to net_income.

4. "Gross profit" maps to gross_profit.

5. "Operating income" or "income from operations"
   maps to operating_income.

6. "Profit" by itself can be ambiguous. If you cannot tell
   whether the user means net income, gross profit, or operating
   income, set needs_clarification=true.

7. For "operating margin":
   operation = operating_margin
   metric = operating_income

   The downstream application will retrieve total revenue and
   calculate the margin. Do not calculate it yourself.

8. Q1, Q2, Q3, Q4 map to fiscal_quarter 1, 2, 3, 4.

9. If a quarter is explicitly given:
   period_type = quarterly
   duration_months = 3.

10. "Year over year", "year-over-year", and "YoY"
    map to comparison = year_over_year.

11. If only the current year is stated in a YoY question,
    DO NOT invent the previous year.
    Leave prior_year null.
    Deterministic application code will derive it.

12. If two explicit years are given, preserve both:
    fiscal_year = later/current year
    prior_year = earlier year.

13. A question asking for a value "in 2025" without a quarter,
    month, or YTD qualifier should be interpreted as annual
    for this SEC-filing prototype:
    period_type = annual
    duration_months = 12.

14. "Six months", "first six months", or "first half"
    means:
    period_type = year_to_date
    duration_months = 6.

15. Narrative questions such as:
    - what management said about margins,
    - risk factors,
    - management commentary,
    should use:
    question_type = narrative
    narrative_topic = concise description of the topic.

16. If the question cannot safely be mapped to one supported
    interpretation:
    needs_clarification = true
    clarification_reason = a concise explanation.

17. If the question is unrelated to the SEC filing corpus,
    financial results, business performance, risks, management
    commentary, or filing content, set:

    question_type = "unsupported"

    Do not treat general-knowledge questions as narrative questions.

    Examples of unsupported questions:
    - What is the day today?
    - What is the weather?
    - Who is the president?
    - Write Python code for me.  
DOMAIN CLASSIFICATION RULES:

A question is NUMERIC if it asks about a supported financial metric,
period, comparison, or calculation from the SEC filings.

Supported numeric concepts include:
- revenue
- total revenue
- revenues
- net income
- gross profit
- operating income
- operating margin
- quarter or fiscal-year results
- year-over-year growth
- absolute or percentage change

IMPORTANT:
Questions about these supported financial concepts MUST NOT be
classified as unsupported.

Examples:

"What was Tesla's Q1 2026 total revenue?"
→ question_type = "numeric"
→ metric = "total_revenue"
→ operation = "lookup"
→ fiscal_year = 2026
→ fiscal_quarter = 1
→ period_type = "quarterly"

"What was Tesla's net income in 2025?"
→ question_type = "numeric"

"What was Tesla's Q2 2026 operating margin?"
→ question_type = "numeric"

"What did management say about margin pressure?"
→ question_type = "narrative"

Use question_type = "unsupported" ONLY when the question is unrelated
to the available SEC filing domain.

Examples:
"What is the day today?"
"What is the weather?"
"Who is the president?"
"Write a Python sorting algorithm."
→ question_type = "unsupported"      

Accuracy and abstention are more important than guessing.
"""


class QueryClarificationRequired(ValueError):
    """Raised when the user's intent is genuinely ambiguous."""


class UnsupportedQueryError(ValueError):
    """Raised when the query is outside the MVP's supported scope."""


def call_llm_for_intent(
    question: str,
) -> LLMIntent:
    """
    Ask the LLM to perform semantic interpretation only.

    The response must conform to LLMIntent.
    """

    model = os.getenv("OPENAI_MODEL","gpt-5.6-luna")



    client = OpenAI()

    response = client.responses.parse(
        model=model,
        input=[
            {
                "role": "system",
                "content": SYSTEM_PROMPT,
            },
            {
                "role": "user",
                "content": question,
            },
        ],
        text_format=LLMIntent,
    )

    intent = response.output_parsed

    if intent is None:
        raise RuntimeError(
            "The model did not return a structured intent."
        )

    return intent
def resolve_intent(
    question: str,
    intent: LLMIntent,
) -> FinancialQuery:
    """
    Convert LLM interpretation into a trusted application query.

    This layer applies deterministic business rules and does not
    blindly trust the LLM output.
    """

    # ---------------------------------------------------------
    # Global guardrails
    # ---------------------------------------------------------

    # Out-of-domain questions should never reach retrieval.
    if intent.question_type == QuestionType.UNSUPPORTED:
        raise UnsupportedQueryError(
            "This question is outside the scope of the "
            "SEC Filing Intelligence prototype."
        )

    # In-domain but ambiguous questions require clarification.
    if intent.needs_clarification:
        raise QueryClarificationRequired(
            intent.clarification_reason
            or "The question is ambiguous."
        )

    # MVP company guardrail.
    if intent.company is None:
        company = "Tesla, Inc."

    elif intent.company.lower() in {
        "tesla",
        "tesla inc",
        "tesla, inc.",
        "tesla inc.",
    }:
        company = "Tesla, Inc."

    else:
        raise UnsupportedQueryError(
            f"Unsupported company: {intent.company}. "
            "The current prototype supports Tesla only."
        )

    fiscal_year = intent.fiscal_year
    prior_year = intent.prior_year

    period_type = intent.period_type
    duration_months = intent.duration_months

    # ---------------------------------------------------------
    # Numeric intent validation
    # ---------------------------------------------------------

    if intent.question_type == QuestionType.NUMERIC:

        if intent.metric is None:
            raise QueryClarificationRequired(
                "A numeric question requires a supported metric."
            )

        if intent.operation is None:
            raise QueryClarificationRequired(
                "A numeric question requires an operation."
            )

        if fiscal_year is None:
            raise QueryClarificationRequired(
                "A numeric question requires a fiscal year."
            )

        # Quarter semantics are deterministic.
        if intent.fiscal_quarter is not None:
            period_type = PeriodType.QUARTERLY
            duration_months = 3

        # Annual facts always represent 12 months.
        if period_type == PeriodType.ANNUAL:
            duration_months = 12

        # YoY prior year is derived deterministically.
        if (
            intent.comparison == ComparisonType.YEAR_OVER_YEAR
            and prior_year is None
        ):
            prior_year = fiscal_year - 1

        # Growth operations require a comparison period.
        if intent.operation in {
            QueryOperation.PERCENTAGE_CHANGE,
            QueryOperation.ABSOLUTE_CHANGE,
        }:
            if prior_year is None:
                raise QueryClarificationRequired(
                    "A comparison requires a prior period."
                )

    # ---------------------------------------------------------
    # Narrative intent validation
    # ---------------------------------------------------------

    elif intent.question_type == QuestionType.NARRATIVE:

        if not intent.narrative_topic:
            raise QueryClarificationRequired(
                "A narrative question requires a topic."
            )

    # ---------------------------------------------------------
    # Trusted application query
    # ---------------------------------------------------------

    return FinancialQuery(
        original_question=question,
        company=company,
        question_type=intent.question_type,
        metric=intent.metric,
        operation=intent.operation,
        fiscal_year=fiscal_year,
        prior_year=prior_year,
        fiscal_quarter=intent.fiscal_quarter,
        period_type=period_type,
        duration_months=duration_months,
        comparison=intent.comparison,
        narrative_topic=intent.narrative_topic,
    )
def parse_query(
    question: str,
) -> FinancialQuery:
    """
    Public entry point.

    Natural language
        -> LLM structured interpretation
        -> deterministic validation/resolution
        -> FinancialQuery
    """

    question = question.strip()

    if not question:
        raise ValueError(
            "Question cannot be empty."
        )

    intent = call_llm_for_intent(question)

    return resolve_intent(
        question,
        intent,
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
        (
            "What did management say "
            "about margin pressure?"
        ),
    ]

    for question in questions:
        print("\n" + "=" * 80)
        print("QUESTION:")
        print(question)

        try:
            query = parse_query(question)

            print("\nSTRUCTURED QUERY:")
            print(
                query.model_dump_json(
                    indent=2
                )
            )

        except Exception as exc:
            print(
                f"\nERROR: {exc}"
            )        