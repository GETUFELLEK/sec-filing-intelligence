# SEC Filing Intelligence

Trustworthy financial question answering over SEC filing PDFs. This system enables users to ask natural-language questions about company financials and receive answers grounded in SEC filing documents with full traceability.

## Overview

SEC Filing Intelligence is a lightweight agentic system designed to answer financial questions extracted from SEC filings (10-K, 10-Q). The core design principle is:

> **Use probabilistic models where interpretation is required, and deterministic systems where exactness is available.**

### Key Features

- **Dual retrieval paths**: Numeric questions use exact structured lookup; narrative questions use semantic retrieval
- **Period-aware retrieval**: Correctly distinguishes quarterly vs. year-to-date values
- **Deterministic calculations**: Financial math is performed with Python `Decimal`, not LLMs
- **Validation before computation**: Ensures facts can be safely combined before calculation
- **Full traceability**: Every answer includes source file, page, statement, row, and raw values
- **Graceful abstention**: System explicitly refuses to answer when facts are missing or ambiguous
- **Comprehensive evaluation**: Hand-verified golden set with exact expected values

## Architecture

The system follows a two-path routing model:

```
User Question
      |
      v
LLM Intent Parser (structured output)
      |
      v
Validated Query
   /       \
  /         \
Numeric    Narrative
  |            |
Exact         Semantic
FactStore     Retrieval
  |            |
Validation    Top-k Evidence
  |            |
Python        Grounded LLM
Math          Synthesis
  \            /
   \          /
    Grounded Answer + Evidence
```

### Numeric Path

For questions like "What was Tesla's Q2 2026 revenue?":

1. **Intent parsing**: LLM converts question to structured `LLMIntent`
2. **Resolution**: Deterministic code converts intent to `FinancialQuery`
3. **Retrieval**: Exact lookup in `FactStore` yields `FinancialFact`
4. **Validation**: Confirms facts can be combined (same company, period, units, accounting basis)
5. **Calculation**: Deterministic Python computes answer
6. **Answer**: Returns value with full provenance

### Narrative Path

For questions like "What did management say about margin pressure?":

1. **Intent parsing**: LLM identifies question as narrative
2. **Embedding**: Question is embedded and compared against cached document chunks
3. **Retrieval**: Cosine similarity returns top-k relevant passages
4. **Synthesis**: LLM synthesizes answer grounded in retrieved evidence
5. **Answer**: Returns narrative response with source citations

## Getting Started

### Installation

```bash
pip install -r requirements.txt
```

### Configuration

The system is configured to work with Tesla financial data in the `data/sample_filings/` directory.

### Running the Application

Start the Streamlit interface:

```bash
streamlit run streamlit_app.py
```

The app will open at `http://localhost:8501`

## Supported Metrics and Operations

### Structured Financial Metrics

- Total revenue
- Gross profit
- Operating income
- Net income

### Operations

- Exact lookup: "What was Tesla's Q2 2026 revenue?"
- Percentage change: "What was Tesla's Q1 to Q2 2026 revenue growth?"
- Absolute change: "How much did revenue change quarter-over-quarter?"
- Ratio calculation: "What was Tesla's Q2 2026 operating margin?"

### Period Types

- Annual
- Quarterly
- Year-to-date (YTD)
- Quarterly vs. YTD distinction with period metadata

## Design Principles

### Why Two Retrieval Paths?

**Numeric questions** require exact identity across:
- Metric name
- Fiscal year and quarter
- Period type (quarterly vs. YTD)
- Duration
- Units
- Accounting basis (GAAP vs. non-GAAP)

Embeddings preserve semantic similarity but not exact table position or fine-grained label distinctions. Therefore, numeric questions use structured retrieval.

**Narrative questions** ask for semantic meaning across natural-language passages, making embeddings and cosine similarity appropriate.

### Period-Aware Retrieval

SEC 10-Q filings contain both:

| Period | Revenue |
|---|---:|
| Three months ended June 30, 2026 | 28,236 |
| Six months ended June 30, 2026 | 50,623 |

A system that only indexes `Tesla + revenue + 2026` cannot safely distinguish these. The fact identity includes:

- `period_type` (quarterly vs. YTD)
- `duration_months` (3 vs. 6)
- `fiscal_quarter` and `period_end_date`
- `metric` (revenue, operating_income, etc.)

