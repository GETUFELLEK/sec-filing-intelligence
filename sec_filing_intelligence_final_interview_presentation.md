# SEC Filing Intelligence — Final Interview Presentation

## Slide 1 — Title

# SEC Filing Intelligence
### Trustworthy Financial Question Answering over SEC Filing PDFs

**Getu Fellek**  
Research Engineer — Post-Training & Small Language Models (SLMs)  
Final Interview Presentation

**Core design principle**

> Use probabilistic models where interpretation is required, and deterministic systems where exactness is available.

---

## Slide 2 — What Was the Assignment?

### Goal

Build a tangible prototype that lets a user ask natural-language questions about company financials and receive answers grounded in SEC filing PDFs.

### Important constraints

- PDF is the primary source of truth.
- Live EDGAR/XBRL access should not be the primary runtime path.
- Financial tables can have inconsistent layouts, quarterly and YTD columns side by side, GAAP and non-GAAP values, similar line-item names, footnotes, and restatements.
- A previous assistant had failed by hallucinating financial values, mixing annual and quarterly periods, confusing similar metrics, and providing weak traceability.

### What the assignment evaluates

- reasoning and engineering judgment,
- agentic/workflow design,
- trust and hallucination control,
- retrieval choices for numeric tables,
- traceability,
- evaluation,
- scaling and product thinking.

**Key interpretation**

> This is not a generic chatbot problem. It is a trust problem over messy financial documents.

---

## Slide 3 — Deliberate Scope Reduction

### What I implemented

- **Company:** Tesla
- **Filings:** representative 10-K and 10-Q PDFs
- **Structured numeric metrics:** Total revenue, Gross profit, Operating income, Net income
- **Periods:** Annual, Quarterly, Year-to-date
- **Operations:** Exact lookup, Percentage change, Absolute change, Operating margin
- **Narrative questions:** semantic retrieval over filing prose
- **Traceability:** source file, page, statement, row, period, raw value, calculation

### What I intentionally did not implement

- Full SEC corpus
- All companies
- Every financial statement
- Balance sheet and cash-flow extraction
- Production vector database
- Full conversational memory
- Complex autonomous-agent orchestration

### Why

> I narrowed implementation coverage, not architectural capability.

The assignment explicitly encourages thoughtful scope reductions. I preferred a narrow system whose behavior I could verify deeply over a broad system with weak reliability.

---

## Slide 4 — Why Not Use One Generic RAG Pipeline?

### Numeric questions and narrative questions require different retrieval behavior

**Numeric financial questions**

Example:

> “What was Tesla’s Q2 2026 revenue?”

Need exact identity across metric, year, quarter, period type, duration, units, and accounting basis.

Embeddings are not designed to preserve exact table position or fine label distinctions.

**Narrative questions**

Example:

> “What did management say about margin pressure?”

Need semantic similarity across natural-language passages.

### Design decision

```text
User Question
      |
      v
LLM Intent Parser
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
    Grounded Answer
```

**Key principle**

> Exact financial facts use structured retrieval. Narrative questions use semantic retrieval.

---

## Slide 5 — End-to-End Runtime Architecture

```text
Streamlit UI
    |
    v
workflow.py
    |
    v
parse_query(question)
    |
    v
llm_query_parser.py
    |
    +--> LLM call --> LLMIntent
    |
    +--> resolve_intent()
              |
              v
        FinancialQuery
              |
              v
         workflow.py
          /        \
         /          \
   NUMERIC        NARRATIVE
      |               |
      v               v
answer_engine.py  narrative_retrieval.py
      |               |
      v               v
FactQuery         Query Embedding
      |               |
      v               v
FactStore         Cosine Similarity
      |               |
      v               v
FinancialFact(s)  Top-k Passages
      |               |
      v               v
Validation        Grounded LLM
      |               |
      v               v
Calculations      Narrative Answer
      \               /
       \             /
        Final Answer
             |
             v
        Streamlit UI
```

### Why the workflow is intentionally simple

I use a lightweight agentic workflow rather than a complex autonomous-agent framework.

