from __future__ import annotations

from pathlib import Path

from app.answer_engine import execute_query
from app.fact_store import load_sample_fact_store
from app.llm_query_parser import parse_query
from app.fact_store import (
    FactStore,
    load_sample_fact_store,
)
from app.narrative_retrieval import (
    NarrativeChunk,
    answer_narrative,
    prepare_narrative_chunks,
)
from app.schemas import QuestionType


def answer_question(
    question: str,
    store: FactStore,
    narrative_chunks: list[NarrativeChunk],
):
    """
    Unified SEC filing question-answering workflow.
    """

    query = parse_query(
        question
    )

    if query.question_type == QuestionType.NUMERIC:
        return execute_query(
            query,
            store,
        )

    if query.question_type == QuestionType.NARRATIVE:
        return answer_narrative(
            question,
            narrative_chunks,
        )

    raise ValueError(
        f"Unsupported question type: "
        f"{query.question_type}"
    )
if __name__ == "__main__":
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

    print("Preparing financial facts...")

    store = load_sample_fact_store()

    print("Preparing narrative retrieval...")

    narrative_chunks = prepare_narrative_chunks(
        pdf_paths,
        cache_path,
    )

    questions = [
        (
            "What was Tesla's Q1 2026 "
            "revenue growth year over year?"
        ),
        (
            "What was Tesla's Q2 2026 "
            "operating margin?"
        ),
        (
            "What did management say "
            "about margin pressure?"
        ),
    ]

    for question in questions:
        print("\n" + "=" * 80)
        print("QUESTION")
        print(question)

        result = answer_question(
            question,
            store,
            narrative_chunks,
        )

        print("\nANSWER")

        if hasattr(
            result,
            "model_dump_json",
        ):
            print(
                result.model_dump_json(
                    indent=2
                )
            )

        else:
            print(
                result["answer"]
            )

            print(
                "\nRETRIEVED EVIDENCE"
            )

            for source in result["sources"]:
                print(
                    f"- "
                    f"{source['source_file']}, "
                    f"page "
                    f"{source['page_number']}"
                )