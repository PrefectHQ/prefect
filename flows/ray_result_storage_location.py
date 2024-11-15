"""This is a regression test for https://github.com/PrefectHQ/prefect/issues/16009"""

from pathlib import Path

from prefect_ray import RayTaskRunner

from prefect import flow, get_run_logger, task
from prefect.cache_policies import NONE
from prefect.results import ResultRecord
from prefect.settings import (
    PREFECT_LOCAL_STORAGE_PATH,
    PREFECT_RESULTS_PERSIST_BY_DEFAULT,
    temporary_settings,
)


@task(result_storage_key="test-key", cache_policy=NONE)
def task_a():
    logger = get_run_logger()
    current_storage_path = PREFECT_LOCAL_STORAGE_PATH.value()
    logger.info(f"Task running with storage path: {current_storage_path}")
    return 42


@flow(task_runner=RayTaskRunner)
def my_flow():
    state = task_a.submit(return_state=True)
    return state.result()


if __name__ == "__main__":
    # Create a temporary directory for test results
    tmp_path = Path("test_results")
    tmp_path.mkdir(exist_ok=True)

    try:
        with temporary_settings(
            {
                PREFECT_RESULTS_PERSIST_BY_DEFAULT: True,
                PREFECT_LOCAL_STORAGE_PATH: str(tmp_path),
            },
        ):
            my_flow()

            # Check result file exists in correct location
            result_file = tmp_path / "test-key"
            assert result_file.exists(), f"Result file not found at {result_file}"

            # Verify file contents using ResultRecord deserialization
            record = ResultRecord.deserialize(result_file.read_bytes())
            result = record.result
            assert result == 42

            # Verify no files exist in CWD
            cwd_result = Path.cwd() / "test-key"
            assert not cwd_result.exists(), f"Found unexpected result file in current working directory: {cwd_result}"

            # List all files in tmp_path for debugging
            found_files = list(tmp_path.glob("**/*"))
            assert len(found_files) == 2, (
                f"Expected exactly two files in {tmp_path}, "
                f"found {len(found_files)}: {found_files!r}"
            )
            assert any(
                f.name == "test-key" for f in found_files
            ), f"Expected to find 'test-key' in {found_files!r}"

        print("Result storage location test passed!")
    finally:
        # Clean up test directory
        import shutil

        shutil.rmtree(tmp_path)