The workflow has a small number of explicit transitions, so plain Python orchestration is easier to inspect, test, debug, modify live, and reason about.

If the system later required iterative retrieval, evidence grading, retries, human review, or multi-step planning, I would consider graph-based orchestration.

---

## Slide 6 — LLM Boundary: Interpretation, Not Financial Truth

### Step 1 — LLM produces `LLMIntent`

For:

> “What was Tesla’s Q2 2026 operating margin?”

Conceptually:

```python
LLMIntent(
    company="Tesla",
    question_type="numeric",
    operation="operating_margin",
    fiscal_year=2026,
    fiscal_quarter=2,
)
```

This means:

> “This is what the LLM thinks the user means.”

### Step 2 — deterministic `resolve_intent()`

```text
LLMIntent
    |
    v
resolve_intent()
    |
    v
FinancialQuery
```

The resolver checks and normalizes supported company, required metric/operation, year, quarter, period type, duration, clarification state, and unsupported questions.

### Trust boundary

> Structured output constrains syntax, but not semantic correctness.

Therefore the raw LLM output is never treated directly as an executable financial instruction.

---

## Slide 7 — FinancialQuery vs FactQuery vs FinancialFact

### `FinancialQuery`

**What does the validated user request require?**

Example:

```text
Tesla
Q2 2026
operation = operating_margin
```

### `FactQuery`

**What exact stored number do I need to retrieve?**

Operating margin requires two:

```text
FactQuery #1
Tesla + operating_income + Q2 2026

FactQuery #2
Tesla + total_revenue + Q2 2026
```

### `FinancialFact`

**What value did the filing actually report?**

```text
Operating income = 398 million USD
Revenue = 28,236 million USD
```

### Mental model

```text
FinancialQuery
= business instruction

FactQuery
= exact retrieval instruction

FinancialFact
= source-derived financial truth
```

---

## Slide 8 — Numeric Path: Exact Fact Lookup

Example:

> “What was Tesla’s Q1 2026 total revenue?”

### Runtime flow

```text
Streamlit
  |
workflow.py
  |
parse_query()
  |
LLMIntent
  |
resolve_intent()
  |
FinancialQuery
  |
execute_query()
  |
answer_lookup()
  |
FactQuery
  |
FactStore
  |
FinancialFact
  |
NumericAnswer
  |
Streamlit
```

### Exact retrieval guardrail

```python
if len(matches) == 0:
    raise FactNotFoundError()

if len(matches) > 1:
    raise AmbiguousFactError()

return matches[0]
```

### Why this matters

- **0 matches** → do not invent.
- **1 match** → safe to return.
- **>1 match** → do not arbitrarily choose.

> When retrieval is not uniquely determined, the system loses authority to answer.

---

## Slide 9 — Period-Aware Retrieval

### Critical SEC filing problem

Tesla Q2 2026 10-Q contains both:

| Period | Revenue |
|---|---:|
| Three months ended June 30, 2026 | 28,236 |
| Six months ended June 30, 2026 | 50,623 |

A system that only stores:

```text
Tesla + revenue + 2026
```

cannot distinguish them safely.

### My fact identity includes

- `period_type`
- `duration_months`
- `fiscal_quarter`
- `period_end_date`
- year
- metric

### Example

```text
Q2 2026 revenue
→ quarterly
→ 3 months
→ 28,236
```

versus:

```text
Six months ended June 30, 2026
→ year_to_date
→ 6 months
→ 50,623
```

**Key takeaway**

> Period semantics are part of the identity of a financial fact.

---

## Slide 10 — Deterministic Financial Calculations

Example:

> “What was Tesla’s Q2 2026 operating margin?”

### Runtime path after intent resolution

```text
FinancialQuery
      |
answer_engine.py
      |
operation == OPERATING_MARGIN
      |
      +--> FactQuery: operating_income
      |         |
      |         v
      |    FinancialFact = 398
      |
      +--> FactQuery: total_revenue
                |
                v
           FinancialFact = 28,236
                |
                v
           validation.py
                |
                v
          calculations.py
                |
                v
              1.41%
```

