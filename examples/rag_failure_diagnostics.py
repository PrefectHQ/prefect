# ---
# title: Instrumenting a simple RAG flow for failure diagnosis
# description: Use Prefect tasks, logs, and a simple routing step to inspect retrieval quality before a downstream answer step.
# icon: database
# dependencies: ["prefect"]
# keywords: ["rag", "llm", "observability", "debugging", "orchestration"]
# draft: false
# ---
#
# This example shows how to use Prefect to inspect a simple RAG pipeline and
# route common failure signals before they become downstream incidents.
#
# The goal is not to build a production RAG stack.
# Instead, we focus on the workflow patterns that help answer questions like:
#
# - Did we ingest the right documents?
# - Are we chunking them in a useful way?
# - Is the retriever surfacing the chunks that matter?
# - Does the generated answer stay grounded in retrieved context?
# - If diagnostics fail, should the flow stop early or retry with a safer path?
#
# The pattern can be adapted to your own internal failure mode checklist,
# whether you track 5, 12, or 16 recurring failure classes.

from __future__ import annotations

from dataclasses import dataclass

from prefect import flow, get_run_logger, task


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
    retrieved_ids: list[str]
    retrieval_coverage: float
    missing_keywords: list[str]
    answer_contains_forbidden: bool


@task
def ingest_documents() -> list[Document]:
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


@task
def chunk_documents(docs: list[Document], max_chars: int = 160) -> list[Document]:
    logger = get_run_logger()
    chunks: list[Document] = []

    for doc in docs:
        text = doc.text.strip()
        if len(text) <= max_chars:
            chunks.append(doc)
            continue

        start = 0
        index = 0
        while start < len(text):
            end = min(start + max_chars, len(text))
            chunk_text = text[start:end].strip()
            chunk_id = f"{doc.doc_id}-chunk-{index}"
            chunks.append(Document(doc_id=chunk_id, text=chunk_text))
            start = end
            index += 1

    avg_len = sum(len(chunk.text) for chunk in chunks) / len(chunks) if chunks else 0.0
    logger.info(
        "Created %d chunks from %d docs (avg length %.1f chars).",
        len(chunks),
        len(docs),
        avg_len,
    )
    return chunks


def _tokenize(text: str) -> list[str]:
    normalized = text.lower()
    for char in ("?", ".", ",", ":", ";"):
        normalized = normalized.replace(char, " ")
    return [token for token in normalized.split() if token]


def _score_chunk(query_tokens: list[str], chunk: Document) -> float:
    chunk_tokens = _tokenize(chunk.text)
    overlap = set(query_tokens) & set(chunk_tokens)
    return float(len(overlap))


@task
def retrieve_relevant_chunks(
    query: str,
    chunks: list[Document],
    top_k: int = 3,
) -> tuple[list[RetrievedChunk], dict[str, float]]:
    logger = get_run_logger()

    query_tokens = _tokenize(query)
    logger.info("Query tokens: %s", query_tokens)

    scored: list[RetrievedChunk] = []
    for chunk in chunks:
        score = _score_chunk(query_tokens, chunk)
        if score > 0:
            scored.append(
                RetrievedChunk(
                    doc_id=chunk.doc_id,
                    text=chunk.text,
                    score=score,
                )
            )

    scored.sort(key=lambda item: item.score, reverse=True)
    top_chunks = scored[:top_k]

    logger.info(
        "Retrieved %d chunks with non-zero score (top_k = %d).",
        len(scored),
        top_k,
    )
    logger.info(
        "Top chunk ids with scores: %s",
        [(chunk.doc_id, chunk.score) for chunk in top_chunks],
    )

    coverage_tokens: set[str] = set()
    for chunk in top_chunks:
        coverage_tokens.update(_tokenize(chunk.text))

    coverage = len(set(query_tokens) & coverage_tokens) / max(len(set(query_tokens)), 1)
    logger.info("Approximate keyword coverage in top chunks: %.2f", coverage)

    metrics = {
        "coverage": coverage,
        "retrieved_count": float(len(scored)),
        "top_k": float(top_k),
    }
    return top_chunks, metrics


@task
def llm_answer(query: str, context_chunks: list[RetrievedChunk]) -> str:
    logger = get_run_logger()

    logger.info("Context passed to the model:")
    for chunk in context_chunks:
        logger.info("- [%s] %s", chunk.doc_id, chunk.text)

    answer = (
        "Yes, you can pay your subscription with Bitcoin or other cryptocurrencies. "
        "We support flexible payment options for your convenience."
    )

    logger.info("Model answer (intentionally incorrect for this example): %s", answer)
    return answer


