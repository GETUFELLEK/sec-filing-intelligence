from __future__ import annotations
import json
import os
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pdfplumber
from openai import OpenAI


EMBEDDING_MODEL = os.getenv(
    "OPENAI_EMBEDDING_MODEL",
    "text-embedding-3-small",
)


@dataclass
class NarrativeChunk:
    text: str
    source_file: str
    page_number: int
    embedding: list[float] | None = None


def extract_narrative_chunks(
    pdf_paths: list[Path],
    min_chars: int = 200,
) -> list[NarrativeChunk]:
    """
    Extract small narrative chunks from PDF pages while preserving
    source-file and page-number provenance.
    """

    chunks: list[NarrativeChunk] = []

    for pdf_path in pdf_paths:
        with pdfplumber.open(pdf_path) as pdf:

            for page_number, page in enumerate(
                pdf.pages,
                start=1,
            ):
                # Extract text from the page.
                text = page.extract_text() or ""

                # Normalize whitespace.
                text = " ".join(text.split())

                # Ignore pages with very little useful text.
                if len(text) < min_chars:
                    continue

                # Split the page into smaller overlapping chunks.
                for chunk_text in split_text(text):

                    # Ignore tiny leftover chunks.
                    if len(chunk_text) < min_chars:
                        continue

                    chunks.append(
                        NarrativeChunk(
                            text=chunk_text,
                            source_file=pdf_path.name,
                            page_number=page_number,
                        )
                    )

    return chunks
def prepare_narrative_chunks(
    pdf_paths: list[Path],
    cache_path: Path,
) -> list[NarrativeChunk]:
    """
    Load cached embeddings when available.
    Otherwise extract, embed, and cache them.
    """

    if cache_path.exists():
        print(
            f"Loading cached narrative embeddings "
            f"from {cache_path}"
        )

        return load_chunks(
            cache_path
        )

    print("Extracting narrative chunks...")

    chunks = extract_narrative_chunks(
        pdf_paths
    )

    print(
        f"Extracted {len(chunks)} chunks."
    )

    print("Embedding chunks...")

    embed_chunks(
        chunks
    )

    save_chunks(
        chunks,
        cache_path,
    )

    print(
        f"Saved narrative cache to "
        f"{cache_path}"
    )

    return chunks

def embed_chunks(
    chunks: list[NarrativeChunk],
    batch_size: int = 50,
) -> None:
    client = OpenAI()

    for start in range(0, len(chunks), batch_size):
        batch = chunks[start:start + batch_size]

        texts = [
            chunk.text
            for chunk in batch
        ]

        response = client.embeddings.create(
            model=EMBEDDING_MODEL,
            input=texts,
        )

        for chunk, item in zip(
            batch,
            response.data,
        ):
            chunk.embedding = item.embedding

        print(
            f"Embedded "
            f"{min(start + batch_size, len(chunks))}"
            f"/{len(chunks)} chunks"
        )
        
def cosine_similarity(
    a: list[float],
    b: list[float],
) -> float:
    a_vec = np.array(a)
    b_vec = np.array(b)

    denominator = (
        np.linalg.norm(a_vec)
        * np.linalg.norm(b_vec)
    )

    if denominator == 0:
        return 0.0

    return float(
        np.dot(a_vec, b_vec)
        / denominator
    )
def split_text(
    text: str,
    chunk_size: int = 1200,
    overlap: int = 200,
) -> list[str]:
    """
    Split text into small overlapping chunks.

    V1 uses simple word-based chunking rather than
    introducing a separate chunking framework.
    """
    words = text.split()

    chunks = []
    current = []
    current_length = 0

    for word in words:
        current.append(word)
        current_length += len(word) + 1

        if current_length >= chunk_size:
            chunks.append(" ".join(current))

            # Keep a small overlap from the end.
            overlap_words = []
            overlap_length = 0

            for previous_word in reversed(current):
                overlap_words.insert(0, previous_word)
                overlap_length += len(previous_word) + 1

                if overlap_length >= overlap:
                    break

            current = overlap_words
            current_length = overlap_length

    if current:
        chunks.append(" ".join(current))

    return chunks       

