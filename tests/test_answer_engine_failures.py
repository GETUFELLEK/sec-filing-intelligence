from app.answer_engine import execute_query
from app.fact_store import load_sample_fact_store
from app.answer_engine import answer_question
from app.llm_query_parser import QueryClarificationRequired
from app.schemas import (
    AnswerStatus,
    ComparisonType,
    FinancialQuery,
    MetricName,
    PeriodType,
    QueryOperation,
    QuestionType,
)
def test_llm_clarification_becomes_ambiguous(
    monkeypatch,
):
    def fake_parse_query(question: str):
        raise QueryClarificationRequired(
            "'Profit' could mean gross profit, "
            "operating income, or net income."
        )

    monkeypatch.setattr(
        "app.answer_engine.parse_query",
        fake_parse_query,
    )

    answer = answer_question(
        "What was Tesla's profit in 2025?"
    )

    assert answer.status == AnswerStatus.AMBIGUOUS
    assert answer.result_value is None

def test_underspecified_quarterly_revenue_is_ambiguous():
    store = load_sample_fact_store()

    query = FinancialQuery(
        original_question=(
            "What was Tesla's quarterly revenue in 2026?"
        ),
        company="Tesla, Inc.",
        question_type=QuestionType.NUMERIC,
        metric=MetricName.TOTAL_REVENUE,
        operation=QueryOperation.LOOKUP,
        fiscal_year=2026,
        prior_year=None,
        fiscal_quarter=None,
        period_type=PeriodType.QUARTERLY,
        duration_months=3,
        comparison=ComparisonType.NONE,
    )

    answer = execute_query(
        query,
        store,
    )

    assert answer.status == AnswerStatus.AMBIGUOUS
    assert answer.result_value is None
    assert answer.evidence == []
def test_missing_q4_2026_returns_not_found():
    store = load_sample_fact_store()

    query = FinancialQuery(
        original_question=(
            "What was Tesla's Q4 2026 revenue?"
        ),
        company="Tesla, Inc.",
        question_type=QuestionType.NUMERIC,
        metric=MetricName.TOTAL_REVENUE,
        operation=QueryOperation.LOOKUP,
        fiscal_year=2026,
        prior_year=None,
        fiscal_quarter=4,
        period_type=PeriodType.QUARTERLY,
        duration_months=3,
        comparison=ComparisonType.NONE,
    )

    answer = execute_query(
        query,
        store,
    )

    assert answer.status == AnswerStatus.NOT_FOUND
    assert answer.result_value is None    
def test_narrative_query_not_yet_supported():
    store = load_sample_fact_store()

    query = FinancialQuery(
        original_question=(
            "What did management say about margin pressure?"
        ),
        company="Tesla, Inc.",
        question_type=QuestionType.NARRATIVE,
        metric=None,
        operation=None,
        fiscal_year=None,
        prior_year=None,
        fiscal_quarter=None,
        period_type=None,
        duration_months=None,
        comparison=ComparisonType.NONE,
        narrative_topic="margin pressure",
    )

    answer = execute_query(
        query,
        store,
    )

    assert answer.status == AnswerStatus.UNSUPPORTED