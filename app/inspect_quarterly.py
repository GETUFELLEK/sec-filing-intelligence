from pathlib import Path

import pdfplumber


PDF_FILES = [
    Path("data/sample_filings/tesla_2026_q1_10q.pdf"),
    Path("data/sample_filings/tesla_2026_q2_10q.pdf"),
]


def inspect_quarterly_statement(pdf_path: Path) -> None:
    print("\n" + "=" * 90)
    print(pdf_path.name)
    print("=" * 90)

    with pdfplumber.open(pdf_path) as pdf:

        candidates = []

        for page_number, page in enumerate(pdf.pages, start=1):
            text = page.extract_text() or ""
            text_lower = text.lower()

            signals = [
                "consolidated statements of operations",
                "total revenues",
                "gross profit",
                "net income",
            ]

            if all(signal in text_lower for signal in signals):
                candidates.append(page_number)

        print(f"Candidate pages: {candidates}")

        for page_number in candidates:
            page = pdf.pages[page_number - 1]

            print("\n" + "-" * 90)
            print(f"PAGE {page_number}")
            print("-" * 90)

            print("\nPAGE TEXT:\n")
            print(page.extract_text() or "")

            tables = page.extract_tables()

            print(
                f"\nNUMBER OF TABLES DETECTED: "
                f"{len(tables)}"
            )

            for i, table in enumerate(tables, start=1):
                print(f"\n--- TABLE {i} ---")

                for row in table:
                    print(row)


if __name__ == "__main__":
    for pdf_path in PDF_FILES:
        inspect_quarterly_statement(pdf_path)