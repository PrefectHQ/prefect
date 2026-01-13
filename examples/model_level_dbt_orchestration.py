# ---
# title: Model-Level dbt Orchestration
# description: Orchestrate dbt models individually using dbt's native selection syntax, with Prefect handling conditional execution and observability.
# icon: sitemap
# dependencies: ["prefect", "prefect-dbt>=0.7.0rc1", "dbt-core", "dbt-duckdb"]
# keywords: ["dbt", "orchestration", "dependencies", "models", "lineage", "dag"]
# draft: false
# order: 4
# ---
#
# **Run specific dbt models with Prefect orchestration – leverage dbt's native dependency resolution while adding conditional execution and model-level observability.**
#
# dbt already handles dependency resolution and topological sorting - that's its core job.
# This example shows how to combine dbt's model selection with Prefect's orchestration
# capabilities for patterns like:
#
# * **Conditional downstream execution** – Only run downstream models when upstream succeeds
# * **Model-level tasks** – Each model run is a separate Prefect task with its own observability
# * **Custom orchestration logic** – Add business rules around which models run when
#
# > **Note**: This example uses **dbt Core** which allows running specific models via
# > `--select`. dbt Cloud's API only supports job-level operations.
#
# ### dbt's Selection Syntax (the right way)
#
# dbt already provides powerful model selection:
# - `dbt run -s my_model` – Run just this model
# - `dbt run -s +my_model` – Run this model and all upstream dependencies
# - `dbt run -s my_model+` – Run this model and all downstream dependents
# - `dbt run -s +my_model+` – Run upstream, model, and downstream
# - `dbt run -s tag:critical` – Run all models with a specific tag
#
# Prefect doesn't need to reimplement this - we just need to orchestrate *when* and *whether*
# to invoke these commands.
#
# ### Running the example
# ```bash
# python examples/model_level_dbt_orchestration.py
# ```

import io
import json
import shutil
import urllib.request
import zipfile
from pathlib import Path
from typing import Any

from prefect_dbt import PrefectDbtRunner, PrefectDbtSettings

from prefect import flow, task
from prefect.logging import get_run_logger

DEFAULT_REPO_ZIP = (
    "https://github.com/PrefectHQ/examples/archive/refs/heads/examples-markdown.zip"
)


# ---------------------------------------------------------------------------
# Project Setup
# ---------------------------------------------------------------------------


@task(retries=2, retry_delay_seconds=5, log_prints=True)
def setup_dbt_project(repo_zip_url: str = DEFAULT_REPO_ZIP) -> Path:
    """Download and setup the demo dbt project with DuckDB profile."""
    project_dir = Path(__file__).parent / "prefect_dbt_project"

    if not project_dir.exists():
        print(f"Downloading dbt project archive → {repo_zip_url}\n")
        tmp_extract_base = project_dir.parent / "_tmp_dbt_extract"
        if tmp_extract_base.exists():
            shutil.rmtree(tmp_extract_base)

        with urllib.request.urlopen(repo_zip_url) as resp:
            data = resp.read()

        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            zf.extractall(tmp_extract_base)

        candidates = list(
            tmp_extract_base.rglob("**/resources/prefect_dbt_project/dbt_project.yml")
        )
        if not candidates:
            raise ValueError("dbt_project.yml not found in expected location")

        project_root = candidates[0].parent
        shutil.move(str(project_root), str(project_dir))
        shutil.rmtree(tmp_extract_base)
        print(f"Extracted dbt project to {project_dir}\n")
    else:
        print(f"Using cached dbt project at {project_dir}\n")

    # Create profiles.yml for DuckDB
    profiles_content = f"""demo:
  outputs:
    dev:
      type: duckdb
      path: {project_dir}/demo.duckdb
      threads: 1
  target: dev"""

    with open(project_dir / "profiles.yml", "w") as f:
        f.write(profiles_content)

    return project_dir


# ---------------------------------------------------------------------------
# Model Execution – Run models using dbt's native selection
# ---------------------------------------------------------------------------


