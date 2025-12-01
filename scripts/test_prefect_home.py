"""
Test script to verify PREFECT_HOME is respected and measure task creation performance.

This script tests:
1. That PREFECT_HOME environment variable is properly respected
2. Task creation performance when mapping tasks
3. Comparison between default and custom PREFECT_HOME locations

Related to issue #19581: Windows performance issues with task mapping
"""

import json
import os
import platform
import sys
import time
from pathlib import Path

from prefect import flow, get_run_logger, task
from prefect.settings import get_current_settings


@task
def dummy_task(x: int) -> int:
    """A simple task that returns its input."""
    return x


@flow
def test_prefect_home_flow(num_tasks: int = 100) -> dict:
    """
    Test flow that maps tasks and measures performance.

    Args:
        num_tasks: Number of tasks to map

    Returns:
        Dictionary with timing results and PREFECT_HOME info
    """
    logger = get_run_logger()
    settings = get_current_settings()

    # Log PREFECT_HOME information
    prefect_home = settings.home
    prefect_home_env = os.environ.get("PREFECT_HOME", "not set")

    logger.info(f"PREFECT_HOME env var: {prefect_home_env}")
    logger.info(f"Settings home path: {prefect_home}")
    logger.info(f"Settings home exists: {prefect_home.exists()}")

    # Verify PREFECT_HOME is respected
    if prefect_home_env != "not set":
        expected_path = Path(prefect_home_env).expanduser().resolve()
        actual_path = prefect_home.resolve()
        if expected_path != actual_path:
            logger.warning(
                f"PREFECT_HOME mismatch! Expected: {expected_path}, Got: {actual_path}"
            )
        else:
            logger.info("PREFECT_HOME is correctly respected")

    # Measure task mapping time
    logger.info(f"Starting to map {num_tasks} tasks...")
    start_map = time.perf_counter()
    futures = dummy_task.map(range(num_tasks))
    map_time = time.perf_counter() - start_map
    logger.info(f"Mapping {num_tasks} tasks took: {map_time:.4f}s")

    # Measure wait time
    start_wait = time.perf_counter()
    futures.wait()
    wait_time = time.perf_counter() - start_wait
    logger.info(f"Waiting for {num_tasks} tasks took: {wait_time:.4f}s")

    # Calculate per-task times
    per_task_map_time = (map_time / num_tasks) * 1000  # ms
    per_task_wait_time = (wait_time / num_tasks) * 1000  # ms

    logger.info(f"Per-task map time: {per_task_map_time:.4f}ms")
    logger.info(f"Per-task wait time: {per_task_wait_time:.4f}ms")

    results = {
        "prefect_home_env": prefect_home_env,
        "prefect_home_resolved": str(prefect_home),
        "prefect_home_exists": prefect_home.exists(),
        "num_tasks": num_tasks,
        "map_time_seconds": map_time,
        "wait_time_seconds": wait_time,
        "per_task_map_time_ms": per_task_map_time,
        "per_task_wait_time_ms": per_task_wait_time,
        "total_time_seconds": map_time + wait_time,
    }

    return results


def main():
    """Run the test and print results."""
    print(f"Platform: {platform.system()} {platform.release()}")
    print(f"Python: {sys.version}")
    print(f"PREFECT_HOME env: {os.environ.get('PREFECT_HOME', 'not set')}")
    print("-" * 60)

    # Run the test flow
    results = test_prefect_home_flow(num_tasks=100)

    print("-" * 60)
    print("Results:")
    print(json.dumps(results, indent=2, default=str))

    # Output for GitHub Actions
    github_output = os.environ.get("GITHUB_OUTPUT")
    if github_output:
        with open(github_output, "a") as f:
            f.write(f"map_time={results['map_time_seconds']:.4f}\n")
            f.write(f"wait_time={results['wait_time_seconds']:.4f}\n")
            f.write(f"total_time={results['total_time_seconds']:.4f}\n")
            f.write(f"per_task_map_ms={results['per_task_map_time_ms']:.4f}\n")

    return results


if __name__ == "__main__":
    main()
