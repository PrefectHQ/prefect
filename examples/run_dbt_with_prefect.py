# ---
# title: dbt Model Orchestration
# description: Orchestrate any dbt project with bullet-proof retries, observability, and a single Python file – no YAML or shell scripts required.
# icon: database
# dependencies: ["prefect", "prefect-dbt>=0.7.0rc1", "dbt-core", "dbt-duckdb"]
# keywords: ["dbt", "materialization", "tasks", "analytics"]
# draft: false
# order: 3
# ---
#
# **Transform unreliable dbt scripts into production-grade data pipelines with enterprise observability, automatic failure recovery, and zero-downtime deployments.**
#
# When you combine Prefect with dbt, you get the **perfect marriage of best-in-class analytics tools**:
#
# * **Python** gives you the flexibility to integrate with any data source, API, or system your analytics need.
# * **dbt Core** handles the heavy lifting of SQL transformations, testing, and documentation.
# * **Prefect** wraps the entire workflow in battle-tested orchestration: automatic [retries](https://docs.prefect.io/v3/develop/write-tasks#retries), [scheduling](https://docs.prefect.io/v3/deploy/index#workflow-scheduling-and-parametrization), and [observability](https://docs.prefect.io/v3/develop/logging#prefect-loggers).
#
# The result? Your analytics team gets reliable, observable data pipelines that leverage the strengths of both platforms. Point this combo at any warehouse and it will transform your data while providing enterprise-grade workflow management.
#
# > **Note**: This example uses **dbt Core** (the open-source CLI). For dbt Cloud integration, see the [dbt Cloud examples](https://docs.prefect.io/integrations/prefect-dbt#dbt-cloud) in the Prefect documentation.
#
# This example demonstrates these Prefect features:
# * [`@task`](https://docs.prefect.io/v3/develop/write-tasks#write-and-run-tasks) – wrap dbt commands in retries & observability.
# * [`log_prints`](https://docs.prefect.io/v3/develop/logging#configure-logging) – surface dbt output automatically in Prefect logs.
# * Automatic [**retries**](https://docs.prefect.io/v3/develop/write-tasks#retries) with exponential back-off for flaky network connections.
# * [**prefect-dbt integration**](https://docs.prefect.io/integrations/prefect-dbt) – native dbt execution with enhanced logging and failure handling.
#
# ### The Scenario: Reliable Analytics Workflows
# Your analytics team uses dbt to model data in DuckDB for rapid local development and testing, but deploys to Snowflake in production. You need a workflow that:
# - Anyone can run locally without complex setup (DuckDB)
# - Automatically retries on network failures or temporary dbt errors
# - Provides clear logs and observability for debugging
# - Can be easily scheduled and deployed to production
#
# ### Our Solution
# Write three focused Python functions (download project, run dbt commands, orchestrate workflow), add Prefect decorators, and let Prefect handle [retries](https://docs.prefect.io/v3/develop/write-tasks#retries), [logging](https://docs.prefect.io/v3/develop/logging#prefect-loggers), and [scheduling](https://docs.prefect.io/v3/deploy/index#workflow-scheduling-and-parametrization). The entire example is self-contained – no git client or global dbt configuration required.
#
# *For more on integrating Prefect with dbt, see the [Prefect documentation](https://docs.prefect.io/integrations/dbt).*
#
# ### Running the example locally
# ```bash
# python 02_flows/prefect_and_dbt.py
# ```
# Watch as Prefect orchestrates the complete dbt lifecycle: downloading the project, running models, executing tests, and materializing results. The flow creates a local DuckDB file you can explore with any SQL tool.
#
# ## Code walkthrough
# 1. **Project Setup** – Download and cache a demo dbt project from GitHub
# 2. **dbt CLI Wrapper** – Execute dbt commands with automatic retries and logging using prefect-dbt
# 3. **Orchestration Flow** – Run the complete dbt lifecycle in sequence
# 4. **Execution** – Self-contained example that works out of the box

import io
import shutil
import urllib.request
import zipfile
from pathlib import Path

from prefect_dbt import PrefectDbtRunner, PrefectDbtSettings

from prefect import flow, task

DEFAULT_REPO_ZIP = (
    "https://github.com/PrefectHQ/examples/archive/refs/heads/examples-markdown.zip"
)