### Code pattern

```python
margin = (
    operating_income.reported_value
    / revenue.reported_value
) * Decimal("100")
```

### Why deterministic arithmetic?

Because once the exact source values are known, there is no reason to ask an LLM to perform arithmetic.

Advantages: reproducibility, lower hallucination risk, easier testing, and better auditability.

---

## Slide 11 — Validation Before Calculation

Retrieving two valid facts does **not** mean they are valid to combine.

### Example failure

```text
Operating income:
Q2 2026, 3 months

Revenue:
2026 YTD, 6 months
```

Both values may be individually correct, but:

```text
398 / 50,623
```

would be financially invalid as a Q2 operating margin.

### Validation checks

- same company,
- same period,
- same quarter where applicable,
- same duration,
- same units,
- same accounting basis,
- required metric identity.

### Design principle

> Retrieval establishes that a fact exists. Validation establishes that the facts can safely participate in the requested calculation.

---

## Slide 12 — Narrative RAG Path

Example:

> “What did management say about margin pressure?”

### Offline / initialization phase

```text
PDF
 |
extract text
 |
split into chunks
 |
~1,200 characters
 |
~200-character overlap
 |
embed chunks
 |
cache embeddings
```

### Runtime phase

```text
User Question
     |
LLM Intent Parser
     |
question_type = NARRATIVE
     |
embed question
     |
cosine similarity
     |
top-k chunks
     |
grounded LLM synthesis
     |
answer + source evidence
```

### Retrieval method

- Embeddings
- Cosine similarity
- No BM25 in the current prototype
- Cached document embeddings
- Only the question is newly embedded at runtime

### Why embeddings here?

Narrative retrieval is semantic rather than exact-table lookup.

---

## Slide 13 — Narrative Scope Policy

During early testing, searching multiple filings for underspecified narrative questions mixed management commentary from different reporting periods.

### Prototype policy

For narrative questions without an explicit period:

> Default to the latest filing rather than silently combine commentary across periods.

Current narrative corpus:

```text
tesla_2026_q2_10q.pdf
```

### Production evolution

Index all filings with metadata:

```text
company
filing_type
fiscal_year
quarter
filing_date
source_file
page
```

Then:

```text
temporal intent
    |
metadata filter
    |
semantic retrieval
    |
top-k evidence
```

> The current limitation is a documented prototype policy, not an architectural limitation.

---

## Slide 14 — State, Context, and Memory

### State

The structured information moving through the current workflow:

```text
User Question
→ LLMIntent
→ FinancialQuery
→ FactQuery
→ FinancialFact(s)
→ Answer
```

I do not use a formal LangGraph state object; state is passed explicitly through Python function arguments and return values.

### Context

What the LLM sees during each call.

**Intent parsing**

```text
system instructions
+
current user question
```

**Narrative synthesis**

```text
system grounding instructions
+
user question
+
top-k retrieved SEC passages
```

### Memory

No conversational long-term memory is persisted in the prototype.

Persistent application data is limited to:

- structured financial facts,
- cached document embeddings.

### Why not persist conversation memory?

The current use case is primarily stateless financial Q&A.

Persistent conversation memory could introduce unnecessary complexity, stale assumptions, context contamination, and cross-question leakage.

> I would add session memory only if multi-turn financial analysis became a product requirement.

---

## Slide 15 — Main Failure Modes and Guardrails

| Failure mode | Guardrail |
|---|---|
| Wrong intent classification | `LLMIntent` → deterministic `resolve_intent()` |
| Wrong metric / similar labels | normalized exact metric mapping |
| Quarterly vs YTD confusion | period type + duration + quarter + end date |
| Multiple matching facts | ambiguity error; never choose arbitrarily |
| Missing data | controlled not-found response |
| Wrong units / accounting basis | validation before calculation |
| Arithmetic error | Python `Decimal`, not LLM math |
| Narrative hallucination | answer only from retrieved evidence |
| Irrelevant narrative chunks | top-k semantic retrieval |
| Bad PDF extraction | multi-signal statement detection + benchmark |
| Unsupported question | explicit abstention path |