@task(retries=1, retry_delay_seconds=5, log_prints=True)
def run_dbt_models(
    project_dir: Path,
    select: str,
    full_refresh: bool = False,
) -> dict[str, Any]:
    """Run dbt models using dbt's native --select syntax.

    This uses dbt's built-in dependency resolution - we don't need to
    reimplement topological sorting. dbt handles it.

    Args:
        project_dir: Path to the dbt project
        select: dbt selection syntax (e.g., "my_model", "+my_model", "tag:critical")
        full_refresh: Whether to do a full refresh for incremental models

    Returns:
        Dict with model execution results
    """
    logger = get_run_logger()
    logger.info(f"Running dbt with selection: {select}")

    settings = PrefectDbtSettings(
        project_dir=str(project_dir),
        profiles_dir=str(project_dir),
    )
    runner = PrefectDbtRunner(settings=settings, raise_on_failure=False)

    # Build the command - dbt handles all dependency resolution
    cmd = ["run", "--select", select]
    if full_refresh:
        cmd.append("--full-refresh")

    runner.invoke(cmd)

    # Parse results
    run_results_path = project_dir / "target" / "run_results.json"
    results = {"select": select, "models": [], "success": True}

    if run_results_path.exists():
        with open(run_results_path) as f:
            run_results = json.load(f)

        for r in run_results.get("results", []):
            model_result = {
                "unique_id": r.get("unique_id"),
                "status": r.get("status"),
                "execution_time": r.get("execution_time", 0),
            }
            results["models"].append(model_result)
            if r.get("status") not in ("success", "pass"):
                results["success"] = False

    return results


@task(log_prints=True)
def run_dbt_tests(
    project_dir: Path,
    select: str | None = None,
) -> dict[str, Any]:
    """Run dbt tests, optionally for specific models."""
    logger = get_run_logger()

    settings = PrefectDbtSettings(
        project_dir=str(project_dir),
        profiles_dir=str(project_dir),
    )
    runner = PrefectDbtRunner(settings=settings, raise_on_failure=False)

    cmd = ["test"]
    if select:
        cmd.extend(["--select", select])
        logger.info(f"Running tests for: {select}")
    else:
        logger.info("Running all tests")

    runner.invoke(cmd)

    # Parse results
    run_results_path = project_dir / "target" / "run_results.json"
    results = {"tests": [], "passed": 0, "failed": 0}

    if run_results_path.exists():
        with open(run_results_path) as f:
            run_results = json.load(f)

        for r in run_results.get("results", []):
            status = r.get("status")
            results["tests"].append({"unique_id": r.get("unique_id"), "status": status})
            if status in ("pass", "success"):
                results["passed"] += 1
            else:
                results["failed"] += 1

    return results


# ---------------------------------------------------------------------------
# Orchestration Patterns
# ---------------------------------------------------------------------------


@flow(name="run_model_with_upstream", log_prints=True)
def run_model_with_upstream(
    project_dir: Path,
    model: str,
) -> dict[str, Any]:
    """Run a model and all its upstream dependencies.

    Uses dbt's +model syntax - dbt figures out the dependency order.
    """
    logger = get_run_logger()
    logger.info(f"Running {model} with all upstream dependencies")

    # The + prefix tells dbt to include upstream deps
    # dbt handles the topological sort internally
    return run_dbt_models(project_dir, select=f"+{model}")


@flow(name="run_model_then_downstream", log_prints=True)
def run_model_then_downstream(
    project_dir: Path,
    model: str,
    run_downstream: bool = True,
) -> dict[str, Any]:
    """Run a model, then conditionally run its downstream dependents.

    This is where Prefect adds value - conditional orchestration logic
    that dbt doesn't handle on its own.
    """
    logger = get_run_logger()

    # First, run just this model
    logger.info(f"Running model: {model}")
    result = run_dbt_models(project_dir, select=model)

    if not result["success"]:
        logger.error(f"Model {model} failed - skipping downstream")
        return {"model": result, "downstream": None, "downstream_skipped": True}

    if not run_downstream:
        logger.info("Downstream execution disabled")
        return {"model": result, "downstream": None, "downstream_skipped": True}

    # Model succeeded - run downstream dependents
    # The model+ syntax (suffix) tells dbt to include downstream
    logger.info(f"Model {model} succeeded - running downstream dependents")
    downstream_result = run_dbt_models(project_dir, select=f"{model}+")

    return {
        "model": result,
        "downstream": downstream_result,
        "downstream_skipped": False,
    }


