# ---
# title: Model-Level dbt Orchestration
# description: Run specific dbt models with conditional execution and model-level observability.
# icon: sitemap
# dependencies: ["prefect-dbt", "dbt-duckdb"]
# keywords: ["dbt", "orchestration", "dependencies", "models", "lineage", "dag"]
# draft: false
# order: 4
# ---
#
# **Run specific dbt models with Prefect orchestration – add conditional execution
# and model-level observability to your dbt workflows.**
#
# This example shows patterns for:
#
# * **Conditional downstream execution** – Only run downstream models when upstream succeeds
# * **Model-level observability** – Each dbt run is a separate Prefect task with results
#
# > **Note**: This example uses **dbt Core**. dbt Cloud's API only supports job-level operations.
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


@task(retries=1, retry_delay_seconds=5, log_prints=True)
def run_dbt_models(
    project_dir: Path,
    select: str,
    full_refresh: bool = False,
) -> dict[str, Any]:
    """Run dbt models using --select syntax.

    Args:
        project_dir: Path to the dbt project
        select: dbt selection syntax (e.g., "my_model", "+my_model", "tag:critical")
        full_refresh: Whether to do a full refresh for incremental models
    """
    logger = get_run_logger()
    logger.info(f"Running dbt with selection: {select}")

    settings = PrefectDbtSettings(
        project_dir=str(project_dir),
        profiles_dir=str(project_dir),
    )
    runner = PrefectDbtRunner(settings=settings, raise_on_failure=False)

    cmd = ["run", "--select", select]
    if full_refresh:
        cmd.append("--full-refresh")

    runner.invoke(cmd)

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


@flow(name="run_model_then_downstream", log_prints=True)
def run_model_then_downstream(
    project_dir: Path,
    model: str,
    run_downstream: bool = True,
) -> dict[str, Any]:
    """Run a model, then conditionally run its downstream dependents."""
    logger = get_run_logger()

    logger.info(f"Running model: {model}")
    result = run_dbt_models(project_dir, select=model)

    if not result["success"]:
        logger.error(f"Model {model} failed - skipping downstream")
        return {"model": result, "downstream": None, "downstream_skipped": True}

    if not run_downstream:
        return {"model": result, "downstream": None, "downstream_skipped": True}

    logger.info(f"Model {model} succeeded - running downstream dependents")
    downstream_result = run_dbt_models(project_dir, select=f"{model}+")

    return {
        "model": result,
        "downstream": downstream_result,
        "downstream_skipped": False,
    }


@flow(name="model_level_dbt_orchestration", log_prints=True)
def model_level_dbt_flow() -> dict[str, Any]:
    """Demonstrate model-level dbt orchestration patterns."""
    logger = get_run_logger()

    project_dir = setup_dbt_project()

    settings = PrefectDbtSettings(
        project_dir=str(project_dir),
        profiles_dir=str(project_dir),
    )
    runner = PrefectDbtRunner(settings=settings, raise_on_failure=False)
    runner.invoke(["deps"])

    # Pattern 1: Run model with upstream dependencies using +model syntax
    logger.info("\n" + "=" * 50)
    logger.info("Pattern 1: Run model with upstream dependencies")
    logger.info("=" * 50)
    result1 = run_dbt_models(project_dir, select="+my_second_dbt_model")

    # Pattern 2: Run model, then conditionally run downstream
    logger.info("\n" + "=" * 50)
    logger.info("Pattern 2: Conditional downstream execution")
    logger.info("=" * 50)
    result2 = run_model_then_downstream(project_dir, "my_first_dbt_model")

    return {
        "with_upstream": result1,
        "conditional_downstream": result2,
    }


if __name__ == "__main__":
    print("Demonstrating model-level dbt orchestration patterns...\n")
    model_level_dbt_flow()
    print("\nDone!")