### Core trust philosophy

> The architecture is the primary guardrail—not just the prompt.

---

## Slide 16 — Evaluation

### Hand-verified golden set

10 representative questions covering:

- exact financial lookup,
- Q1 YoY revenue growth,
- Q2 operating margin,
- quarterly vs YTD separation,
- narrative retrieval,
- ambiguity,
- unsupported questions.

### Example checks

```text
Q2 2026 revenue
→ 28,236

Six-month 2026 revenue
→ 50,623

Q2 2026 operating margin
→ 1.41%

"profit"
→ clarification / ambiguity

"What day is today?"
→ unsupported
```

### Result

**10 / 10 passed**

### Important lesson from evaluation

The benchmark initially exposed semantic routing errors even though the LLM used structured output.

That reinforced:

> Structured output guarantees shape, not meaning.

### Evaluation philosophy

- Numeric questions: exact expected values and behavior.
- Narrative questions: expected source/concepts + qualitative review.
- Failure cases are part of the benchmark, not only successful cases.

---

## Slide 17 — Small Code Snippets That Capture the Architecture

### 1. Routing

```python
query = parse_query(question)

if query.question_type == QuestionType.NUMERIC:
    return execute_query(query, store)

if query.question_type == QuestionType.NARRATIVE:
    return answer_narrative(question, narrative_chunks)
```

### 2. Exact retrieval safety

```python
if len(matches) == 0:
    raise FactNotFoundError()

if len(matches) > 1:
    raise AmbiguousFactError()

return matches[0]
```

### 3. Deterministic calculation

```python
margin = (
    operating_income.reported_value
    / revenue.reported_value
) * Decimal("100")
```

### Why these snippets matter

They capture the core design in three lines of thought:

> route by task type → retrieve exact facts → calculate deterministically.

---

## Slide 18 — How I Would Deploy It for Clients

### Separate offline ingestion from online serving

```text
SEC PDFs
   |
Offline Ingestion Workers
   |
   +--> Structured Facts --> SQL / analytical database
   |
   +--> Narrative Chunks --> Embeddings --> Vector index
```

### Online query path

```text
Client / Web UI
      |
API Gateway / Load Balancer
      |
Financial QA API
      |
Intent / Workflow Router
   /                    \
Numeric                  Narrative
 |                          |
SQL facts                Vector search
 |                          |
Validation               Grounded LLM
 |                          |
Calculation              Answer
   \                      /
        Grounded Response
```

### Production steps

- replace in-memory FactStore with persistent indexed storage,
- replace local JSON embedding cache with vector storage,
- expose a versioned API,
- containerize,
- deploy behind authentication and a load balancer,
- move ingestion to asynchronous workers,
- add retries/timeouts,
- add observability,
- add CI/CD and regression evaluation,
- add audit logs and security controls.

### Key production principle

> Keep the online serving path lightweight; expensive document processing belongs in asynchronous preprocessing.

---

## Slide 19 — Scaling to Tens of Thousands of Filings

### What breaks first in the prototype?

- in-memory fact storage,
- brute-force vector comparisons,
- local JSON cache,
- synchronous document preparation,
- hardcoded company/metric support.

### Production evolution

**Structured path**

```text
financial facts
→ indexed relational / analytical store
→ indexes on company, metric, filing, year, period
```

**Narrative path**

```text
chunks
→ vector index
→ metadata filtering
→ candidate retrieval
→ optional reranking
```

### Additional improvements

- section-aware/layout-aware chunking,
- hybrid lexical + semantic retrieval,
- reranking,
- extraction confidence,
- reconciliation across filing versions,
- amended filing handling,
- richer GAAP/non-GAAP representation.

---

## Slide 20 — Why This Is Agentic, but Not Over-Engineered

I describe the system as:

> **A lightweight agentic SEC filing intelligence workflow with deterministic financial reasoning and grounded narrative retrieval.**

### Agentic behavior

The system:

- interprets a task,
- classifies the request,
- routes to specialized capabilities,
- retrieves evidence,
- performs validation,
- executes calculations or synthesis,
- abstains when necessary.