@flow(name="staged_model_execution", log_prints=True)
def staged_model_execution(
    project_dir: Path,
    stages: list[str],
) -> dict[str, Any]:
    """Run models in explicit stages with gates between them.

    Each stage must succeed before the next stage runs.
    Stages can use any dbt selection syntax.

    Example stages:
        ["tag:staging", "tag:intermediate", "tag:marts"]
        ["stg_*", "int_*", "fct_* mart_*"]
    """
    logger = get_run_logger()
    results = {"stages": [], "failed_at_stage": None}

    for i, stage_select in enumerate(stages):
        logger.info(f"Stage {i + 1}/{len(stages)}: {stage_select}")

        stage_result = run_dbt_models(project_dir, select=stage_select)
        results["stages"].append({"select": stage_select, "result": stage_result})

        if not stage_result["success"]:
            logger.error(f"Stage '{stage_select}' failed - stopping pipeline")
            results["failed_at_stage"] = i
            break

        logger.info(f"Stage '{stage_select}' succeeded")

    return results


# ---------------------------------------------------------------------------
# Main Flow
# ---------------------------------------------------------------------------


@flow(name="model_level_dbt_orchestration", log_prints=True)
def model_level_dbt_flow() -> dict[str, Any]:
    """Demonstrate model-level dbt orchestration patterns.

    Shows how Prefect orchestrates dbt without reimplementing dbt's
    dependency resolution - we use dbt's --select syntax and add
    conditional execution logic on top.
    """
    logger = get_run_logger()

    # Setup
    project_dir = setup_dbt_project()

    # Install deps
    settings = PrefectDbtSettings(
        project_dir=str(project_dir),
        profiles_dir=str(project_dir),
    )
    runner = PrefectDbtRunner(settings=settings, raise_on_failure=False)
    runner.invoke(["deps"])

    # Pattern 1: Run a specific model with its upstream dependencies
    # dbt's +model syntax handles the dependency resolution
    logger.info("\n" + "=" * 50)
    logger.info("Pattern 1: Run model with upstream dependencies")
    logger.info("=" * 50)
    result1 = run_model_with_upstream(project_dir, "my_second_dbt_model")

    # Pattern 2: Run model, then conditionally run downstream
    # This is where Prefect adds value - conditional logic
    logger.info("\n" + "=" * 50)
    logger.info("Pattern 2: Conditional downstream execution")
    logger.info("=" * 50)
    result2 = run_model_then_downstream(project_dir, "my_first_dbt_model")

    # Pattern 3: Run tests for specific models
    logger.info("\n" + "=" * 50)
    logger.info("Pattern 3: Model-specific tests")
    logger.info("=" * 50)
    test_results = run_dbt_tests(project_dir, select="my_first_dbt_model")

    return {
        "with_upstream": result1,
        "conditional_downstream": result2,
        "tests": test_results,
    }


# ### Key Takeaways
#
# 1. **Don't reimplement dbt's DAG resolution** - use `--select` syntax
# 2. **Prefect adds value through orchestration logic** - conditional execution,
#    staged pipelines, model-level observability
# 3. **dbt selection syntax is powerful**:
#    - `+model` = upstream deps + model
#    - `model+` = model + downstream
#    - `tag:x` = all models with tag
#    - `path:models/staging` = all models in path
#
# For more on dbt selection: https://docs.getdbt.com/reference/node-selection/syntax

if __name__ == "__main__":
    print("Demonstrating model-level dbt orchestration patterns...\n")
    results = model_level_dbt_flow()
    print("\nDone!")