def retrieve_narrative(
    question: str,
    chunks: list[NarrativeChunk],
    top_k: int = 3,
) -> list[NarrativeChunk]:
    client = OpenAI()

    response = client.embeddings.create(
        model=EMBEDDING_MODEL,
        input=question,
    )

    query_embedding = response.data[0].embedding

    scored = []

    for chunk in chunks:
        if chunk.embedding is None:
            continue

        score = cosine_similarity(
            query_embedding,
            chunk.embedding,
        )

        scored.append(
            (score, chunk)
        )

    scored.sort(
        key=lambda item: item[0],
        reverse=True,
    )

    return [
        chunk
        for _, chunk in scored[:top_k]
    ]
def answer_narrative(
    question: str,
    chunks: list[NarrativeChunk],
    top_k: int = 4,
) -> dict:
    """
    Retrieve relevant narrative passages and generate
    a grounded answer from those passages only.
    """

    retrieved = retrieve_narrative(
        question,
        chunks,
        top_k=top_k,
    )

    context_parts = []

    for i, chunk in enumerate(
        retrieved,
        start=1,
    ):
        context_parts.append(
            f"[{i}] "
            f"Source: {chunk.source_file}, "
            f"page {chunk.page_number}\n"
            f"{chunk.text}"
        )

    context = "\n\n".join(context_parts)

    client = OpenAI()

    response = client.responses.create(
        model=os.getenv(
            "OPENAI_MODEL",
            "gpt-4.1-mini",
        ),
        input=[
            {
                "role": "system",
                "content": (
                    "Answer the user's question using only "
                    "the provided SEC filing passages. "
                    "Ignore passages that are not directly "
                    "relevant. Do not invent facts or numbers. "
                    "If the passages are insufficient, say so. "
                    "Cite supporting passages using [1], [2], "
                    "etc."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Question:\n{question}\n\n"
                    f"SEC filing passages:\n{context}"
                ),
            },
        ],
    )

    return {
        "answer": response.output_text,
        "sources": [
            {
                "source_file": chunk.source_file,
                "page_number": chunk.page_number,
            }
            for chunk in retrieved
        ],
    }  
      
if __name__ == "__main__":
    pdf_paths = [
        # Path(
        #     "data/sample_filings/"
        #     "tesla_2025_10k.pdf"
        # ),
        # Path(
        #     "data/sample_filings/"
        #     "tesla_2026_q1_10q.pdf"
        # ),
        Path(
            "data/sample_filings/"
            "tesla_2026_q2_10q.pdf"
        ),
    ]

    print("Extracting narrative chunks...")

    chunks = extract_narrative_chunks(
        pdf_paths
    )

    print(
        f"Extracted {len(chunks)} chunks."
    )

    print("Embedding chunks...")

    embed_chunks(chunks)

    print("Embeddings complete.")

    question = (
        "What did management say "
        "about margin pressure?"
    )

    print(
        f"\nQuestion: {question}"
    )

    results = retrieve_narrative(
        question,
        chunks,
        top_k=3,
    )

    for i, chunk in enumerate(
        results,
        start=1,
    ):
        print("\n" + "=" * 80)
        print(
            f"RESULT {i}: "
            f"{chunk.source_file}, "
            f"page {chunk.page_number}"
        )
        print("=" * 80)

        print(
            chunk.text[:1500]
    
    ) 
           
    print(f"Extracted {len(chunks)} chunks.")

    # for chunk in chunks[:5]:
    #  print(
    #     chunk.source_file,
    #     chunk.page_number,
    #     len(chunk.text),
    # )
    
    print("\n" + "=" * 80)
    print("GROUNDED NARRATIVE ANSWER")
    print("=" * 80)

    answer = answer_narrative(
        question,
        chunks,
    )

    print(answer["answer"])

    print("\nSOURCES")

    for source in answer["sources"]:
        print(f"- {source['source_file']}, page {source['page_number']}")
def save_chunks(
    chunks: list[NarrativeChunk],
    cache_path: Path,
) -> None:
    """
    Save narrative chunks and embeddings locally.
    """

    cache_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    data = [
        {
            "text": chunk.text,
            "source_file": chunk.source_file,
            "page_number": chunk.page_number,
            "embedding": chunk.embedding,
        }
        for chunk in chunks
    ]

    cache_path.write_text(
        json.dumps(data),
        encoding="utf-8",
    )


def load_chunks(
    cache_path: Path,
) -> list[NarrativeChunk]:
    """
    Load previously embedded narrative chunks.
    """

    data = json.loads(
        cache_path.read_text(
            encoding="utf-8"
        )
    )

    return [
        NarrativeChunk(
            text=item["text"],
            source_file=item["source_file"],
            page_number=item["page_number"],
            embedding=item["embedding"],
        )
        for item in data
    ]        