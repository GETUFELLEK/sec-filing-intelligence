from __future__ import annotations

import json
from pathlib import Path

from app.fact_store import load_sample_fact_store
from app.llm_query_parser import (
    QueryClarificationRequired,
    UnsupportedQueryError,
)
from app.narrative_retrieval import prepare_narrative_chunks
from app.workflow import answer_question


GOLDEN_PATH = Path(
    "eval/golden_questions.json"
)

NARRATIVE_PDFS = [
    Path(
        "data/sample_filings/"
        "tesla_2026_q2_10q.pdf"
    )
]

CACHE_PATH = Path(
    "data/cache/"
    "tesla_q2_2026_narrative.json"
)


def load_golden_questions() -> list[dict]:
    return json.loads(
        GOLDEN_PATH.read_text(
            encoding="utf-8"
        )
    )


def evaluate_numeric(
    case: dict,
    result,
) -> tuple[bool, str]:
    """
    Evaluate deterministic numeric answers.
    """

    actual_status = result.status.value

    if actual_status != case["expected_status"]:
        return (
            False,
            (
                f"expected status="
                f"{case['expected_status']}, "
                f"got {actual_status}"
            ),
        )

    expected_value = case.get(
        "expected_value"
    )

    if expected_value is not None:
        actual_value = str(
            result.result_value
        )

        if actual_value != expected_value:
            return (
                False,
                (
                    f"expected value="
                    f"{expected_value}, "
                    f"got {actual_value}"
                ),
            )

    expected_unit = case.get(
        "expected_unit"
    )

    if (
        expected_unit is not None
        and result.result_unit != expected_unit
    ):
        return (
            False,
            (
                f"expected unit="
                f"{expected_unit}, "
                f"got {result.result_unit}"
            ),
        )

    return True, "exact match"


def evaluate_narrative(
    case: dict,
    result: dict,
) -> tuple[bool, str]:
    """
    Lightweight evaluation for narrative RAG.

    We verify that an answer was generated and that
    retrieval includes the expected filing. Narrative
    quality is still reviewed manually.
    """

    answer = result.get(
        "answer",
        ""
    )

    sources = result.get(
        "sources",
        []
    )

    if not answer.strip():
        return False, "empty narrative answer"

    expected_source = case.get(
        "expected_source"
    )

    source_files = {
        source["source_file"]
        for source in sources
    }

    if (
        expected_source
        and expected_source not in source_files
    ):
        return (
            False,
            (
                f"expected source "
                f"{expected_source} "
                f"was not retrieved"
            ),
        )

    keywords = case.get(
        "expected_keywords",
        []
    )

    answer_lower = answer.lower()

    matched = [
        keyword
        for keyword in keywords
        if keyword.lower() in answer_lower
    ]

    # Require at least two expected concepts when
    # keywords are provided.
    if keywords and len(matched) < 2:
        return (
            False,
            (
                "insufficient expected concepts; "
                f"matched={matched}"
            ),
        )

    return (
        True,
        (
            f"grounded narrative; "
            f"matched keywords={matched}"
        ),
    )


def main() -> None:
    cases = load_golden_questions()

    print("Preparing evaluation system...")

    # Build structured facts once.
    store = load_sample_fact_store()

    # Load cached narrative embeddings.
    narrative_chunks = prepare_narrative_chunks(
        NARRATIVE_PDFS,
        CACHE_PATH,
    )

    print(
        f"\nRunning {len(cases)} "
        f"golden questions...\n"
    )

    passed = 0

    for case in cases:
        case_id = case["id"]
        category = case["category"]
        question = case["question"]
        expected_status = case[
            "expected_status"
        ]

        try:
            result = answer_question(
                question,
                store,
                narrative_chunks,
            )

            if isinstance(result, dict):
                actual_status = "answered"

                if (
                    expected_status
                    != actual_status
                ):
                    success = False
                    detail = (
                        f"expected status="
                        f"{expected_status}, "
                        f"got {actual_status}"
                    )
                else:
                    success, detail = (
                        evaluate_narrative(
                            case,
                            result,
                        )
                    )

            else:
                success, detail = (
                    evaluate_numeric(
                        case,
                        result,
                    )
                )

        except QueryClarificationRequired as exc:
            success = (
                expected_status
                == "ambiguous"
            )

            detail = (
                f"clarification required: {exc}"
            )

        except UnsupportedQueryError as exc:
            success = (
                expected_status
                == "unsupported"
            )

            detail = (
                f"unsupported: {exc}"
            )

        except Exception as exc:
            success = False
            detail = (
                f"unexpected error: {exc}"
            )

        label = (
            "PASS"
            if success
            else "FAIL"
        )

        if success:
            passed += 1

        print(
            f"{label:<4} "
            f"{case_id:<4} "
            f"{category:<20} "
            f"{detail}"
        )

    total = len(cases)

    print("\n" + "=" * 80)

    print(
        f"RESULT: {passed}/{total} passed"
    )

    print("=" * 80)


if __name__ == "__main__":
    main()