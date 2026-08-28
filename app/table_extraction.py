from __future__ import annotations

import re
from decimal import Decimal
from pathlib import Path

import pdfplumber

from app.ingestion import find_statement_pages
from app.schemas import (
    AccountingBasis,
    FinancialFact,
    FilingType,
    PeriodType,
)


STATEMENT_TITLE = "Consolidated Statements of Operations"

# We intentionally start with a small, trustworthy metric set.
TARGET_METRICS = {
    "Total revenues": "total_revenue",
    "Gross profit": "gross_profit",
    "Income from operations": "operating_income",
    "Net income": "net_income",
}


def normalize_whitespace(text: str) -> str:
    """Collapse repeated/newline whitespace into single spaces."""
    return " ".join(text.split())


def extract_years(page_text: str) -> list[int]:
    """
    Extract year columns from an annual Statements of Operations page.

    Example source text:

        Year Ended December 31,
        2025 2024 2023
    """
    pattern = re.compile(
        r"Year Ended December 31,\s*"
        r"(\d{4})\s+(\d{4})\s+(\d{4})",
        re.IGNORECASE,
    )

    match = pattern.search(page_text)

    if not match:
        raise ValueError(
            "Could not determine year columns from statement page."
        )

    return [int(year) for year in match.groups()]


def is_financial_value(token: str) -> bool:
    """
    Return True if a token looks like a financial numeric value.

    Supports:
        94,827
        1.18
        (338)
        (5,001)
        —
    """
    token = token.strip()

    if token in {"—", "-", "–"}:
        return True

    pattern = re.compile(
        r"^\(?-?\d[\d,]*(?:\.\d+)?\)?$"
    )

    return bool(pattern.match(token))


def parse_financial_value(token: str) -> Decimal | None:
    """
    Convert SEC-style financial text to Decimal.

    Examples:
        "94,827" -> Decimal("94827")
        "(338)"  -> Decimal("-338")
        "1.18"   -> Decimal("1.18")
        "—"      -> None
    """
    token = token.strip()

    if token in {"—", "-", "–"}:
        return None

    negative = token.startswith("(") and token.endswith(")")

    cleaned = (
        token.replace(",", "")
        .replace("(", "")
        .replace(")", "")
        .strip()
    )

    value = Decimal(cleaned)

    if negative:
        value = -value

    return value


def extract_row_values(
    row: list[str | None],
) -> list[tuple[str, Decimal | None]]:
    """
    Extract numeric values while ignoring layout artifacts such as
    "$", empty cells, and None.

    Example pdfplumber row:

        [
            "Automotive sales",
            "$",
            "65,821",
            "",
            "$",
            "72,480",
            "",
            "$",
            "78,509"
        ]

    becomes:

        [
            ("65,821", Decimal("65821")),
            ("72,480", Decimal("72480")),
            ("78,509", Decimal("78509"))
        ]
    """
    values: list[tuple[str, Decimal | None]] = []

    for cell in row[1:]:
        if cell is None:
            continue

        token = normalize_whitespace(cell)

        if not token or token == "$":
            continue

        if is_financial_value(token):
            values.append(
                (token, parse_financial_value(token))
            )

    return values


def select_statement_table(
    tables: list[list[list[str | None]]],
) -> list[list[str | None]]:
    """
    Find the table that contains our expected financial statement rows.

    We do not assume table 0 is always the correct table.
    """
    required_rows = {
        "Total revenues",
        "Gross profit",
        "Net income",
    }

    for table in tables:
        labels = {
            normalize_whitespace(row[0])
            for row in table
            if row and row[0]
        }

        if required_rows.issubset(labels):
            return table

    raise ValueError(
        "Could not find a trustworthy Statements of Operations table."
    )


def extract_statement_facts(
    pdf_path: str | Path,
) -> list[FinancialFact]:
    """
    Extract a small set of validated financial facts from Tesla's
    annual Consolidated Statements of Operations.
    """
    pdf_path = Path(pdf_path)

    candidate_pages = find_statement_pages(pdf_path)

    if len(candidate_pages) != 1:
        raise ValueError(
            "Expected exactly one Statements of Operations page, "
            f"found {candidate_pages}"
        )

    page_number = candidate_pages[0]

    facts: list[FinancialFact] = []

    with pdfplumber.open(pdf_path) as pdf:
        page = pdf.pages[page_number - 1]

        page_text = page.extract_text() or ""

        years = extract_years(page_text)

        tables = page.extract_tables()

        statement_table = select_statement_table(tables)

        for row in statement_table:
            if not row or not row[0]:
                continue

            row_label = normalize_whitespace(row[0])

            if row_label not in TARGET_METRICS:
                continue

            values = extract_row_values(row)

            if len(values) != len(years):
                raise ValueError(
                    f"Expected {len(years)} values for "
                    f"{row_label!r}, but found {len(values)}: "
                    f"{values}"
                )

            metric_normalized = TARGET_METRICS[row_label]

            for year, (value_raw, value) in zip(years, values):
                fact = FinancialFact(
                    company="Tesla, Inc.",
                    filing_type=FilingType.TEN_K,
                    source_file=pdf_path.name,

                    statement_name=STATEMENT_TITLE,
                    table_title=STATEMENT_TITLE,

                    metric_raw=row_label,
                    metric_normalized=metric_normalized,

                    value_raw=value_raw,
                    reported_value=value,

                    currency="USD",
                    scale="millions",

                    fiscal_year=year,
                    fiscal_quarter=None,
                    period_type=PeriodType.ANNUAL,
                    duration_months=12,
                    period_end_date=f"{year}-12-31",
                    column_label=f"Year ended December 31, {year}",

                    accounting_basis=AccountingBasis.GAAP,

                    page_number=page_number,
                    row_label=row_label,

                    raw_context=" | ".join(
                        normalize_whitespace(cell)
                        for cell in row
                        if cell
                    ),

                    confidence=1.0,
                )

                facts.append(fact)

    return facts


if __name__ == "__main__":
    path = Path(
        "data/sample_filings/tesla_2025_10k.pdf"
    )

    facts = extract_statement_facts(path)

    print(f"\nExtracted {len(facts)} financial facts:\n")

    for fact in facts:
        print(
            f"{fact.metric_normalized:20} "
            f"{fact.fiscal_year}: "
            f"{fact.value_raw:>10} "
            f"{fact.scale} "
            f"(PDF page {fact.page_number})"
        )