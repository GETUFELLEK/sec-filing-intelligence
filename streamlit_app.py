from pathlib import Path

import streamlit as st

from app.fact_store import load_sample_fact_store
from app.llm_query_parser import (
    QueryClarificationRequired,
    UnsupportedQueryError,
)
from app.narrative_retrieval import prepare_narrative_chunks
from app.workflow import answer_question


st.set_page_config(
    page_title="SEC Filing Intelligence",
    page_icon="📊",
    layout="centered",
)


@st.cache_resource
def prepare_system():
    """
    Load structured financial facts and cached
    narrative embeddings once for the demo.
    """

    store = load_sample_fact_store()

    pdf_paths = [
        Path(
            "data/sample_filings/"
            "tesla_2026_q2_10q.pdf"
        )
    ]

    cache_path = Path(
        "data/cache/"
        "tesla_q2_2026_narrative.json"
    )

    narrative_chunks = prepare_narrative_chunks(
        pdf_paths,
        cache_path,
    )

    return store, narrative_chunks


def show_numeric_answer(result):
    st.subheader("Answer")

    st.write(result.answer_text)

    if result.calculation:
        st.markdown("**Calculation**")
        st.code(result.calculation)

    if result.evidence:
        st.markdown("**Evidence**")

        for evidence in result.evidence:
            with st.expander(
                f"{evidence.source_file} — "
                f"page {evidence.page_number}"
            ):
                st.write(
                    f"**Statement:** "
                    f"{evidence.statement_name}"
                )

                if evidence.row_label:
                    st.write(
                        f"**Row:** "
                        f"{evidence.row_label}"
                    )

                if evidence.column_label:
                    st.write(
                        f"**Period:** "
                        f"{evidence.column_label}"
                    )

                if evidence.value_raw:
                    st.write(
                        f"**Reported value:** "
                        f"{evidence.value_raw} "
                        f"{evidence.currency} "
                        f"{evidence.scale}"
                    )


def show_narrative_answer(result):
    st.subheader("Answer")

    st.write(result["answer"])

    st.markdown("**Retrieved Evidence**")

    for source in result["sources"]:
        st.write(
            f"• {source['source_file']} "
            f"— page {source['page_number']}"
        )


store, narrative_chunks = prepare_system()


st.title("SEC Filing Intelligence")

st.caption(
    "Grounded financial Q&A over SEC filing PDFs"
)

st.info(
    "Numeric questions use structured financial facts "
    "and deterministic calculations. Narrative questions "
    "use semantic retrieval and grounded LLM synthesis."
)


question = st.text_input(
    "Ask a question",
    placeholder=(
        "Example: What was Tesla's Q2 2026 operating margin?"
    ),
)


if st.button(
    "Ask",
    type="primary",
    use_container_width=True,
):
    if not question.strip():
        st.warning(
            "Please enter a question."
        )

    else:
        try:
            with st.spinner(
                "Analyzing SEC filings..."
            ):
                result = answer_question(
                    question,
                    store,
                    narrative_chunks,
                )

            if hasattr(
                result,
                "model_dump",
            ):
                show_numeric_answer(
                    result
                )

            else:
                show_narrative_answer(
                    result
                )

        except QueryClarificationRequired as exc:
            st.warning(
                f"Clarification required: {exc}"
            )

        except UnsupportedQueryError as exc:
            st.warning(
                f"Unsupported query: {exc}"
            )

        except Exception as exc:
            st.error(
                f"Unable to answer safely: {exc}"
            )


st.divider()

st.markdown("**Try these questions:**")

st.code(
    "What was Tesla's net income in 2025?\n"
    "What was Tesla's Q1 2026 revenue growth year over year?\n"
    "What was Tesla's Q2 2026 operating margin?\n"
    "What did management say about margin pressure?"
)