# ---
# title: Orchestrating batch RAG diagnostics with retries and routing
# description: Use Prefect to process a batch of RAG queries, retry flaky steps, and route low-coverage results for review.
# icon: database
# dependencies: ["prefect"]
# keywords: ["rag", "llm", "orchestration", "observability", "debugging"]
# draft: false
# ---
#
# This example shows how to use Prefect to orchestrate a small batch RAG workflow.
#
# The goal is not to build a production RAG system.
# Instead, we show how Prefect can help with workflow problems that appear
# around RAG pipelines:
#
# - retrying a flaky preparation step
# - running query level diagnostics across a batch
# - routing low coverage retrieval results for review
# - creating a run artifact that summarizes what happened
#
# You can adapt the same pattern to real retrieval, reranking, embedding,
# evaluation, or alerting tasks in your own system.

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from prefect import flow, get_run_logger, task
from prefect.artifacts import create_markdown_artifact

STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "can",
    "do",
    "for",
    "from",
    "i",
    "in",
    "is",
    "my",
    "of",
    "or",
    "the",
    "to",
    "we",
    "what",
    "with",
    "you",
    "your",
}
FLAKY_QUERY = "Do you accept wire transfers for subscriptions?"
PREPARE_ATTEMPTS: dict[str, int] = {}


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
class PreparedQuery:
    query: str
    tokens: list[str]
    attempts_used: int


@dataclass
class QueryEvaluation:
    query: str
    query_tokens: list[str]
    coverage: float
    matched_tokens: list[str]
    retrieved_ids: list[str]
    retrieved_count: int
    top_score: float


@dataclass
class QueryResult:
    query: str
    attempts_used: int
    coverage: float
    action: str
    retrieved_ids: list[str]
    answer: str
    matched_tokens: list[str] = field(default_factory=list)


def _tokenize(text: str) -> list[str]:
    cleaned = (
        text.lower()
        .replace("?", " ")
        .replace(",", " ")
        .replace(".", " ")
        .replace(":", " ")
    )
    return [token for token in cleaned.split() if token and token not in STOPWORDS]


def _score_chunk(query_tokens: list[str], chunk: Document) -> float:
    chunk_tokens = set(_tokenize(chunk.text))
    overlap = set(query_tokens) & chunk_tokens
    return float(len(overlap))


@task
def ingest_documents() -> list[Document]:
    logger = get_run_logger()

    docs = [
        Document(
            doc_id="faq-1",
            text=(
                "We currently accept major credit cards and PayPal for "
                "subscriptions. All payments are processed in USD."
            ),
        ),
        Document(
            doc_id="faq-2",
            text=(
                "You can update or cancel your subscription at any time from "
                "your account billing settings. Changes apply to the next "
                "billing cycle."
            ),
        ),
        Document(
            doc_id="faq-3",
            text=(
                "We do not support cryptocurrency payments. Bitcoin and other "
                "cryptocurrencies are not accepted."
            ),
        ),
    ]

    logger.info("Ingested %d documents into the knowledge base.", len(docs))
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
            chunks.append(
                Document(doc_id=f"{doc.doc_id}-chunk-{index}", text=chunk_text)
            )
            start = end
            index += 1

    avg_len = sum(len(chunk.text) for chunk in chunks) / len(chunks) if chunks else 0.0
    logger.info(
        "Created %d chunks from %d docs with average length %.1f chars.",
        len(chunks),
        len(docs),
        avg_len,
    )
    return chunks


@task
def get_queries() -> list[str]:
    return [
        "Do you accept PayPal for subscriptions?",
        "Can I cancel from billing settings?",
        "What currency are payments processed in?",
        "Can I pay with Bitcoin?",
        FLAKY_QUERY,
    ]


