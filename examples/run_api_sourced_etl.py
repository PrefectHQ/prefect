# ---
# title: API-sourced ETL
# description: Build a small ETL pipeline that fetches JSON from a public API, transforms it with pandas, and writes a CSV – all orchestrated by Prefect.
# icon: database
# dependencies: ["prefect", "httpx", "pandas"]
# keywords: ["getting_started", "etl", "pandas"]
# draft: false
# order: 2
# ---
#
# Prefect turns everyday Python into production-grade workflows with **zero boilerplate**.
#
# When you pair Prefect with pandas you get a **versatile ETL toolkit**:
#
# * **Python** supplies a rich ecosystem of connectors and libraries for virtually every data source and destination.
# * **pandas** gives you lightning-fast, expressive transforms that turn raw bits into tidy DataFrames.
# * **Prefect** wraps the whole thing in battle-tested orchestration: automatic [retries](https://docs.prefect.io/v3/develop/write-tasks#retries), [scheduling](https://docs.prefect.io/v3/deploy/index#workflow-scheduling-and-parametrization), and [observability](https://docs.prefect.io/v3/develop/logging#prefect-loggers) , so you don't have to write reams of defensive code.
#
# The result? You spend your time thinking about *what* you want to build, not *how* to keep it alive. Point this trio at any API, database, or file system and it will move the data where you need it while handling the messy details for you.
#
# In this article you will:
# 1. **Extract** JSON from the public [Dev.to REST API](https://dev.to/api).
# 2. **Transform** it into an analytics-friendly pandas `DataFrame`.
# 3. **Load** the result to a CSV – ready for your BI tool of choice.
#
# This example demonstrates these Prefect features:
# * [`@task`](https://docs.prefect.io/v3/develop/write-tasks#write-and-run-tasks) – wrap any function in retries & observability.
# * [`log_prints`](https://docs.prefect.io/v3/develop/logging#configure-logging) – surface `print()` logs automatically.
# * Automatic [**retries**](https://docs.prefect.io/v3/develop/write-tasks#retries) with back-off, no extra code.
#
# ### Rapid analytics from a public API
# Your data team wants engagement metrics from Dev.to articles, daily. You need a quick,
# reliable pipeline that anyone can run locally and later schedule in Prefect Cloud.
#
# ### The Solution
# Write three small Python functions (extract, transform, load), add two decorators, and
# let Prefect handle [retries](https://docs.prefect.io/v3/develop/write-tasks#retries), [concurrency](https://docs.prefect.io/v3/develop/task-runners#configure-a-task-runner), and [logging](https://docs.prefect.io/v3/develop/logging#prefect-loggers). No framework-specific hoops, just
# Python the way you already write it.
#
# *For more background on Prefect's design philosophy, check out our blog post: [Built to Fail: Design Patterns for Resilient Data Pipelines](https://www.prefect.io/blog/built-to-fail-design-patterns-for-resilient-data-pipelines)*
#
# Watch as Prefect orchestrates the ETL pipeline with automatic retries and logging. The flow fetches multiple pages of articles, transforms them into a structured DataFrame, and saves the results to CSV. This pattern is highly adaptable - use it to build pipelines that move data between any sources and destinations:
# * APIs → Databases (Postgres, MySQL, etc.)
# * APIs → Cloud Storage (S3, GCS, Azure)
# * APIs → Data Warehouses (Snowflake, BigQuery, Redshift, etc.)
# * And many more combinations
#
# ## Code walkthrough
# 1. **Imports** – Standard libraries for HTTP + pandas.
# 2. **`fetch_page` task** – Downloads a single page with retries.
# 3. **`to_dataframe` task** – Normalises JSON to a pandas DataFrame.
# 4. **`save_csv` task** – Persists the DataFrame and logs a peek.
# 5. **`etl` flow** – Orchestrates the tasks sequentially for clarity.
# 6. **Execution** – A friendly `if __name__ == "__main__"` with some basic configurations kicks things off.
#