### Deterministic Calculations

Once exact source values are retrieved and validated, arithmetic is performed with Python `Decimal` rather than an LLM:

```python
margin = (
    operating_income.reported_value
    / revenue.reported_value
) * Decimal("100")
```

**Advantages:**
- Reproducibility
- Lower hallucination risk
- Easier testing and auditability

### Validation Before Calculation

Retrieved facts must satisfy validation checks before combination:

- Same company
- Same period and quarter
- Same duration
- Same units
- Same accounting basis

Mismatches (e.g., Q2 operating income with YTD revenue) are rejected rather than silently computed.

### Trust Boundaries

The system enforces strict trust boundaries:

| Failure Mode | Guardrail |
|---|---|
| Wrong intent classification | `LLMIntent` → deterministic `resolve_intent()` |
| Wrong metric / similar labels | Normalized exact metric mapping |
| Quarterly vs YTD confusion | Period type + duration + quarter + end date |
| Multiple matching facts | Ambiguity error; never choose arbitrarily |
| Missing data | Controlled not-found response |
| Wrong units / accounting basis | Validation before calculation |
| Arithmetic error | Python `Decimal`, not LLM math |
| Narrative hallucination | Answer only from retrieved evidence |
| Irrelevant narrative chunks | Top-k semantic retrieval |

**Core principle:** The architecture itself is the primary guardrail—not just the prompt.

## Data Flow

### Numeric Query Example

```
Question: "What was Tesla's Q2 2026 operating margin?"

LLMIntent(
    company="Tesla",
    question_type="numeric",
    operation="operating_margin",
    fiscal_year=2026,
    fiscal_quarter=2,
)

FinancialQuery: Tesla, operating_margin, Q2 2026

FactQuery #1: Tesla + operating_income + Q2 2026
FactQuery #2: Tesla + total_revenue + Q2 2026

FinancialFact #1: operating_income = 398 million USD
FinancialFact #2: total_revenue = 28,236 million USD

Validation: All facts match in company, period, duration, units
Calculation: (398 / 28,236) * 100 = 1.41%

Answer: Operating margin = 1.41% (source: Tesla Q2 2026 10-Q)
```

### Narrative Query Example

```
Question: "What did management say about margin pressure?"

LLMIntent: question_type = "narrative"

Query embedding vs. cached document embeddings
→ Cosine similarity
→ Top-k passages retrieved

Grounded LLM synthesis using retrieved passages
→ Answer with source citations
```

## Implementation Structure

### Core Modules

- **`workflow.py`**: Main orchestration and routing logic
- **`answer_engine.py`**: Numeric query execution and calculations
- **`llm_query_parser.py`**: Intent parsing and structured output handling
- **`narrative_retrieval.py`**: Semantic retrieval for narrative questions
- **`fact_store.py`**: In-memory structured financial fact storage
- **`validation.py`**: Pre-calculation validation logic
- **`calculations.py`**: Deterministic financial math
- **`schemas.py`**: Data class definitions for type safety

### API Endpoints

- `answer_question(question, store, narrative_chunks)`: Main entry point
- `parse_query(question)`: Intent parsing
- `answer_narrative(question, chunks)`: Narrative path
- `execute_query(query, store)`: Numeric path

## Evaluation

### Golden Question Set

10 representative questions covering:

- Exact financial lookup
- Calculated metrics (YoY growth, margins)
- Period-aware retrieval (quarterly vs. YTD)
- Narrative retrieval
- Ambiguity handling
- Unsupported questions

### Results

**10 / 10 passed**

Example test cases:

```
Q2 2026 revenue → 28,236
Six-month 2026 revenue → 50,623
Q2 2026 operating margin → 1.41%
"profit" (ambiguous) → clarification required
"What day is today?" (unsupported) → rejection
```

### Evaluation Philosophy

- Numeric questions: exact expected values and behavior
- Narrative questions: expected source/concepts + qualitative review
- Failure cases are part of the benchmark, not only successful cases

Run evaluation:

```bash
python eval/run_eval.py
```

## Production Deployment

### Architecture Evolution

For production deployment to tens of thousands of filings:

**Structured Path**
```
Financial facts → Indexed relational/analytical store
→ Indexes on company, metric, filing, year, period
```