### Why no LangGraph?

Current workflow:

```text
small number of explicit branches
+
no iterative planning
+
no long-running state
```

Therefore plain Python is sufficient.

### When I would add graph orchestration

- iterative retrieval,
- evidence grading,
- retries,
- multiple tools,
- human review,
- multi-step planning,
- checkpointing.

> Framework complexity should be earned by workflow complexity.

---

## Slide 21 — Limitations and What I Would Improve Next

### Current limitations

- Tesla only
- selected income-statement metrics
- latest-filing narrative policy
- no balance-sheet/cash-flow structured extraction
- small evaluation set
- simple fixed-size chunking
- no retrieval reranker
- no persistent production storage
- no conversational memory

### If I had another day

- add gross margin,
- add balance-sheet extraction,
- add period-aware narrative metadata filtering,
- enlarge the evaluation set,
- add retrieval-quality measurements.

### If I had another week

- multi-company ingestion,
- persistent SQL + vector stores,
- layout-aware parsing,
- hybrid retrieval and reranking,
- observability,
- confidence/reconciliation layer,
- deployment-ready API.

---

## Slide 22 — Closing Takeaway

### What I optimized for

Not maximum feature count.

I optimized for:

- correctness,
- traceability,
- explicit failure behavior,
- explainable architecture,
- deterministic reasoning where possible,
- appropriate use of LLMs.

### Final message

> **Financial QA should not ask one probabilistic model to do everything.**

> **Use the LLM to interpret language and synthesize evidence. Use structured retrieval, validation, and deterministic computation wherever exactness is available.**

### Why this matters

That separation makes the system easier to verify, easier to evaluate, easier to debug, safer to scale, and more trustworthy for enterprise users.

---

# Appendix — Demo Questions

### Exact fact lookup

> What was Tesla's Q1 2026 total revenue?

### Calculated question

> What was Tesla's Q2 2026 operating margin?

### Period-aware retrieval

> What was Tesla's Q2 2026 revenue?

> What was Tesla's revenue for the six months ended June 30, 2026?

### Narrative question

> What did management say about margin pressure?

### Ambiguity

> What was Tesla's profit?

### Unsupported

> What is the day today?

---

# Appendix — 60-Second Architecture Explanation

> I built the system around the idea that financial questions do not all require the same retrieval strategy. A lightweight LLM parser converts natural language into structured intent, but that intent is validated deterministically before execution. Numeric questions go to a structured FactStore containing exact values extracted from filing tables, with period, unit, accounting-basis, and provenance metadata. Calculations such as YoY growth and operating margin are performed with deterministic Python rather than the LLM. Narrative questions use a separate RAG path with cached document embeddings, cosine-similarity retrieval, and grounded LLM synthesis. The system explicitly abstains on missing or ambiguous facts and returns source evidence so users can verify the answer. I intentionally scoped implementation to Tesla and selected metrics so I could demonstrate reliability deeply, while keeping the architecture extensible to additional statements, companies, and production storage.

---

# Appendix — Core Interview Defense

## Why not embeddings for exact numbers?

Embeddings preserve semantic similarity, not exact numerical identity, table position, or fine-grained financial labels. Numeric retrieval therefore uses structured facts.

## Why use an LLM at all?

Natural language is variable and ambiguous. The LLM is useful for interpreting intent, but deterministic code decides whether that interpretation is safe to execute.

## Why no conversational memory?

The current task is primarily stateless financial Q&A. Persisting conversation history would add complexity and potential contamination without improving the core use case.

## Why no LangGraph?

The workflow is small and explicit. I would introduce graph orchestration only when retries, multi-step planning, evidence grading, human review, or persistent workflow state justify it.

## What is the strongest guardrail?

The architecture itself: probabilistic components are used only where ambiguity exists; exact financial retrieval, validation, and arithmetic are deterministic.

## What does 10/10 mean?

It means the prototype passes the hand-verified benchmark I defined for the implemented scope. It does not mean the system is production-complete; the benchmark should expand significantly before deployment.