from __future__ import annotations

from pathlib import Path
from typing import Any

import httpx
import pandas as pd

from prefect import flow, task

# ---------------------------------------------------------------------------
# Extract – fetch a single page of articles
# ---------------------------------------------------------------------------


@task(retries=3, retry_delay_seconds=[2, 5, 15])
def fetch_page(page: int, api_base: str, per_page: int) -> list[dict[str, Any]]:
    """Return a list of article dicts for a given page number."""
    url = f"{api_base}/articles"
    params = {"page": page, "per_page": per_page}
    print(f"Fetching page {page} …")
    response = httpx.get(url, params=params, timeout=30)
    response.raise_for_status()
    return response.json()


# ---------------------------------------------------------------------------
# Transform – convert list[dict] ➜ pandas DataFrame
# ---------------------------------------------------------------------------


@task
def to_dataframe(raw_articles: list[list[dict[str, Any]]]) -> pd.DataFrame:
    """Flatten & normalise JSON into a tidy DataFrame."""
    # Combine pages, then select fields we care about
    records = [article for page in raw_articles for article in page]
    df = pd.json_normalize(records)[
        [
            "id",
            "title",
            "published_at",
            "url",
            "comments_count",
            "positive_reactions_count",
            "tag_list",
            "user.username",
        ]
    ]
    return df


# ---------------------------------------------------------------------------
# Load – save DataFrame to CSV (or print preview)
# ---------------------------------------------------------------------------


@task
def save_csv(df: pd.DataFrame, path: Path) -> None:
    """Persist DataFrame to disk then log a preview."""
    df.to_csv(path, index=False)
    print(f"Saved {len(df)} rows ➜ {path}\n\nPreview:\n{df.head()}\n")


# ---------------------------------------------------------------------------
# Flow – orchestrate the ETL with optional concurrency
# ---------------------------------------------------------------------------


@flow(name="devto_etl", log_prints=True)
def etl(api_base: str, pages: int, per_page: int, output_file: Path) -> None:
    """Run the end-to-end ETL for *pages* of articles."""

    # Extract – simple loop for clarity
    raw_pages: list[list[dict[str, Any]]] = []
    for page_number in range(1, pages + 1):
        raw_pages.append(fetch_page(page_number, api_base, per_page))

    # Transform
    df = to_dataframe(raw_pages)

    # Load
    save_csv(df, output_file)


# ## Run it!
#
# ```bash
# python 01_getting_started/03_run_api_sourced_etl.py
# ```

if __name__ == "__main__":
    # Configuration – tweak to taste
    api_base = "https://dev.to/api"
    pages = 3  # Number of pages to fetch
    per_page = 30  # Articles per page (max 30 per API docs)
    output_file = Path("devto_articles.csv")

    etl(api_base=api_base, pages=pages, per_page=per_page, output_file=output_file)

# ## What just happened?
#
# 1. Prefect registered a *flow run* and three *task runs* (`fetch_page`, `to_dataframe`, `save_csv`).
# 2. Each `fetch_page` call downloaded a page and, if it failed, would automatically retry.
# 3. The raw JSON pages were combined into a single pandas DataFrame.
# 4. The CSV was written to disk and a preview printed locally (the flow's `log_prints=True` flag logs messages inside the flow body; prints inside tasks are displayed in the console).
# 5. You can view run details, timings, and logs in the Prefect UI.
#
# ## Key Takeaways
#
# * **Pure Python, powered-up** – Decorators add retries and logging without changing your logic.
# * **Observability first** – Each task run (including every page fetch) is logged and can be viewed in the UI if you have a Prefect Cloud account or a local Prefect server running.
# * **Composable** – Swap `save_csv` for a database loader or S3 upload with one small change.
# * **Reusable** – Import the `etl` flow and run it with different parameters from another flow.
#
# Prefect lets you focus on *data*, not orchestration plumbing – happy ETL-ing! 🎉
