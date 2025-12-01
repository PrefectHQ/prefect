"""
Test script to measure task mapping and submitting performance.

This script measures:
1. Time to map N tasks using task.map()
2. Time to wait for mapped tasks to complete
3. Time to submit tasks one-by-one using task.submit()

Related to issue #19581: Windows is 2x slower to create tasks when mapping or submitting
"""

import json
import os
import platform
import sys
import time

from prefect import flow, get_run_logger, task


@task
def dummy_task(x: int) -> int:
    """A simple task that returns its input."""
    return x


@flow
def test_mapping_performance(num_tasks: int = 100) -> dict:
    """
    Test flow that maps tasks and measures performance.

    Args:
        num_tasks: Number of tasks to map

    Returns:
        Dictionary with timing results
    """
    logger = get_run_logger()

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
    per_task_map_time_ms = (map_time / num_tasks) * 1000
    per_task_wait_time_ms = (wait_time / num_tasks) * 1000

    logger.info(f"Per-task map time: {per_task_map_time_ms:.4f}ms")
    logger.info(f"Per-task wait time: {per_task_wait_time_ms:.4f}ms")

    return {
        "test_type": "mapping",
        "num_tasks": num_tasks,
        "map_time_seconds": map_time,
        "wait_time_seconds": wait_time,
        "per_task_map_time_ms": per_task_map_time_ms,
        "per_task_wait_time_ms": per_task_wait_time_ms,
        "total_time_seconds": map_time + wait_time,
    }


@flow
def test_submitting_performance(num_tasks: int = 100) -> dict:
    """
    Test flow that submits tasks one-by-one and measures performance.

    This separates submission time from waiting time to isolate the
    task creation cost.

    Args:
        num_tasks: Number of tasks to submit

    Returns:
        Dictionary with timing results
    """
    logger = get_run_logger()

    # First, measure just the submission time (creating futures)
    logger.info(f"Starting to submit {num_tasks} tasks...")
    futures = []
    start_submit = time.perf_counter()

    for i in range(num_tasks):
        future = dummy_task.submit(i)
        futures.append(future)

    submit_time = time.perf_counter() - start_submit
    logger.info(f"Submitting {num_tasks} tasks took: {submit_time:.4f}s")

    # Then, measure the waiting time separately
    start_wait = time.perf_counter()
    for future in futures:
        future.wait()
    wait_time = time.perf_counter() - start_wait
    logger.info(f"Waiting for {num_tasks} tasks took: {wait_time:.4f}s")

    per_task_submit_time_ms = (submit_time / num_tasks) * 1000
    per_task_wait_time_ms = (wait_time / num_tasks) * 1000

    logger.info(f"Per-task submit time: {per_task_submit_time_ms:.4f}ms")
    logger.info(f"Per-task wait time: {per_task_wait_time_ms:.4f}ms")

    return {
        "test_type": "submitting",
        "num_tasks": num_tasks,
        "submit_time_seconds": submit_time,
        "wait_time_seconds": wait_time,
        "per_task_submit_time_ms": per_task_submit_time_ms,
        "per_task_wait_time_ms": per_task_wait_time_ms,
        "total_time_seconds": submit_time + wait_time,
    }


def main():
    """Run the performance tests and print results."""
    print("=" * 60)
    print("Windows Mapping Performance Test")
    print("=" * 60)
    print(f"Platform: {platform.system()} {platform.release()}")
    print(f"Python: {sys.version}")
    print("=" * 60)

    num_tasks = int(os.environ.get("NUM_TASKS", "100"))

    # Run mapping test
    print("\n--- Test 1: Mapping Performance ---")
    mapping_results = test_mapping_performance(num_tasks=num_tasks)

    # Run submitting test
    print("\n--- Test 2: Submitting Performance ---")
    submitting_results = test_submitting_performance(num_tasks=num_tasks)

    # Combine results
    results = {
        "platform": platform.system(),
        "platform_release": platform.release(),
        "python_version": platform.python_version(),
        "num_tasks": num_tasks,
        "mapping": mapping_results,
        "submitting": submitting_results,
    }

    print("\n" + "=" * 60)
    print("Final Results:")
    print("=" * 60)
    print(json.dumps(results, indent=2))

    # Output for GitHub Actions summary
    github_step_summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if github_step_summary:
        with open(github_step_summary, "a") as f:
            f.write(f"## Performance Results ({platform.system()})\n\n")
            f.write("| Metric | Value |\n")
            f.write("|--------|-------|\n")
            f.write(f"| Platform | {platform.system()} {platform.release()} |\n")
            f.write(f"| Python | {platform.python_version()} |\n")
            f.write(f"| Number of tasks | {num_tasks} |\n")
            f.write("| **Mapping** | |\n")
            f.write(f"| Map time | {mapping_results['map_time_seconds']:.4f}s |\n")
            f.write(f"| Wait time | {mapping_results['wait_time_seconds']:.4f}s |\n")
            f.write(
                f"| Per-task map time | {mapping_results['per_task_map_time_ms']:.4f}ms |\n"
            )
            f.write("| **Submitting** | |\n")
            f.write(
                f"| Submit time | {submitting_results['submit_time_seconds']:.4f}s |\n"
            )
            f.write(f"| Wait time | {submitting_results['wait_time_seconds']:.4f}s |\n")
            f.write(
                f"| Per-task submit time | {submitting_results['per_task_submit_time_ms']:.4f}ms |\n"
            )
            f.write("\n")

    # Output for GitHub Actions
    github_output = os.environ.get("GITHUB_OUTPUT")
    if github_output:
        with open(github_output, "a") as f:
            f.write(f"map_time={mapping_results['map_time_seconds']:.4f}\n")
            f.write(f"wait_time={mapping_results['wait_time_seconds']:.4f}\n")
            f.write(f"submit_time={submitting_results['submit_time_seconds']:.4f}\n")

    return results


if __name__ == "__main__":
    main()