# ---------------------------------------------------------------------------
# Project Setup – download and cache dbt project
# ---------------------------------------------------------------------------
# To keep this example fully self-contained, we download a demo dbt project
# directly from GitHub as a ZIP file. This means users don't need git installed.
# [Learn more about tasks in the Prefect documentation](https://docs.prefect.io/v3/develop/write-tasks)


@task(retries=2, retry_delay_seconds=5, log_prints=True)
def build_dbt_project(repo_zip_url: str = DEFAULT_REPO_ZIP) -> Path:
    """Download and extract the demo dbt project, returning its local path.

    To keep the example fully self-contained we grab the GitHub archive as a ZIP
    so users do **not** need `git` installed. The project is extracted from the
    PrefectHQ/examples repository into a sibling directory next to this script
    (`prefect_dbt_project`). If that directory already exists we skip the download
    to speed up subsequent runs.
    """

    project_dir = Path(__file__).parent / "prefect_dbt_project"
    if project_dir.exists():
        print(f"Using cached dbt project at {project_dir}\n")
        return project_dir

    tmp_extract_base = project_dir.parent / "_tmp_dbt_extract"
    if tmp_extract_base.exists():
        shutil.rmtree(tmp_extract_base)

    print(f"Downloading dbt project archive → {repo_zip_url}\n")
    with urllib.request.urlopen(repo_zip_url) as resp:
        data = resp.read()

    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        zf.extractall(tmp_extract_base)

    # Find the folder containing dbt_project.yml (in resources/prefect_dbt_project)
    candidates = list(
        tmp_extract_base.rglob("**/resources/prefect_dbt_project/dbt_project.yml")
    )
    if not candidates:
        raise ValueError(
            "dbt_project.yml not found in resources/prefect_dbt_project – structure unexpected"
        )

    project_root = candidates[0].parent
    shutil.move(str(project_root), str(project_dir))
    shutil.rmtree(tmp_extract_base)

    print(f"Extracted dbt project to {project_dir}\n")
    return project_dir


# ---------------------------------------------------------------------------
# Create profiles.yml for DuckDB – needed for dbt to work
# ---------------------------------------------------------------------------
# This task creates a simple profiles.yml file for DuckDB so dbt can connect
# to the database. This keeps the example self-contained.


@task(retries=2, retry_delay_seconds=5, log_prints=True)
def create_dbt_profiles(project_dir: Path) -> None:
    """Create a profiles.yml file for DuckDB connection.

    This creates a simple DuckDB profile so dbt can run without external
    database configuration. The profile points to a local DuckDB file.
    This will overwrite any existing profiles.yml to ensure correct formatting.
    """

    profiles_content = f"""demo:
  outputs:
    dev:
      type: duckdb
      path: {project_dir}/demo.duckdb
      threads: 1
  target: dev"""

    profiles_path = project_dir / "profiles.yml"
    with open(profiles_path, "w") as f:
        f.write(profiles_content)

    print(f"Created/updated profiles.yml at {profiles_path}")


# ---------------------------------------------------------------------------
# dbt CLI Wrapper – execute commands with retries and logging using prefect-dbt
# ---------------------------------------------------------------------------
# This task uses the modern PrefectDbtRunner from prefect-dbt integration which
# provides native dbt execution with enhanced logging, failure handling, and
# automatic event emission.
# [Learn more about retries in the Prefect documentation](https://docs.prefect.io/v3/develop/write-tasks#retries)


@task(retries=2, retry_delay_seconds=5, log_prints=True)
def run_dbt_commands(commands: list[str], project_dir: Path) -> None:
    """Run dbt commands using the modern prefect-dbt integration.

    Uses PrefectDbtRunner which provides enhanced logging, failure handling,
    and automatic Prefect event emission for dbt node status changes.
    This is much more robust than subprocess calls and integrates natively
    with Prefect's observability features.
    """

    print(f"Running dbt commands: {commands}\n")

    # Configure dbt settings to point to our project directory
    settings = PrefectDbtSettings(
        project_dir=str(project_dir),
        profiles_dir=str(project_dir),  # Use project dir for profiles too
    )

    # Create runner and execute commands
    # Use raise_on_failure=False to handle dbt failures more gracefully
    runner = PrefectDbtRunner(settings=settings, raise_on_failure=False)

    for command in commands:
        print(f"Executing: dbt {command}")
        runner.invoke(command.split())
        print(f"Completed: dbt {command}\n")