@task(retries=2, retry_delay_seconds=1)
def prepare_query(query: str) -> PreparedQuery:
    logger = get_run_logger()

    PREPARE_ATTEMPTS[query] = PREPARE_ATTEMPTS.get(query, 0) + 1
    attempts_used = PREPARE_ATTEMPTS[query]

    if query == FLAKY_QUERY and attempts_used == 1:
        logger.warning(
            "Simulating a transient query preparation failure for %r on attempt %d.",
            query,
            attempts_used,
        )
        raise RuntimeError("Temporary preparation error")

    tokens = _tokenize(query)
    logger.info(
        "Prepared query %r into tokens %s after %d attempt(s).",
        query,
        tokens,
        attempts_used,
    )
    return PreparedQuery(query=query, tokens=tokens, attempts_used=attempts_used)


@task
def retrieve_relevant_chunks(
    prepared: PreparedQuery,
    chunks: list[Document],
    top_k: int = 3,
) -> list[RetrievedChunk]:
    logger = get_run_logger()

    scored: list[RetrievedChunk] = []
    for chunk in chunks:
        score = _score_chunk(prepared.tokens, chunk)
        if score > 0:
            scored.append(
                RetrievedChunk(doc_id=chunk.doc_id, text=chunk.text, score=score)
            )

    scored.sort(key=lambda item: item.score, reverse=True)
    top_chunks = scored[:top_k]

    logger.info(
        "Retrieved %d matching chunks for %r. Top results: %s",
        len(scored),
        prepared.query,
        [(chunk.doc_id, chunk.score) for chunk in top_chunks],
    )
    return top_chunks


@task
def evaluate_retrieval_coverage(
    prepared: PreparedQuery,
    retrieved: list[RetrievedChunk],
) -> QueryEvaluation:
    logger = get_run_logger()

    retrieved_tokens: set[str] = set()
    for chunk in retrieved:
        retrieved_tokens.update(_tokenize(chunk.text))

    matched_tokens = sorted(set(prepared.tokens) & retrieved_tokens)
    coverage = len(matched_tokens) / max(len(set(prepared.tokens)), 1)
    top_score = retrieved[0].score if retrieved else 0.0
    retrieved_ids = [chunk.doc_id for chunk in retrieved]

    logger.info(
        "Coverage for %r is %.2f with matched tokens %s.",
        prepared.query,
        coverage,
        matched_tokens,
    )

    return QueryEvaluation(
        query=prepared.query,
        query_tokens=prepared.tokens,
        coverage=coverage,
        matched_tokens=matched_tokens,
        retrieved_ids=retrieved_ids,
        retrieved_count=len(retrieved),
        top_score=top_score,
    )


@task
def route_query(evaluation: QueryEvaluation, threshold: float = 0.6) -> str:
    logger = get_run_logger()

    action = "answer" if evaluation.coverage >= threshold else "review"
    logger.info(
        "Routing %r to %s because coverage is %.2f and threshold is %.2f.",
        evaluation.query,
        action,
        evaluation.coverage,
        threshold,
    )
    return action


@task
def generate_answer(
    prepared: PreparedQuery,
    retrieved: list[RetrievedChunk],
    action: str,
) -> str:
    logger = get_run_logger()

    if action != "answer":
        message = (
            "Skipped answer generation because retrieval coverage was below "
            "the review threshold."
        )
        logger.warning("%s Query: %r", message, prepared.query)
        return message

    query_lower = prepared.query.lower()

    if "bitcoin" in query_lower or "cryptocurr" in query_lower:
        answer = (
            "No. We do not support cryptocurrency payments. Bitcoin and other "
            "cryptocurrencies are not accepted."
        )
    elif "paypal" in query_lower or "credit" in query_lower:
        answer = (
            "We currently accept major credit cards and PayPal for "
            "subscriptions. All payments are processed in USD."
        )
    elif "cancel" in query_lower or "billing" in query_lower:
        answer = (
            "You can update or cancel your subscription from your account "
            "billing settings. Changes apply to the next billing cycle."
        )
    elif "currency" in query_lower or "usd" in query_lower:
        answer = "All payments are processed in USD."
    elif retrieved:
        answer = retrieved[0].text
    else:
        answer = "No grounded answer was produced."

    logger.info("Generated grounded answer for %r.", prepared.query)
    return answer


