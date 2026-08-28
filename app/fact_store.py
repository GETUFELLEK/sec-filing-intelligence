from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from app.quarterly_extraction import (
    extract_quarterly_statement_facts,
)
from app.schemas import FactQuery, FinancialFact
from app.table_extraction import extract_statement_facts


class FactStoreError(LookupError):
    pass


class FactNotFoundError(FactStoreError):
    pass


class AmbiguousFactError(FactStoreError):
    pass


class FactStore:
    """
    Simple in-memory store for normalized financial facts.

    V1 deliberately uses deterministic filtering rather than
    embedding similarity for exact numeric lookup.
    """

    def __init__(
        self,
        facts: Iterable[FinancialFact],
    ) -> None:
        self._facts = list(facts)

    @property
    def facts(self) -> list[FinancialFact]:
        return list(self._facts)

    def search(
        self,
        query: FactQuery,
    ) -> list[FinancialFact]:
        matches = self._facts

        if query.company is not None:
            matches = [
                fact
                for fact in matches
                if fact.company.lower()
                == query.company.lower()
            ]

        if query.metric_normalized is not None:
            matches = [
                fact
                for fact in matches
                if fact.metric_normalized
                == query.metric_normalized
            ]

        if query.fiscal_year is not None:
            matches = [
                fact
                for fact in matches
                if fact.fiscal_year
                == query.fiscal_year
            ]

        if query.fiscal_quarter is not None:
            matches = [
                fact
                for fact in matches
                if fact.fiscal_quarter
                == query.fiscal_quarter
            ]

        if query.period_type is not None:
            matches = [
                fact
                for fact in matches
                if fact.period_type
                == query.period_type
            ]

        if query.duration_months is not None:
            matches = [
                fact
                for fact in matches
                if fact.duration_months
                == query.duration_months
            ]

        if query.accounting_basis is not None:
            matches = [
                fact
                for fact in matches
                if fact.accounting_basis
                == query.accounting_basis
            ]

        return matches

    def get_one(
        self,
        query: FactQuery,
    ) -> FinancialFact:
        matches = self.search(query)

        if not matches:
            raise FactNotFoundError(
                f"No financial fact matched query: "
                f"{query.model_dump(exclude_none=True)}"
            )

        if len(matches) > 1:
            descriptions = [
                (
                    f"{fact.metric_normalized}, "
                    f"{fact.column_label}, "
                    f"{fact.value_raw}, "
                    f"{fact.source_file}"
                )
                for fact in matches
            ]

            raise AmbiguousFactError(
                "Query matched multiple financial facts: "
                + "; ".join(descriptions)
            )

        return matches[0]


def load_sample_fact_store() -> FactStore:
    """
    Load the filings currently supported by the prototype.
    """

    annual_pdf = Path(
        "data/sample_filings/tesla_2025_10k.pdf"
    )

    q1_pdf = Path(
        "data/sample_filings/tesla_2026_q1_10q.pdf"
    )

    q2_pdf = Path(
        "data/sample_filings/tesla_2026_q2_10q.pdf"
    )

    facts: list[FinancialFact] = []

    facts.extend(
        extract_statement_facts(annual_pdf)
    )

    facts.extend(
        extract_quarterly_statement_facts(q1_pdf)
    )

    facts.extend(
        extract_quarterly_statement_facts(q2_pdf)
    )

    return FactStore(facts)


if __name__ == "__main__":
    from app.schemas import PeriodType

    store = load_sample_fact_store()

    print(
        f"Loaded {len(store.facts)} financial facts."
    )

    fact = store.get_one(
        FactQuery(
            company="Tesla, Inc.",
            metric_normalized="total_revenue",
            fiscal_year=2026,
            fiscal_quarter=2,
            period_type=PeriodType.QUARTERLY,
            duration_months=3,
        )
    )

    print("\nRetrieved:")
    print(
        fact.model_dump_json(
            indent=2
        )
    )