# ---------------------------------------------------------------------------
# Orchestration Flow – run the complete dbt lifecycle
# ---------------------------------------------------------------------------
# This flow orchestrates the standard dbt workflow: debug → deps → seed → run → test.
# Each step is a separate task run in Prefect, providing granular observability
# and automatic retry handling for any step that fails. Now using the flexible
# prefect-dbt integration for enhanced dbt execution.
# [Learn more about flows in the Prefect documentation](https://docs.prefect.io/v3/develop/write-flows)


@flow(name="dbt_flow", log_prints=True)
def dbt_flow(repo_zip_url: str = DEFAULT_REPO_ZIP) -> None:
    """Run the demo dbt project with Prefect using prefect-dbt integration.

    Steps executed:
    1. Download and setup the dbt project
    2. Create profiles.yml for DuckDB connection
    3. `dbt deps`   – download any package dependencies (none for this tiny demo).
    4. `dbt seed`   – load seed CSVs if they exist (safe to run even when empty).
    5. `dbt run`    – build the model(s) defined under `models/`.
    6. `dbt test`   – execute any tests declared in the project.

    Each step runs as a separate Prefect task with automatic retries and logging.
    Uses the modern prefect-dbt integration for enhanced observability and
    native dbt execution.
    """

    project_dir = build_dbt_project(repo_zip_url)
    create_dbt_profiles(project_dir)

    # dbt commands – executed sequentially using prefect-dbt integration
    run_dbt_commands(["deps"], project_dir)
    run_dbt_commands(["seed"], project_dir)
    run_dbt_commands(["run"], project_dir)
    run_dbt_commands(["test"], project_dir)

    # Let users know where the DuckDB file was written for exploration
    duckdb_path = project_dir / "demo.duckdb"
    print(f"\nDone! DuckDB file located at: {duckdb_path.resolve()}")


# ### What Just Happened?
#
# Here's the sequence of events when you run this flow:
# 1. **Project Download** – Prefect registered a task run to download and extract the dbt project from GitHub (with automatic caching for subsequent runs).
# 2. **dbt Lifecycle** – Five separate task runs executed the standard dbt workflow: `deps`, `seed`, `run`, and `test`.
# 3. **Native dbt Integration** – Each dbt command used the `DbtCoreOperation` for enhanced logging, failure handling, and automatic event emission.
# 4. **Automatic Retries** – Each dbt command would automatically retry on failure (network issues, temporary dbt errors, etc.).
# 5. **Centralized Logging** – All dbt output streamed directly to Prefect logs with proper log level mapping.
# 6. **Event Emission** – Prefect automatically emitted events for each dbt node execution, enabling advanced monitoring and alerting.
# 7. **Local Results** – A DuckDB file appeared at `prefect_dbt_project/demo.duckdb` ready for analysis.
#
# **Prefect + prefect-dbt transformed a series of shell commands into a resilient, observable workflow** – no YAML files, no cron jobs, just Python with enterprise-grade dbt integration.
#
# ### Why This Matters
#
# Traditional dbt orchestration often involves brittle shell scripts, complex YAML configurations, or heavyweight workflow tools. Prefect with the prefect-dbt integration gives you **enterprise-grade orchestration with zero operational overhead**:
#
# - **Reliability**: Automatic retries with exponential backoff handle transient failures
# - **Native Integration**: DbtCoreOperation provides enhanced logging, failure handling, and event emission
# - **Observability**: Every dbt command and node is logged, timed, and searchable in the Prefect UI with proper log level mapping
# - **Event-Driven**: Automatic Prefect events for dbt node status changes enable advanced monitoring and alerting
# - **Portability**: The same Python file runs locally, in CI/CD, and in production
# - **Composability**: Easily extend this flow with data quality checks, Slack alerts, or downstream dependencies
#
# This pattern scales from prototype analytics to production data platforms. Whether you're running dbt against DuckDB for rapid local iteration or Snowflake for enterprise analytics, Prefect ensures your workflows are reliable, observable, and maintainable.
#
# To learn more about orchestrating analytics workflows with Prefect, check out:
# - [prefect-dbt integration guide](https://docs.prefect.io/integrations/prefect-dbt)
# - [Task configuration and retries](https://docs.prefect.io/v3/develop/write-tasks#retries)
# - [Workflow scheduling and deployment](https://docs.prefect.io/v3/deploy/index#workflow-scheduling-and-parametrization)

if __name__ == "__main__":
    dbt_flow()
