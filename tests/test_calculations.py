from decimal import Decimal

from app.calculations import (
    absolute_change,
    percentage_change,
    operating_margin,
)
from app.quarterly_extraction import (
    extract_quarterly_statement_facts,
)
from app.schemas import PeriodType
import pytest

from app.validation import FinancialValidationError


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


def test_q1_2026_revenue_yoy_growth():
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

    result = percentage_change(
        current,
        prior,
    )

    assert result == Decimal("15.78")

def test_q1_2026_operating_margin():
    facts = extract_quarterly_statement_facts(
        "data/sample_filings/tesla_2026_q1_10q.pdf"
    )

    operating_income = get_fact(
        facts,
        "operating_income",
        2026,
        PeriodType.QUARTERLY,
        quarter=1,
    )

    revenue = get_fact(
        facts,
        "total_revenue",
        2026,
        PeriodType.QUARTERLY,
        quarter=1,
    )

    from app.calculations import operating_margin

    result = operating_margin(
        operating_income,
        revenue,
    )

    assert result == Decimal("4.20")
def test_q1_2026_revenue_absolute_change():
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

    result = absolute_change(
        current,
        prior,
    )

    assert result == Decimal("3052")


def test_operating_margin_rejects_mixed_periods():
    facts = extract_quarterly_statement_facts(
        "data/sample_filings/tesla_2026_q2_10q.pdf"
    )

    quarterly_operating_income = get_fact(
        facts,
        "operating_income",
        2026,
        PeriodType.QUARTERLY,
        quarter=2,
    )

    ytd_revenue = get_fact(
        facts,
        "total_revenue",
        2026,
        PeriodType.YEAR_TO_DATE,
    )

    with pytest.raises(
        FinancialValidationError
    ):
        operating_margin(
            quarterly_operating_income,
            ytd_revenue,
        )

def test_q2_2026_revenue_yoy_growth():
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

    result = percentage_change(
        current,
        prior,
    )

    assert result == Decimal("25.52")