@task
def summarize_diagnostics(
    query: str,
    answer: str,
    retrieved: list[RetrievedChunk],
    retrieval_metrics: dict[str, float],
    total_docs: int,
    total_chunks: int,
) -> RagRunStats:
    logger = get_run_logger()

    query_tokens = set(_tokenize(query))
    answer_tokens = set(_tokenize(answer))

    tracked_terms = {"bitcoin", "subscription", "paypal", "credit", "cards"}
    missing_keywords = sorted((query_tokens & tracked_terms) - answer_tokens)

    answer_contains_forbidden = any(
        token in answer_tokens for token in ("bitcoin", "crypto", "cryptocurrency", "cryptocurrencies")
    )

    retrieved_ids = [chunk.doc_id for chunk in retrieved]
    retrieval_coverage = retrieval_metrics.get("coverage", 0.0)

    logger.info("Diagnostics summary:")
    logger.info("  retrieved_ids = %s", retrieved_ids)
    logger.info("  retrieval_coverage = %.2f", retrieval_coverage)
    logger.info("  missing_keywords_in_answer = %s", missing_keywords)
    logger.info("  answer_contains_forbidden = %s", answer_contains_forbidden)

    logger.info("Possible failure patterns to investigate:")

    if answer_contains_forbidden:
        logger.info(
            "- Grounding drift: the answer introduces a payment method that the FAQ explicitly forbids."
        )

    if retrieval_coverage < 0.5:
        logger.info(
            "- Retriever coverage issue: query keywords are weakly represented in the top chunks."
        )

    if not retrieved_ids:
        logger.info(
            "- Retriever recall failure: no chunks scored as relevant for this query."
        )

    return RagRunStats(
        query=query,
        total_docs=total_docs,
        total_chunks=total_chunks,
        retrieved_ids=retrieved_ids,
        retrieval_coverage=retrieval_coverage,
        missing_keywords=missing_keywords,
        answer_contains_forbidden=answer_contains_forbidden,
    )


@task
def choose_follow_up_action(stats: RagRunStats) -> str:
    logger = get_run_logger()

    if stats.answer_contains_forbidden:
        action = "halt_for_manual_review"
        logger.info(
            "Selected follow-up action: %s (answer conflicts with retrieved policy).",
            action,
        )
        return action

    if not stats.retrieved_ids:
        action = "stop_due_to_empty_retrieval"
        logger.info(
            "Selected follow-up action: %s (no relevant context was retrieved).",
            action,
        )
        return action

    if stats.retrieval_coverage < 0.5:
        action = "retry_with_broader_retrieval"
        logger.info(
            "Selected follow-up action: %s (retrieval coverage is below threshold).",
            action,
        )
        return action

    action = "proceed"
    logger.info("Selected follow-up action: %s.", action)
    return action


@flow
def rag_failure_diagnostics_flow(
    query: str = "Can I pay my subscription with Bitcoin?",
) -> RagRunStats:
    docs = ingest_documents()
    chunks = chunk_documents(docs)
    retrieved, metrics = retrieve_relevant_chunks(query=query, chunks=chunks, top_k=3)
    answer = llm_answer(query=query, context_chunks=retrieved)

    stats = summarize_diagnostics(
        query=query,
        answer=answer,
        retrieved=retrieved,
        retrieval_metrics=metrics,
        total_docs=len(docs),
        total_chunks=len(chunks),
    )

    next_step = choose_follow_up_action(stats)

    logger = get_run_logger()

    if next_step == "retry_with_broader_retrieval":
        logger.warning(
            "Retrying with a broader retrieval window before any downstream action."
        )
        retrieved, metrics = retrieve_relevant_chunks(query=query, chunks=chunks, top_k=5)
        answer = llm_answer(query=query, context_chunks=retrieved)
        stats = summarize_diagnostics(
            query=query,
            answer=answer,
            retrieved=retrieved,
            retrieval_metrics=metrics,
            total_docs=len(docs),
            total_chunks=len(chunks),
        )
    elif next_step == "halt_for_manual_review":
        logger.warning(
            "Halting before any downstream action because the answer conflicts with the retrieved context."
        )
    elif next_step == "stop_due_to_empty_retrieval":
        logger.warning(
            "Stopping early because retrieval returned no relevant context."
        )
    else:
        logger.info(
            "Diagnostics look healthy enough to continue to a downstream step."
        )

    return stats


if __name__ == "__main__":
    rag_failure_diagnostics_flow()
