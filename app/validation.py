from __future__ import annotations

from datetime import date

from app.schemas import FinancialFact, PeriodType


class FinancialValidationError(ValueError):
    """
    Raised when two financial facts cannot be safely compared.
    """


def validate_values_present(
    left: FinancialFact,
    right: FinancialFact,
) -> None:
    if left.reported_value is None:
        raise FinancialValidationError(
            "Left financial fact has no numeric value."
        )

    if right.reported_value is None:
        raise FinancialValidationError(
            "Right financial fact has no numeric value."
        )


def validate_same_metric(
    left: FinancialFact,
    right: FinancialFact,
) -> None:
    if left.metric_normalized != right.metric_normalized:
        raise FinancialValidationError(
            "Cannot compare different financial metrics: "
            f"{left.metric_normalized!r} vs "
            f"{right.metric_normalized!r}."
        )


def validate_same_units(
    left: FinancialFact,
    right: FinancialFact,
) -> None:
    if left.currency != right.currency:
        raise FinancialValidationError(
            "Cannot compare facts with different currencies: "
            f"{left.currency!r} vs {right.currency!r}."
        )

    if left.scale != right.scale:
        raise FinancialValidationError(
            "Cannot compare facts with different scales: "
            f"{left.scale!r} vs {right.scale!r}."
        )


def validate_same_accounting_basis(
    left: FinancialFact,
    right: FinancialFact,
) -> None:
    if left.accounting_basis != right.accounting_basis:
        raise FinancialValidationError(
            "Cannot directly compare different accounting bases: "
            f"{left.accounting_basis.value!r} vs "
            f"{right.accounting_basis.value!r}."
        )


def _month_day(period_end_date: str | None) -> tuple[int, int] | None:
    if period_end_date is None:
        return None

    parsed = date.fromisoformat(period_end_date)

    return parsed.month, parsed.day


def validate_periods_for_yoy(
    current: FinancialFact,
    prior: FinancialFact,
) -> None:
    """
    Validate that two facts represent comparable year-over-year periods.

    Examples:

        FY2025 vs FY2024        -> valid
        Q1 2026 vs Q1 2025     -> valid
        Q2 2026 vs Q2 2025     -> valid
        H1 2026 vs H1 2025     -> valid

        Q2 2026 vs H1 2025     -> invalid
        Q1 2026 vs Q2 2025     -> invalid
        FY2025 vs Q1 2026      -> invalid
    """

    if current.period_type != prior.period_type:
        raise FinancialValidationError(
            "Period type mismatch: "
            f"{current.period_type.value!r} vs "
            f"{prior.period_type.value!r}."
        )

    if current.duration_months != prior.duration_months:
        raise FinancialValidationError(
            "Period duration mismatch: "
            f"{current.duration_months} months vs "
            f"{prior.duration_months} months."
        )

    if current.period_type == PeriodType.QUARTERLY:
        if current.fiscal_quarter != prior.fiscal_quarter:
            raise FinancialValidationError(
                "Quarter mismatch: "
                f"Q{current.fiscal_quarter} vs "
                f"Q{prior.fiscal_quarter}."
            )

    if current.period_type == PeriodType.YEAR_TO_DATE:
        if _month_day(current.period_end_date) != _month_day(
            prior.period_end_date
        ):
            raise FinancialValidationError(
                "Year-to-date periods end on different dates."
            )

    if (
        current.fiscal_year is not None
        and prior.fiscal_year is not None
        and current.fiscal_year <= prior.fiscal_year
    ):
        raise FinancialValidationError(
            "Expected the current period to be later than "
            "the comparison period."
        )

def validate_same_period(
    left: FinancialFact,
    right: FinancialFact,
) -> None:
    """
    Ensure two facts describe the same reporting period.
    """

    if left.fiscal_year != right.fiscal_year:
        raise FinancialValidationError(
            "Fiscal year mismatch."
        )

    if left.period_type != right.period_type:
        raise FinancialValidationError(
            "Period type mismatch."
        )

    if left.duration_months != right.duration_months:
        raise FinancialValidationError(
            "Period duration mismatch."
        )

    if left.fiscal_quarter != right.fiscal_quarter:
        raise FinancialValidationError(
            "Fiscal quarter mismatch."
        )

    if left.period_end_date != right.period_end_date:
        raise FinancialValidationError(
            "Period end-date mismatch."
        )
def validate_yoy_comparison(
    current: FinancialFact,
    prior: FinancialFact,
) -> None:
    """
    Run all deterministic guardrails required before YoY arithmetic.
    """

    validate_values_present(current, prior)
    validate_same_metric(current, prior)
    validate_same_units(current, prior)
    validate_same_accounting_basis(current, prior)
    validate_periods_for_yoy(current, prior)