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


async def test_mutual_exclusivity():
    await run_sync_in_worker_thread(
        invoke_and_assert,
        [
            "task",
            "serve",
            f"{TEST_PROJECTS_DIR}/tasks/household.py:do_the_dishes",
            "--module",
            "tests.test-projects.tasks.household",
        ],
        expected_code=1,
        expected_output_contains=[
            "You may provide entrypoints or modules, but not both at the same time."
        ],
    )


async def test_module_import_error():
    await run_sync_in_worker_thread(
        invoke_and_assert,
        [
            "task",
            "serve",
            "--module",
            "tests.test-projects.tasks.doesnotexist",
        ],
        expected_code=1,
        expected_output_contains=[
            "Module 'tests.test-projects.tasks.doesnotexist' could not be imported. Please check the module name and try again."
        ],
    )


async def test_single_module():
    with mock.patch(
        "prefect.cli.task.task_serve", new_callable=mock.AsyncMock
    ) as task_serve:
        await run_sync_in_worker_thread(
            invoke_and_assert,
            [
                "task",
                "serve",
                "--module",
                "tests.test-projects.tasks.household",
            ],
            expected_code=0,
        )
        task_serve.assert_awaited_once_with(mock.ANY, limit=10)
        served_tasks = task_serve.call_args_list[0][0]
        assert any(getattr(t, "name", None) == "do_the_dishes" for t in served_tasks)


async def test_multiple_modules():
    with mock.patch(
        "prefect.cli.task.task_serve", new_callable=mock.AsyncMock
    ) as task_serve:
        await run_sync_in_worker_thread(
            invoke_and_assert,
            [
                "task",
                "serve",
                "--module",
                "tests.test-projects.tasks.household",
                "--module",
                "tests.test-projects.tasks.space",
            ],
            expected_code=0,
        )
        task_serve.assert_awaited_once_with(mock.ANY, mock.ANY, limit=10)
        served_tasks = task_serve.call_args_list[0][0]
        assert any(getattr(t, "name", None) == "do_the_dishes" for t in served_tasks)
        assert any(getattr(t, "name", None) == "spacewalk" for t in served_tasks)