@task
def finalize_query_result(
    prepared: PreparedQuery,
    evaluation: QueryEvaluation,
    action: str,
    answer: str,
) -> QueryResult:
    return QueryResult(
        query=prepared.query,
        attempts_used=prepared.attempts_used,
        coverage=evaluation.coverage,
        action=action,
        retrieved_ids=evaluation.retrieved_ids,
        answer=answer,
        matched_tokens=evaluation.matched_tokens,
    )


@task
def build_batch_artifact(results: list[QueryResult], threshold: float) -> None:
    logger = get_run_logger()

    answered = sum(1 for result in results if result.action == "answer")
    reviewed = len(results) - answered
    retried = sum(1 for result in results if result.attempts_used > 1)

    lines = [
        "### Batch RAG diagnostics",
        "",
        f"- queries_processed: {len(results)}",
        f"- answered: {answered}",
        f"- routed_for_review: {reviewed}",
        f"- queries_with_retries: {retried}",
        f"- coverage_threshold: {threshold:.2f}",
        "",
        "| Query | Attempts | Coverage | Action | Retrieved IDs | Matched tokens |",
        "| --- | ---: | ---: | --- | --- | --- |",
    ]

    for result in results:
        retrieved_ids = (
            ", ".join(result.retrieved_ids) if result.retrieved_ids else "none"
        )
        matched_tokens = (
            ", ".join(result.matched_tokens) if result.matched_tokens else "none"
        )
        lines.append(
            "| "
            f"{result.query} | "
            f"{result.attempts_used} | "
            f"{result.coverage:.2f} | "
            f"{result.action} | "
            f"{retrieved_ids} | "
            f"{matched_tokens} |"
        )

    review_queries = [result.query for result in results if result.action == "review"]
    if review_queries:
        lines.extend(["", "**Queries routed for review**", ""])
        lines.extend(f"- {query}" for query in review_queries)

    markdown = "\n".join(lines)
    create_markdown_artifact(
        key="rag-batch-diagnostics",
        markdown=markdown,
        description="Batch summary of RAG diagnostics, retries, and routing.",
    )
    logger.info("Created artifact 'rag-batch-diagnostics'.")


@flow
def rag_failure_diagnostics_flow(
    coverage_threshold: float = 0.6,
) -> list[QueryResult]:
    docs = ingest_documents()
    chunks = chunk_documents(docs)
    queries = get_queries()

    scheduled: list[tuple[str, Any, Any, Any, Any]] = []

    for query in queries:
        prepared_future = prepare_query.submit(query)
        retrieved_future = retrieve_relevant_chunks.submit(
            prepared=prepared_future,
            chunks=chunks,
            top_k=3,
        )
        evaluation_future = evaluate_retrieval_coverage.submit(
            prepared=prepared_future,
            retrieved=retrieved_future,
        )
        action_future = route_query.submit(
            evaluation=evaluation_future,
            threshold=coverage_threshold,
        )
        scheduled.append(
            (
                query,
                prepared_future,
                retrieved_future,
                evaluation_future,
                action_future,
            )
        )

    result_futures = []
    for (
        _,
        prepared_future,
        retrieved_future,
        evaluation_future,
        action_future,
    ) in scheduled:
        answer_future = generate_answer.submit(
            prepared=prepared_future,
            retrieved=retrieved_future,
            action=action_future,
        )
        result_future = finalize_query_result.submit(
            prepared=prepared_future,
            evaluation=evaluation_future,
            action=action_future,
            answer=answer_future,
        )
        result_futures.append(result_future)

    results = [future.result() for future in result_futures]
    build_batch_artifact(results, coverage_threshold)
    return results


if __name__ == "__main__":
    rag_failure_diagnostics_flow()
