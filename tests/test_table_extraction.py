from decimal import Decimal
from pathlib import Path

from app.table_extraction import (
    extract_statement_facts,
    parse_financial_value,
)


PDF = Path(
    "data/sample_filings/tesla_2025_10k.pdf"
)


def test_parse_positive_value():
    assert parse_financial_value("94,827") == Decimal("94827")


def test_parse_negative_parentheses():
    assert parse_financial_value("(338)") == Decimal("-338")


def test_parse_decimal():
    assert parse_financial_value("1.18") == Decimal("1.18")


def test_parse_dash_as_missing():
    assert parse_financial_value("—") is None


def test_extract_expected_number_of_facts():
    facts = extract_statement_facts(PDF)

    assert len(facts) == 12


def test_tesla_2025_total_revenue():
    facts = extract_statement_facts(PDF)

    fact = next(
        f
        for f in facts
        if f.metric_normalized == "total_revenue"
        and f.fiscal_year == 2025
    )

    assert fact.reported_value == Decimal("94827")
    assert fact.scale == "millions"
    assert fact.currency == "USD"


def test_tesla_2025_net_income():
    facts = extract_statement_facts(PDF)

    fact = next(
        f
        for f in facts
        if f.metric_normalized == "net_income"
        and f.fiscal_year == 2025
    )

    assert fact.reported_value == Decimal("3855")


def test_tesla_2024_total_revenue_from_same_statement():
    facts = extract_statement_facts(PDF)

    fact = next(
        f
        for f in facts
        if f.metric_normalized == "total_revenue"
        and f.fiscal_year == 2024
    )

    assert fact.reported_value == Decimal("97690")