from decimal import Decimal

import pytest

from app.fact_store import (
    AmbiguousFactError,
    FactNotFoundError,
    load_sample_fact_store,
)
from app.schemas import FactQuery, PeriodType


def test_retrieve_q2_2026_revenue():
    store = load_sample_fact_store()

    fact = store.get_one(
        FactQuery(
            metric_normalized="total_revenue",
            fiscal_year=2026,
            fiscal_quarter=2,
            period_type=PeriodType.QUARTERLY,
            duration_months=3,
        )
    )

    assert (
        fact.reported_value
        == Decimal("28236")
    )


def test_retrieve_q2_2026_ytd_revenue():
    store = load_sample_fact_store()

    fact = store.get_one(
        FactQuery(
            metric_normalized="total_revenue",
            fiscal_year=2026,
            period_type=PeriodType.YEAR_TO_DATE,
            duration_months=6,
        )
    )

    assert (
        fact.reported_value
        == Decimal("50623")
    )


def test_underspecified_2026_revenue_is_ambiguous():
    store = load_sample_fact_store()

    with pytest.raises(AmbiguousFactError):
        store.get_one(
            FactQuery(
                metric_normalized="total_revenue",
                fiscal_year=2026,
            )
        )


def test_unknown_year_is_not_found():
    store = load_sample_fact_store()

    with pytest.raises(FactNotFoundError):
        store.get_one(
            FactQuery(
                metric_normalized="total_revenue",
                fiscal_year=1999,
            )
        )