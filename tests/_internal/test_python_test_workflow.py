import itertools
import re
from collections import Counter
from pathlib import Path
from typing import Any

import pytest
import yaml

REPOSITORY_ROOT = Path(__file__).parents[2]
PYTHON_TEST_WORKFLOW = REPOSITORY_ROOT / ".github/workflows/python-tests.yaml"
DURATION_TIMING_PYTHON_VERSION = "3.12"


@pytest.fixture(scope="module")
def jobs() -> dict[str, Any]:
    return yaml.safe_load(PYTHON_TEST_WORKFLOW.read_text())["jobs"]


def expand_matrix(job: dict[str, Any]) -> list[dict[str, Any]]:
    """Expand a job matrix the way GitHub Actions does for `exclude`."""
    matrix = job["strategy"]["matrix"]
    assert "include" not in matrix, "matrix include is not supported by this helper"

    dimensions = {
        key: values for key, values in matrix.items() if key not in {"exclude"}
    }
    combinations = [
        dict(zip(dimensions, values))
        for values in itertools.product(*dimensions.values())
    ]
    return [
        combination
        for combination in combinations
        if not any(
            all(combination.get(key) == value for key, value in exclude.items())
            for exclude in matrix.get("exclude", [])
        )
    ]


def get_step(job: dict[str, Any], step_id: str) -> dict[str, Any]:
    for step in job["steps"]:
        if step.get("id") == step_id:
            return step
    pytest.fail(f"step {step_id!r} not found")


def test_static_test_types_do_not_run_on_postgres(jobs: dict[str, Any]):
    databases = {
        combination["database"] for combination in expand_matrix(jobs["run-tests"])
    }

    assert databases == {"sqlite"}


def test_every_python_version_runs_each_postgres_group_once(jobs: dict[str, Any]):
    balanced_job = jobs["run-canonical-tests"]
    split_count = re.search(
        r"--splits (\d+)", get_step(balanced_job, "canonical_tests")["run"]
    )
    assert split_count
    python_versions = {
        combination["python-version"]
        for combination in expand_matrix(jobs["run-tests"])
    }

    groups = Counter(
        (combination["python-version"], combination["database"], combination["group"])
        for combination in expand_matrix(balanced_job)
    )

    assert groups == Counter(
        (python_version, "postgres:14", group)
        for python_version in python_versions
        for group in range(1, int(split_count.group(1)) + 1)
    )


def test_only_one_python_version_publishes_group_durations(jobs: dict[str, Any]):
    balanced_job = jobs["run-canonical-tests"]
    publishing_steps = [
        step
        for step in balanced_job["steps"]
        if step.get("uses", "").startswith("actions/upload-artifact@")
    ]
    validation_condition = get_step(balanced_job, "validate_canonical_durations")["if"]

    assert re.search(
        rf"matrix\.python-version == '{re.escape(DURATION_TIMING_PYTHON_VERSION)}'",
        validation_condition,
    )
    assert publishing_steps
    for step in publishing_steps:
        assert "steps.validate_canonical_durations.outcome == 'success'" in step["if"]
