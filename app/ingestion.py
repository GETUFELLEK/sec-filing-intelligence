from __future__ import annotations

from pathlib import Path

import pdfplumber


STATEMENT_TITLE = "Consolidated Statements of Operations"


def find_statement_pages(pdf_path: str | Path) -> list[int]:
    """
    Find pages that look like the actual Consolidated Statements
    of Operations table.

    We intentionally require several signals instead of matching
    only the statement title.
    """
    pdf_path = Path(pdf_path)

    matches: list[int] = []

    with pdfplumber.open(pdf_path) as pdf:
        for page_number, page in enumerate(pdf.pages, start=1):
            text = page.extract_text() or ""

            required_signals = [
                STATEMENT_TITLE,
                "Total revenues",
                "Gross profit",
                "Net income",
            ]

            if all(signal.lower() in text.lower() for signal in required_signals):
                matches.append(page_number)

    return matches


def inspect_page(
    pdf_path: str | Path,
    page_number: int,
) -> None:
    """
    Print extracted text and basic table information for one PDF page.
    """
    pdf_path = Path(pdf_path)

    with pdfplumber.open(pdf_path) as pdf:
        page = pdf.pages[page_number - 1]

        print("=" * 80)
        print(f"FILE: {pdf_path.name}")
        print(f"PAGE: {page_number}")
        print("=" * 80)

        text = page.extract_text() or ""

        print("\nEXTRACTED TEXT\n")
        print(text)

        print("\n" + "=" * 80)
        print("TABLES DETECTED")
        print("=" * 80)

        tables = page.extract_tables()

        print(f"\nNumber of detected tables: {len(tables)}")

        for i, table in enumerate(tables, start=1):
            print(f"\n--- TABLE {i} ---")

            for row in table:
                print(row)


if __name__ == "__main__":
    pdf_path = Path(
        "data/sample_filings/tesla_2025_10k.pdf"
    )

    pages = find_statement_pages(pdf_path)

    print(f"Candidate statement pages: {pages}")

    for page_number in pages:
        inspect_page(pdf_path, page_number)