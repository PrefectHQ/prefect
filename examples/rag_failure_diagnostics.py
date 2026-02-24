# ---
# title: Debugging RAG flows with a failure mode checklist
# description: Use Prefect to instrument each stage of a simple RAG pipeline and quickly localize failures.
# icon: database
# dependencies: ["prefect"]
# keywords: ["rag", "llm", "observability", "debugging"]
# draft: false
# ---
#
# This example shows how to use Prefect to debug a Retrieval Augmented Generation (RAG) flow.
#
# The goal is not to build a full RAG system.
# Instead, we focus on the kind of instrumentation that helps you answer questions like:
#
# - Did we ingest the right documents?
# - Are we chunking them in a useful way?
# - Is the retriever actually surfacing the chunks that matter?
# - Did the final answer stay grounded in the retrieved context?
#
# The pattern you see here can be adapted to your own internal "failure mode checklist"
# whether you track 5, 12, or 16 distinct failure patterns in production.

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple
from prefect import flow, get_run_logger, task


# ## Simple domain model
#
# We keep the domain model minimal and self contained.
# Everything runs without external services or LLM APIs.


@dataclass
class Document:
    doc_id: str
    text: str


@dataclass
class RetrievedChunk:
    doc_id: str
    text: str
    score: float


@dataclass
class RagRunStats:
    query: str
    total_docs: int
    total_chunks: int
    retrieved_ids: List[str]
    missing_keywords: List[str]
    answer_contains_forbidden: bool


# ## Stage 1 – ingest a tiny FAQ knowledge base
#
# In a real system this would pull from a database, object storage, or a document loader.
# Here we hard code a minimal example around billing and payment methods.


@task
def ingest_documents() -> List[Document]:
    logger = get_run_logger()

    docs = [
        Document(
            doc_id="faq-1",
            text=(
                "We currently accept major credit cards and PayPal for subscriptions. "
                "All payments are processed in USD."
            ),
        ),
        Document(
            doc_id="faq-2",
            text=(
                "You can update or cancel your subscription at any time from your account "
                "billing settings. Changes apply to the next billing cycle."
            ),
        ),
        Document(
            doc_id="faq-3",
            text=(
                "We do not support cryptocurrency payments. "
                "Bitcoin and other cryptocurrencies are not accepted."
            ),
        ),
    ]

    logger.info("Ingested %d documents into the RAG knowledge base.", len(docs))
    return docs


# ## Stage 2 – naive chunking
#
# This keeps chunking deliberately simple so that the instrumentation is easy to understand.
# Real projects often have much more complex segmentation logic.


@task
def chunk_documents(docs: List[Document], max_chars: int = 160) -> List[Document]:
    logger = get_run_logger()
    chunks: List[Document] = []

    for doc in docs:
        text = doc.text.strip()
        if len(text) <= max_chars:
            chunks.append(doc)
            continue

        # Simple fixed width splitting for demonstration.
        start = 0
        index = 0
        while start < len(text):
            end = min(start + max_chars, len(text))
            chunk_text = text[start:end].strip()
            chunk_id = f"{doc.doc_id}-chunk-{index}"
            chunks.append(Document(doc_id=chunk_id, text=chunk_text))
            start = end
            index += 1

    avg_len = sum(len(c.text) for c in chunks) / len(chunks) if chunks else 0
    logger.info(
        "Created %d chunks from %d docs (avg length %.1f chars).",
        len(chunks),
        len(docs),
        avg_len,
    )
    return chunks


# ## Stage 3 – toy keyword based retrieval
#
# We implement a very small scoring function.
# This keeps the example runnable without extra dependencies while still
# letting us talk about retrieval quality and coverage.


def _tokenize(text: str) -> List[str]:
    return [t.lower() for t in text.replace("?", " ").replace(",", " ").split() if t]


def _score_chunk(query_tokens: List[str], chunk: Document) -> float:
    chunk_tokens = _tokenize(chunk.text)
    overlap = set(query_tokens) & set(chunk_tokens)
    return float(len(overlap))


@task
def retrieve_relevant_chunks(
    query: str,
    chunks: List[Document],
    top_k: int = 3,
) -> Tuple[List[RetrievedChunk], Dict[str, float]]:
    logger = get_run_logger()

    query_tokens = _tokenize(query)
    logger.info("Query tokens: %s", query_tokens)

    scored: List[RetrievedChunk] = []
    for c in chunks:
        score = _score_chunk(query_tokens, c)
        if score > 0:
            scored.append(RetrievedChunk(doc_id=c.doc_id, text=c.text, score=score))

    scored.sort(key=lambda c: c.score, reverse=True)
    top_chunks = scored[:top_k]

    logger.info(
        "Retrieved %d chunks with non zero score (top_k = %d).",
        len(scored),
        top_k,
    )
    logger.info(
        "Top chunk ids with scores: %s",
        [(c.doc_id, c.score) for c in top_chunks],
    )

    # Simple coverage metric: how many unique query tokens appeared
    # in the retrieved chunks at least once.
    coverage_tokens = set()
    for c in top_chunks:
        coverage_tokens.update(_tokenize(c.text))

    coverage = len(set(query_tokens) & coverage_tokens) / max(len(query_tokens), 1)
    logger.info("Approximate keyword coverage in top chunks: %.2f", coverage)

    metrics = {
        "coverage": coverage,
        "retrieved_count": float(len(scored)),
        "top_k": float(top_k),
    }
    return top_chunks, metrics


