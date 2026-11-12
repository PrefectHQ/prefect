import fnmatch
import importlib.util
import itertools
import json
import os
import re
import shutil
import subprocess
from collections import Counter
from pathlib import Path
from typing import Any

import pytest
import yaml

REPOSITORY_ROOT = Path(__file__).parents[2]
PYTHON_TEST_WORKFLOW = REPOSITORY_ROOT / ".github/workflows/python-tests.yaml"
DURATION_TIMING_PYTHON_VERSION = "3.12"

# (prepare job, test job, save job, database) for each duration namespace
DURATION_PIPELINES = {
    "postgres": (
        "prepare-canonical-test-durations",
        "run-canonical-tests",
        "save-canonical-test-durations",
        "postgres:14",
    ),
    "sqlite": (
        "prepare-sqlite-test-durations",
        "run-tests",
        "save-sqlite-test-durations",
        "sqlite",
    ),
}

requires_jq = pytest.mark.skipif(
    shutil.which("jq") is None or shutil.which("bash") is None,
    reason="workflow scripts require bash and jq",
)


@pytest.fixture(scope="module")
def jobs() -> dict[str, Any]:
    return yaml.safe_load(PYTHON_TEST_WORKFLOW.read_text())["jobs"]


@pytest.fixture(scope="module")
def verify_test_selection() -> Any:
    spec = importlib.util.spec_from_file_location(
        "verify_test_selection", REPOSITORY_ROOT / "scripts/verify_test_selection.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


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


def get_step(
    job: dict[str, Any], *, step_id: str | None = None, name: str | None = None
) -> dict[str, Any]:
    for step in job["steps"]:
        if (step_id and step.get("id") == step_id) or (
            name and step.get("name") == name
        ):
            return step
    pytest.fail(f"step {step_id or name!r} not found")


def run_step(
    job: dict[str, Any], step: dict[str, Any], cwd: Path, group: int = 1
) -> subprocess.CompletedProcess[str]:
    environment = os.environ | {k: str(v) for k, v in job["env"].items()}
    script = step["run"].replace("${{ matrix.group }}", str(group))
    return subprocess.run(
        ["bash", "--noprofile", "--norc", "-e", "-o", "pipefail", "-c", script],
        cwd=cwd,
        env=environment,
        capture_output=True,
        check=False,
        text=True,
    )


def test_regular_tests_run_each_duration_group_once_per_python_version(
    jobs: dict[str, Any],
):
    python_versions = set(
        jobs["run-canonical-tests"]["strategy"]["matrix"]["python-version"]
    )
    regular_jobs = 0

    for _, test_job_name, _, database in DURATION_PIPELINES.values():
        test_job = jobs[test_job_name]
        group_count = int(test_job["env"]["DURATION_GROUP_COUNT"])
        combinations = expand_matrix(test_job)
        regular_jobs += len(combinations)

        assert Counter(
            (c["python-version"], c["database"], c["group"]) for c in combinations
        ) == Counter(
            (python_version, database, group)
            for python_version in python_versions
            for group in range(1, group_count + 1)
        )

    assert int(jobs["run-tests"]["env"]["DURATION_GROUP_COUNT"]) == 8
    assert regular_jobs == len(python_versions) * (8 + 18)


def test_sqlite_runs_only_the_server_test_selection(jobs: dict[str, Any]):
    step = get_step(jobs["run-tests"], step_id="group_tests")

    # The union of the former server, database, orchestration-core, and
    # orchestration-api SQLite test types.
    assert step["env"]["PYTEST_SELECTION"].split() == [
        "tests/server/",
        "tests/events/server",
    ]


def test_duration_namespaces_are_isolated(jobs: dict[str, Any]):
    namespaces = {}
    for name, (prepare, test, save, _) in DURATION_PIPELINES.items():
        assert jobs[prepare]["env"] == jobs[test]["env"] == jobs[save]["env"]
        assert jobs[test]["needs"] == prepare
        assert jobs[save]["needs"] == test
        namespaces[name] = jobs[test]["env"]

    # Postgres keeps the cache and artifact names it published before SQLite
    # used duration groups.
    assert namespaces["postgres"] == {
        "DURATION_CACHE_KEY_PREFIX": "pytest-split-v1-python-3.12-postgres-14-",
        "DURATION_BASELINE_ARTIFACT": "canonical-test-duration-baseline",
        "DURATION_ARTIFACT_PREFIX": "canonical-test-durations",
        "DURATION_GROUP_COUNT": "18",
    }
    for this, other in itertools.permutations(namespaces.values()):
        assert not other["DURATION_CACHE_KEY_PREFIX"].startswith(
            this["DURATION_CACHE_KEY_PREFIX"]
        )
        group_pattern = f"{this['DURATION_ARTIFACT_PREFIX']}-*"
        for artifact in (
            other["DURATION_BASELINE_ARTIFACT"],
            other["DURATION_ARTIFACT_PREFIX"],
            f"{other['DURATION_ARTIFACT_PREFIX']}-1",
        ):
            assert not fnmatch.fnmatchcase(artifact, group_pattern)
            assert artifact != this["DURATION_BASELINE_ARTIFACT"]
    for namespace in namespaces.values():
        assert not fnmatch.fnmatchcase(
            namespace["DURATION_BASELINE_ARTIFACT"],
            f"{namespace['DURATION_ARTIFACT_PREFIX']}-*",
        )


@pytest.mark.parametrize("database", DURATION_PIPELINES)
def test_only_one_python_version_publishes_group_durations(
    jobs: dict[str, Any], database: str
):
    test_job = jobs[DURATION_PIPELINES[database][1]]
    publishing_steps = [
        step
        for step in test_job["steps"]
        if step.get("uses", "").startswith("actions/upload-artifact@")
    ]
    validation_condition = get_step(test_job, step_id="validate_group_durations")["if"]

    assert re.search(
        rf"matrix\.python-version == '{re.escape(DURATION_TIMING_PYTHON_VERSION)}'",
        validation_condition,
    )
    assert publishing_steps
    for step in publishing_steps:
        assert "steps.validate_group_durations.outcome == 'success'" in step["if"]


@requires_jq
@pytest.mark.parametrize(
    ("durations", "valid"),
    [
        ({"tests/server/test_a.py::test_a": 0.5}, True),
        ({}, False),
        (
            {"tests/server/test_a.py::test_a": 0.5, "__pytest_split_incomplete__": -1},
            False,
        ),
        ({"tests/server/test_a.py::test_a": -1}, False),
        ({"tests/server/test_a.py::test_a": "1"}, False),
        ({"": 1}, False),
    ],
)
def test_group_duration_validation(
    jobs: dict[str, Any], tmp_path: Path, durations: dict[str, Any], valid: bool
):
    test_job = jobs["run-tests"]
    (tmp_path / "test-durations-3.json").write_text(json.dumps(durations))

    result = run_step(
        test_job, get_step(test_job, step_id="validate_group_durations"), tmp_path, 3
    )

    assert (result.returncode == 0) is valid, result.stderr


@requires_jq
@pytest.mark.parametrize("baseline", [None, "not json", '{"a": -1}', "[]"])
def test_prepare_falls_back_to_count_splitting_without_valid_baseline(
    jobs: dict[str, Any], tmp_path: Path, baseline: str | None
):
    prepare_job = jobs["prepare-sqlite-test-durations"]
    if baseline is not None:
        (tmp_path / "test-durations.json").write_text(baseline)

    result = run_step(
        prepare_job, get_step(prepare_job, name="Validate test durations"), tmp_path
    )

    assert result.returncode == 0, result.stderr
    assert json.loads((tmp_path / "test-durations.json").read_text()) == {}


@requires_jq
@pytest.mark.parametrize(
    ("group_files", "merged"),
    [
        ({group: {f"t{group}": group} for group in range(1, 9)}, True),
        ({group: {f"t{group}": group} for group in range(1, 8)}, False),
        ({group: {"t": group} for group in range(1, 9)}, False),
    ],
    ids=["complete", "missing-group", "duplicate-node"],
)
def test_sqlite_save_merges_only_complete_unique_groups(
    jobs: dict[str, Any],
    tmp_path: Path,
    group_files: dict[int, dict[str, float]],
    merged: bool,
):
    save_job = jobs["save-sqlite-test-durations"]
    (tmp_path / "test-duration-groups").mkdir()
    for group, durations in group_files.items():
        (tmp_path / f"test-duration-groups/test-durations-{group}.json").write_text(
            json.dumps(durations)
        )

    result = run_step(
        save_job, get_step(save_job, name="Merge group test durations"), tmp_path
    )

    assert (result.returncode == 0) is merged, result.stderr
    if merged:
        assert json.loads((tmp_path / "test-durations.json").read_text()) == {
            f"t{group}": group for group in range(1, 9)
        }


def test_selection_guard_reads_selection_consumed_by_regular_jobs(
    jobs: dict[str, Any], verify_test_selection: Any
):
    assert verify_test_selection.regular_test_selections(jobs) == [
        get_step(jobs[name], step_id="group_tests")["env"]["PYTEST_SELECTION"]
        for name in verify_test_selection.REGULAR_TEST_JOBS
    ]

    unconsumed = json.loads(json.dumps(jobs))
    step = get_step(unconsumed["run-tests"], step_id="group_tests")
    step["run"] = step["run"].replace("$PYTEST_SELECTION", "tests/server/")
    with pytest.raises(ValueError, match="run-tests"):
        verify_test_selection.regular_test_selections(unconsumed)


def test_selection_guard_reports_files_omitted_from_regular_jobs(
    verify_test_selection: Any,
):
    assert verify_test_selection.uncovered_test_files(
        {"tests/server/test_a.py", "tests/cli/test_b.py", "tests/test_c.py"},
        ["tests/server/", "tests --ignore=tests/cli/"],
    ) == ["tests/cli/test_b.py"]
