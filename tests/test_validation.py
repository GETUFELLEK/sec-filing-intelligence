import pytest

from app.quarterly_extraction import (
    extract_quarterly_statement_facts,
)
from app.schemas import PeriodType
from app.validation import (
    FinancialValidationError,
    validate_yoy_comparison,
)


def get_fact(
    facts,
    metric,
    year,
    period_type,
    quarter=None,
):
    return next(
        fact
        for fact in facts
        if fact.metric_normalized == metric
        and fact.fiscal_year == year
        and fact.period_type == period_type
        and (
            quarter is None
            or fact.fiscal_quarter == quarter
        )
    )


def test_q1_yoy_is_valid():
    facts = extract_quarterly_statement_facts(
        "data/sample_filings/tesla_2026_q1_10q.pdf"
    )

    current = get_fact(
        facts,
        "total_revenue",
        2026,
        PeriodType.QUARTERLY,
        quarter=1,
    )

    prior = get_fact(
        facts,
        "total_revenue",
        2025,
        PeriodType.QUARTERLY,
        quarter=1,
    )

    # Should not raise.
    validate_yoy_comparison(current, prior)


def test_q2_yoy_is_valid():
    facts = extract_quarterly_statement_facts(
        "data/sample_filings/tesla_2026_q2_10q.pdf"
    )

    current = get_fact(
        facts,
        "total_revenue",
        2026,
        PeriodType.QUARTERLY,
        quarter=2,
    )

    prior = get_fact(
        facts,
        "total_revenue",
        2025,
        PeriodType.QUARTERLY,
        quarter=2,
    )

    validate_yoy_comparison(current, prior)


def test_q2_vs_ytd_is_rejected():
    facts = extract_quarterly_statement_facts(
        "data/sample_filings/tesla_2026_q2_10q.pdf"
    )

    quarterly = get_fact(
        facts,
        "total_revenue",
        2026,
        PeriodType.QUARTERLY,
        quarter=2,
    )

    ytd = get_fact(
        facts,
        "total_revenue",
        2025,
        PeriodType.YEAR_TO_DATE,
    )

    with pytest.raises(
        FinancialValidationError
    ):
        validate_yoy_comparison(
            quarterly,
            ytd,
        )


def test_different_metrics_are_rejected():
    facts = extract_quarterly_statement_facts(
        "data/sample_filings/tesla_2026_q1_10q.pdf"
    )

    revenue = get_fact(
        facts,
        "total_revenue",
        2026,
        PeriodType.QUARTERLY,
        quarter=1,
    )

    net_income = get_fact(
        facts,
        "net_income",
        2025,
        PeriodType.QUARTERLY,
        quarter=1,
    )

    with pytest.raises(
        FinancialValidationError
    ):
        validate_yoy_comparison(
            revenue,
            net_income,
        )