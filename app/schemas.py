from __future__ import annotations

from decimal import Decimal
from enum import Enum

from pydantic import BaseModel, Field


# ─────────────────────────────────────────────────────────────
# ENUMS  (defined first — every model below depends on these)
# ─────────────────────────────────────────────────────────────

class FilingType(str, Enum):
    TEN_K = "10-K"
    TEN_Q = "10-Q"


class PeriodType(str, Enum):
    ANNUAL = "annual"
    QUARTERLY = "quarterly"
    YEAR_TO_DATE = "year_to_date"
    UNKNOWN = "unknown"


class AccountingBasis(str, Enum):
    GAAP = "GAAP"
    NON_GAAP = "non-GAAP"
    UNKNOWN = "unknown"


class Scale(str, Enum):
    ONES = "ones"
    THOUSANDS = "thousands"
    MILLIONS = "millions"
    BILLIONS = "billions"
    UNKNOWN = "unknown"

    def multiplier(self) -> int:
        return {
            Scale.ONES: 1,
            Scale.THOUSANDS: 1_000,
            Scale.MILLIONS: 1_000_000,
            Scale.BILLIONS: 1_000_000_000,
            Scale.UNKNOWN: 1,   # never silently scale an unknown; validation catches it
        }[self]


class ExtractionStatus(str, Enum):
    EXTRACTED = "extracted"
    AMBIGUOUS = "ambiguous"
    VALIDATION_FAILED = "validation_failed"


class QuestionType(str, Enum):
    NUMERIC = "numeric"
    NARRATIVE = "narrative"
    UNSUPPORTED ="unsupported"


class QueryOperation(str, Enum):
    LOOKUP = "lookup"
    PERCENTAGE_CHANGE = "percentage_change"
    ABSOLUTE_CHANGE = "absolute_change"
    OPERATING_MARGIN = "operating_margin"
    GROSS_MARGIN = "gross_margin"


class ComparisonType(str, Enum):
    NONE = "none"
    YEAR_OVER_YEAR = "year_over_year"


class MetricName(str, Enum):
    TOTAL_REVENUE = "total_revenue"
    NET_INCOME = "net_income"
    GROSS_PROFIT = "gross_profit"
    OPERATING_INCOME = "operating_income"
    DILUTED_EPS = "diluted_eps"
    CASH_AND_EQUIVALENTS = "cash_and_equivalents"
    OPERATING_CASH_FLOW = "operating_cash_flow"


# ─────────────────────────────────────────────────────────────
# PERIOD
# ─────────────────────────────────────────────────────────────

class PeriodSpec(BaseModel):
    fiscal_year: int
    fiscal_quarter: int | None = None
    period_type: PeriodType
    duration_months: int
    period_end_date: str
    column_label: str


# ─────────────────────────────────────────────────────────────
# FINANCIAL FACT  (the structured record parsed from a PDF table)
# ─────────────────────────────────────────────────────────────

class FinancialFact(BaseModel):
    # --- Company / document identity ---
    company: str
    filing_type: FilingType
    source_file: str

    # --- Financial statement context ---
    statement_name: str
    table_title: str | None = None

    # --- Metric identity ---
    # metric_raw  = the exact row label from the PDF (traceability, near-miss guard)
    # metric_normalized = canonical mapping, ONLY when confidently matched
    metric_raw: str
    metric_normalized: MetricName | None = None

    # --- Value ---
    # value_raw       = exact string from the PDF, e.g. "(1,234)" or "94,827"
    # reported_value  = parsed number IN the reported scale (94,827 stays 94,827)
    # Normalization to absolute dollars happens at COMPUTE time, not here,
    # so the citation matches the filing exactly.
    value_raw: str
    reported_value: Decimal | None = None

    # --- Unit context ---
    currency: str | None = "USD"
    scale: Scale = Scale.UNKNOWN

    # --- Period context ---
    fiscal_year: int | None = None
    fiscal_quarter: int | None = None
    period_type: PeriodType = PeriodType.UNKNOWN
    duration_months: int | None = None
    period_end_date: str | None = None
    column_label: str | None = None

    # --- Reporting context ---
    is_unaudited: bool = False
    accounting_basis: AccountingBasis = AccountingBasis.UNKNOWN

    # --- Traceability ---
    page_number: int
    row_label: str | None = None
    raw_context: str | None = None

    # --- Extraction quality ---
    extraction_status: ExtractionStatus = ExtractionStatus.EXTRACTED
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)

    def absolute_value(self) -> Decimal | None:
        """Value normalized to absolute dollars, for deterministic math only."""
        if self.reported_value is None:
            return None
        return self.reported_value * self.scale.multiplier()


# ─────────────────────────────────────────────────────────────
# INTENT  (loose — what the LLM is allowed to output)
# ─────────────────────────────────────────────────────────────

class LLMIntent(BaseModel):
    company: str | None = None
    question_type: QuestionType

    metric: MetricName | None = None
    operation: QueryOperation | None = None

    fiscal_year: int | None = None
    prior_year: int | None = None
    fiscal_quarter: int | None = Field(default=None, ge=1, le=4)

    period_type: PeriodType | None = None
    duration_months: int | None = None

    comparison: ComparisonType = ComparisonType.NONE
    narrative_topic: str | None = None

    # The LLM's own honest exit — feeds the clarify/abstain branch.
    needs_clarification: bool = False
    clarification_reason: str | None = None


# ─────────────────────────────────────────────────────────────
# QUERY  (strict — validated internal form the pipeline runs on)
# ─────────────────────────────────────────────────────────────

class FinancialQuery(BaseModel):
    original_question: str
    company: str
    question_type: QuestionType

    metric: MetricName | None = None
    operation: QueryOperation | None = None

    fiscal_year: int | None = None
    prior_year: int | None = None
    fiscal_quarter: int | None = None

    period_type: PeriodType | None = None
    duration_months: int | None = None

    comparison: ComparisonType = ComparisonType.NONE
    narrative_topic: str | None = None

class AnswerStatus(str, Enum):
    ANSWERED = "answered"
    AMBIGUOUS = "ambiguous"
    NOT_FOUND = "not_found"
    VALIDATION_FAILED = "validation_failed"
    UNSUPPORTED = "unsupported"
    System_Error = 'system_error'


class SourceEvidence(BaseModel):
    source_file: str
    page_number: int

    statement_name: str
    row_label: str | None = None
    column_label: str | None = None

    value_raw: str | None = None
    scale: str | None = None
    currency: str | None = None


class NumericAnswer(BaseModel):
    status: AnswerStatus

    question: str

    answer_text: str

    result_value: Decimal | None = None
    result_unit: str | None = None

    calculation: str | None = None

    evidence: list[SourceEvidence] = Field(
        default_factory=list
    )
class FactQuery(BaseModel):
    """The deterministic lookup key against the Fact Store."""
    company: str | None = None
    metric_normalized: MetricName | None = None

    fiscal_year: int | None = None
    fiscal_quarter: int | None = None

    period_type: PeriodType | None = None
    duration_months: int | None = None

    accounting_basis: AccountingBasis | None = None