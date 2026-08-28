from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

from app.schemas import FinancialFact
from app.validation import (
    FinancialValidationError,
    validate_same_accounting_basis,
    #validate_same_metric,
    validate_same_units,
    validate_values_present,
    validate_yoy_comparison,
    validate_same_period,
)


def operating_margin(
    operating_income: FinancialFact,
    revenue: FinancialFact,
) -> Decimal:
    """
    Operating margin = operating income / revenue * 100.
    """

    validate_values_present(
        operating_income,
        revenue,
    )

    validate_same_units(
        operating_income,
        revenue,
    )

    validate_same_accounting_basis(
        operating_income,
        revenue,
    )

    validate_same_period(
        operating_income,
        revenue,
    )

    if operating_income.metric_normalized != "operating_income":
        raise FinancialValidationError(
            "Expected operating income fact."
        )

    if revenue.metric_normalized != "total_revenue":
        raise FinancialValidationError(
            "Expected total revenue fact."
        )

    assert operating_income.reported_value is not None
    assert revenue.reported_value is not None

    if revenue.reported_value == 0:
        raise FinancialValidationError(
            "Operating margin is undefined because revenue is zero."
        )

    result = (
        operating_income.reported_value
        / revenue.reported_value
        * Decimal("100")
    )

    return result.quantize(
        TWO_DECIMALS,
        rounding=ROUND_HALF_UP,
    )

TWO_DECIMALS = Decimal("0.01")


def percentage_change(
    current: FinancialFact,
    prior: FinancialFact,
) -> Decimal:
    """
    Calculate year-over-year percentage change.

    Formula:
        ((current - prior) / prior) * 100

    Validation happens before arithmetic.
    """

    validate_yoy_comparison(current, prior)

    assert current.reported_value is not None
    assert prior.reported_value is not None

    if prior.reported_value == 0:
        raise FinancialValidationError(
            "Percentage change is undefined because "
            "the prior-period value is zero."
        )

    result = (
        (current.reported_value - prior.reported_value)
        / prior.reported_value
        * Decimal("100")
    )

    return result.quantize(
        TWO_DECIMALS,
        rounding=ROUND_HALF_UP,
    )


def absolute_change(
    current: FinancialFact,
    prior: FinancialFact,
) -> Decimal:
    """
    Calculate absolute change between comparable periods.
    """

    validate_yoy_comparison(current, prior)

    assert current.reported_value is not None
    assert prior.reported_value is not None

    return current.reported_value - prior.reported_value