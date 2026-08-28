from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

import pdfplumber

from app.ingestion import find_statement_pages
from app.schemas import (
    AccountingBasis,
    FinancialFact,
    FilingType,
    PeriodSpec,
    PeriodType,
)
from app.table_extraction import (
    STATEMENT_TITLE,
    TARGET_METRICS,
    extract_row_values,
    normalize_whitespace,
    select_statement_table,
)


DURATION_WORDS = {
    "Three": 3,
    "Six": 6,
    "Nine": 9,
}


def extract_quarterly_periods(
    page_text: str,
) -> list[PeriodSpec]:
    """
    Parse period definitions from a quarterly statement header.

    Supported examples:

        Three Months Ended March 31,
        2026 2025

    and:

        Three Months Ended June 30, Six Months Ended June 30,
        2026 2025 2026 2025
    """

    lines = [
        normalize_whitespace(line)
        for line in page_text.splitlines()
        if line.strip()
    ]

    header_index = None
    period_groups = None

    pattern = re.compile(
        r"(Three|Six|Nine)\s+Months\s+Ended\s+"
        r"([A-Za-z]+)\s+(\d{1,2}),",
        re.IGNORECASE,
    )

    for i, line in enumerate(lines):
        matches = pattern.findall(line)

        if matches:
            header_index = i
            period_groups = matches
            break

    if header_index is None or not period_groups:
        raise ValueError(
            "Could not find quarterly period header."
        )

    # Find the next line containing only year columns.
    years: list[int] | None = None

    for line in lines[
        header_index + 1 : header_index + 4
    ]:
        tokens = line.split()

        if (
            tokens
            and all(
                re.fullmatch(r"\d{4}", token)
                for token in tokens
            )
        ):
            years = [int(token) for token in tokens]
            break

    if years is None:
        raise ValueError(
            "Could not identify quarterly year columns."
        )

    expected_years = len(period_groups) * 2

    if len(years) != expected_years:
        raise ValueError(
            f"Expected {expected_years} year columns, "
            f"but found {years}."
        )

    periods: list[PeriodSpec] = []

    year_index = 0

    for duration_word, month_name, day_text in period_groups:
        # Regex is case-insensitive, so normalize capitalization.
        duration_word = duration_word.capitalize()
        month_name = month_name.capitalize()

        duration_months = DURATION_WORDS[duration_word]
        day = int(day_text)

        month_number = datetime.strptime(
            month_name,
            "%B",
        ).month

        # For Tesla's calendar fiscal year, a 3-month period
        # ending Mar/Jun/Sep/Dec corresponds to Q1/Q2/Q3/Q4.
        quarter_map = {
            3: 1,
            6: 2,
            9: 3,
            12: 4,
        }

        for _ in range(2):
            year = years[year_index]
            year_index += 1

            if duration_months == 3:
                period_type = PeriodType.QUARTERLY
                fiscal_quarter = quarter_map.get(
                    month_number
                )
            else:
                period_type = PeriodType.YEAR_TO_DATE
                fiscal_quarter = None

            period_end_date = (
                f"{year:04d}-"
                f"{month_number:02d}-"
                f"{day:02d}"
            )

            column_label = (
                f"{duration_months} months ended "
                f"{month_name} {day}, {year}"
            )

            periods.append(
                PeriodSpec(
                    fiscal_year=year,
                    fiscal_quarter=fiscal_quarter,
                    period_type=period_type,
                    duration_months=duration_months,
                    period_end_date=period_end_date,
                    column_label=column_label,
                )
            )

    return periods


def extract_quarterly_statement_facts(
    pdf_path: str | Path,
) -> list[FinancialFact]:
    """
    Extract supported financial metrics from a Tesla 10-Q while
    preserving quarterly/YTD period semantics.
    """

    pdf_path = Path(pdf_path)

    candidate_pages = find_statement_pages(pdf_path)

    if len(candidate_pages) != 1:
        raise ValueError(
            "Expected exactly one Statements of Operations page, "
            f"found {candidate_pages}."
        )

    page_number = candidate_pages[0]

    facts: list[FinancialFact] = []

    with pdfplumber.open(pdf_path) as pdf:
        page = pdf.pages[page_number - 1]

        page_text = page.extract_text() or ""

        periods = extract_quarterly_periods(
            page_text
        )

        tables = page.extract_tables()

        statement_table = select_statement_table(
            tables
        )

        for row in statement_table:
            if not row or not row[0]:
                continue

            row_label = normalize_whitespace(
                row[0]
            )

            if row_label not in TARGET_METRICS:
                continue

            values = extract_row_values(row)

            if len(values) != len(periods):
                raise ValueError(
                    f"{row_label!r}: expected "
                    f"{len(periods)} values but "
                    f"found {len(values)}."
                )

            metric_normalized = (
                TARGET_METRICS[row_label]
            )

            for period, (
                value_raw,
                value,
            ) in zip(periods, values):

                facts.append(
                    FinancialFact(
                        company="Tesla, Inc.",
                        filing_type=FilingType.TEN_Q,
                        source_file=pdf_path.name,

                        statement_name=STATEMENT_TITLE,
                        table_title=STATEMENT_TITLE,

                        metric_raw=row_label,
                        metric_normalized=metric_normalized,

                        value_raw=value_raw,
                        reported_value=value,

                        currency="USD",
                        scale="millions",

                        fiscal_year=period.fiscal_year,
                        fiscal_quarter=(
                            period.fiscal_quarter
                        ),
                        period_type=(
                            period.period_type
                        ),
                        duration_months=(
                            period.duration_months
                        ),
                        period_end_date=(
                            period.period_end_date
                        ),
                        column_label=(
                            period.column_label
                        ),

                        accounting_basis=(
                            AccountingBasis.GAAP
                        ),

                        is_unaudited=True,

                        page_number=page_number,
                        row_label=row_label,

                        raw_context=" | ".join(
                            normalize_whitespace(cell)
                            for cell in row
                            if cell
                        ),

                        confidence=1.0,
                    )
                )

    return facts


if __name__ == "__main__":
    paths = [
        Path(
            "data/sample_filings/"
            "tesla_2026_q1_10q.pdf"
        ),
        Path(
            "data/sample_filings/"
            "tesla_2026_q2_10q.pdf"
        ),
    ]

    for path in paths:
        print("\n" + "=" * 90)
        print(path.name)
        print("=" * 90)

        facts = extract_quarterly_statement_facts(
            path
        )

        print(
            f"Extracted {len(facts)} facts\n"
        )

        for fact in facts:
            print(
                f"{fact.metric_normalized:20} "
                f"{fact.column_label:35} "
                f"{fact.value_raw:>10}"
            )