from app.llm_query_parser import (
    QueryClarificationRequired,
    resolve_intent,
)
from app.schemas import (
    ComparisonType,
    LLMIntent,
    MetricName,
    PeriodType,
    QueryOperation,
    QuestionType,
)


def test_resolve_q1_yoy_derives_prior_year():
    intent = LLMIntent(
        company="Tesla",
        question_type=QuestionType.NUMERIC,
        metric=MetricName.TOTAL_REVENUE,
        operation=QueryOperation.PERCENTAGE_CHANGE,
        fiscal_year=2026,
        prior_year=None,
        fiscal_quarter=1,
        period_type=PeriodType.QUARTERLY,
        duration_months=3,
        comparison=ComparisonType.YEAR_OVER_YEAR,
    )

    query = resolve_intent(
        "What was Tesla's Q1 2026 "
        "revenue growth year over year?",
        intent,
    )

    assert query.fiscal_year == 2026
    assert query.prior_year == 2025
    assert query.fiscal_quarter == 1
    assert query.duration_months == 3


def test_ambiguous_intent_is_rejected():
    intent = LLMIntent(
        company="Tesla",
        question_type=QuestionType.NUMERIC,
        metric=None,
        operation=QueryOperation.LOOKUP,
        fiscal_year=2025,
        needs_clarification=True,
        clarification_reason=(
            "'Profit' could mean net income, "
            "gross profit, or operating income."
        ),
    )

    try:
        resolve_intent(
            "What was Tesla's profit in 2025?",
            intent,
        )

        assert False

    except QueryClarificationRequired:
        assert True