**Narrative Path**
```
Document chunks → Vector index → Metadata filtering
→ Candidate retrieval → Optional reranking
```

### Deployment Steps

- Replace in-memory `FactStore` with persistent indexed storage (SQL/analytical DB)
- Replace local JSON embedding cache with vector storage (Pinecone, Weaviate, etc.)
- Expose versioned REST API
- Containerize and deploy behind authentication/load balancer
- Move document ingestion to asynchronous workers
- Add retries, timeouts, and observability
- Implement audit logging and security controls
- Add CI/CD and regression evaluation

### Scaling Considerations

**What breaks first in prototype:**
- In-memory fact storage
- Brute-force vector comparisons
- Local JSON cache
- Synchronous document preparation
- Hardcoded company/metric support

**Production improvements:**
- Section-aware/layout-aware chunking
- Hybrid lexical + semantic retrieval
- Reranking models
- Extraction confidence scores
- Reconciliation across filing versions
- Amended filing handling
- Richer GAAP/non-GAAP representation

## Limitations and Future Work

### Current Limitations

- Tesla only (easily extended)
- Selected income-statement metrics
- Latest-filing narrative policy
- No balance-sheet/cash-flow extraction
- Small evaluation set
- Simple fixed-size chunking
- No retrieval reranker
- No persistent production storage

### Next Steps

**Short-term (1 day):**
- Add gross margin
- Add balance-sheet extraction
- Period-aware narrative metadata filtering
- Enlarge evaluation set

**Medium-term (1 week):**
- Multi-company ingestion
- Persistent SQL + vector stores
- Layout-aware PDF parsing
- Hybrid retrieval and reranking
- Production-ready API
- Observability and monitoring

**Long-term:**
- Full SEC corpus support
- All financial statements
- Advanced agentic planning
- Conversational memory for multi-turn analysis
- Confidence scoring and reconciliation

## File Structure

```
sec-filing-intelligence/
├── README.md                          # This file
├── requirements.txt                   # Python dependencies
├── streamlit_app.py                   # Web UI entry point
├── app/                               # Application modules
│   ├── answer_engine.py               # Numeric query logic
│   ├── fact_store.py                  # Fact storage
│   ├── ingestion.py                   # PDF → structured data
│   ├── llm_query_parser.py            # Intent parsing
│   ├── narrative_retrieval.py         # Semantic retrieval
│   ├── schemas.py                     # Data structures
│   ├── validation.py                  # Pre-calculation checks
│   ├── workflow.py                    # Main orchestration
│   └── calculations.py                # Financial math
├── data/
│   ├── cache/                         # Cached embeddings
│   └── sample_filings/                # Sample 10-Q PDFs
├── eval/
│   ├── run_eval.py                    # Evaluation runner
│   └── golden_questions.json          # Hand-verified test set
└── tests/                             # Unit tests
```

## Dependencies

Key libraries:

- `streamlit`: Web UI
- `openai`: LLM for intent parsing and narrative synthesis
- `numpy`, `faiss`: Vector similarity search
- `pypdf`: PDF extraction
- `pydantic`: Data validation

See `requirements.txt` for complete list.

## Contributing

This is a research prototype. Contributions welcome for:

- Additional financial metrics
- Multi-company support
- Improved PDF parsing
- Production infrastructure
- Enhanced evaluation

## License

This project is provided as-is for research and educational purposes.

## FAQ

### Why not just use a vector database for everything?

Embeddings preserve semantic similarity, not exact numerical identity or table position. Financial facts need deterministic retrieval.

### Why use an LLM at all?

Natural language is variable and ambiguous. The LLM interprets user intent, but deterministic code verifies and executes that intent safely.

### What about conversational memory?

The current task is primarily stateless financial Q&A. Persistent memory would add complexity without improving the core use case. We'd add it for multi-turn interactive analysis if needed.

### How does this differ from ChatGPT + context?

This system separates concerns: LLM handles interpretation and synthesis, but deterministic retrieval and validation prevent hallucination of financial facts. Every numeric answer is reproducible and traceable.

### Can this work with other companies/filings?

Yes. The architecture supports multi-company extension. The current implementation scopes to Tesla for verification depth.

### What about balance sheet and cash flow?

Not currently extracted. The architecture supports it; implementation focused on income-statement metrics first.

---

**Last updated:** September 2026  
**Status:** Research Prototype
