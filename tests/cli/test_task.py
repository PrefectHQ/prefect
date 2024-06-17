from unittest import mock

from prefect import __development_base_path__
from prefect.testing.cli import invoke_and_assert
from prefect.utilities.asyncutils import run_sync_in_worker_thread

TEST_PROJECTS_DIR = __development_base_path__ / "tests" / "test-projects"


async def test_invalid_entrypoint():
    await run_sync_in_worker_thread(
        invoke_and_assert,
        [
            "task",
            "serve",
            "file.py",
        ],
        expected_code=1,
        expected_output_contains=[
            (
                "Error: Invalid entrypoint format 'file.py'. It "
                "must be of the form `./path/to/file.py:task_func_name`."
            )
        ],
    )


async def test_import_failure():
    await run_sync_in_worker_thread(
        invoke_and_assert,
        [
            "task",
            "serve",
            "file.py:nope_not_a_chance",
        ],
        expected_code=1,
        expected_output_contains=[
            "Error: 'file.py' has no function 'nope_not_a_chance'."
        ],
    )


async def test_single_entrypoint():
    with mock.patch(
        "prefect.cli.task.task_serve", new_callable=mock.AsyncMock
    ) as task_serve:
        await run_sync_in_worker_thread(
            invoke_and_assert,
            [
                "task",
                "serve",
                f"{TEST_PROJECTS_DIR}/tasks/household.py:do_the_dishes",
            ],
            expected_code=0,
        )

        task_serve.assert_awaited_once_with(mock.ANY, limit=10)
        served_tasks = task_serve.call_args_list[0][0]
        assert len(served_tasks) == 1
        assert served_tasks[0].name == "do_the_dishes"


async def test_multiple_entrypoints():
    with mock.patch(
        "prefect.cli.task.task_serve", new_callable=mock.AsyncMock
    ) as task_serve:
        await run_sync_in_worker_thread(
            invoke_and_assert,
            [
                "task",
                "serve",
                f"{TEST_PROJECTS_DIR}/tasks/household.py:do_the_dishes",
                f"{TEST_PROJECTS_DIR}/tasks/space.py:spacewalk",
            ],
            expected_code=0,
        )

        task_serve.assert_awaited_once_with(mock.ANY, mock.ANY, limit=10)
        served_tasks = task_serve.call_args_list[0][0]
        assert len(served_tasks) == 2
        assert served_tasks[0].name == "do_the_dishes"
        assert served_tasks[1].name == "spacewalk"