# ## Stage 4 – a deliberately wrong "LLM answer"
#
# In a real pipeline this would call your model through an LLM block or custom task.
# Here we simulate a failure pattern that many teams have seen in production:
# the answer confidently contradicts what the context says.


@task
def llm_answer(query: str, context_chunks: List[RetrievedChunk]) -> str:
    logger = get_run_logger()

    logger.info("Context passed to the model:")
    for c in context_chunks:
        logger.info("- [%s] %s", c.doc_id, c.text)

    # Intentionally wrong answer.
    # The context clearly says we do not accept Bitcoin, but the answer claims we do.
    answer = (
        "Yes, you can pay your subscription with Bitcoin or other cryptocurrencies. "
        "We support flexible payment options for your convenience."
    )

    logger.info("Model answer (intentionally incorrect for this example): %s", answer)
    return answer


# ## Stage 5 – high level diagnostics
#
# This is where we connect Prefect observability to a failure mode checklist.
#
# In your own system you might maintain a larger internal catalog of failure patterns,
# for example:
#
# - Retrieval hallucination or grounding drift
# - Chunking or segmentation bugs
# - Embedding or retriever mismatch with true relevance
# - Index skew or stale data issues
#
# Here we show how a flow level diagnostic task can emit signals that map
# concrete incidents to those patterns.


@task
def summarize_diagnostics(
    query: str,
    answer: str,
    retrieved: List[RetrievedChunk],
    retrieval_metrics: Dict[str, float],
) -> RagRunStats:
    logger = get_run_logger()

    query_tokens = set(_tokenize(query))
    answer_tokens = set(_tokenize(answer))

    missing_keywords: List[str] = []
    for keyword in ["bitcoin", "crypto", "cryptocurrency"]:
        if keyword in query_tokens and keyword not in answer_tokens:
            missing_keywords.append(keyword)

    # In this example we expect the opposite:
    # the answer introduces "bitcoin" even though the policy forbids it.
    answer_contains_forbidden = "bitcoin" in answer_tokens

    retrieved_ids = [c.doc_id for c in retrieved]

    logger.info("Diagnostics summary:")
    logger.info("  retrieved_ids = %s", retrieved_ids)
    logger.info(
        "  retrieval_coverage = %.2f",
        retrieval_metrics.get("coverage", 0.0),
    )
    logger.info("  missing_keywords_in_answer = %s", missing_keywords)
    logger.info("  answer_contains_forbidden = %s", answer_contains_forbidden)

    # Map observations to higher level failure patterns.
    logger.info("Possible failure patterns to investigate:")

    if answer_contains_forbidden:
        logger.info(
            "- Retrieval hallucination or grounding drift: "
            "answer introduces Bitcoin support that conflicts with the FAQ.",
        )

    if retrieval_metrics.get("coverage", 0.0) < 0.5:
        logger.info(
            "- Retriever coverage issue: query keywords are poorly represented in top chunks.",
        )

    if not retrieved_ids:
        logger.info(
            "- Retriever recall failure: no chunks scored as relevant for this query.",
        )

    stats = RagRunStats(
        query=query,
        total_docs=0,  # can be filled if needed
        total_chunks=len(retrieved),
        retrieved_ids=retrieved_ids,
        missing_keywords=missing_keywords,
        answer_contains_forbidden=answer_contains_forbidden,
    )

    return stats


# ## The flow – wire everything together
#
# You can run this file directly:
#
#     python examples/rag_failure_diagnostics.py
#
# Then open the Prefect UI to inspect logs and states for each task run.


@flow
def rag_failure_diagnostics_flow(
    query: str = "Can I pay my subscription with Bitcoin?",
) -> RagRunStats:
    docs = ingest_documents()
    chunks = chunk_documents(docs)
    retrieved, metrics = retrieve_relevant_chunks(
        query=query,
        chunks=chunks,
        top_k=3,
    )
    answer = llm_answer(query=query, context_chunks=retrieved)
    stats = summarize_diagnostics(
        query=query,
        answer=answer,
        retrieved=retrieved,
        retrieval_metrics=metrics,
    )
    return stats


if __name__ == "__main__":
    rag_failure_diagnostics_flow()
