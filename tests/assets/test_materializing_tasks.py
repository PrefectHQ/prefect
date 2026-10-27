import pytest

from prefect.assets import Asset, materialize
from prefect.cache_policies import DEFAULT


class TestMaterializingTask:
    def test_with_options_assets_parameter_keeps_existing(self):
        @materialize("storage://original/asset.csv", persist_result=True)
        def initial_task():
            pass

        task_with_options = initial_task.with_options(persist_result=False)

        assert task_with_options.assets == [Asset(key="storage://original/asset.csv")]
        assert not task_with_options.persist_result

    def test_with_options_assets_takes_precedence_over_existing(self):
        @materialize("storage://foo/bar/asset.csv", persist_result=False)
        def initial_task():
            pass

        task_with_options = initial_task.with_options(
            assets=["storage://foo/baz/asset.csv"]
        )

        assert task_with_options.assets == [Asset(key="storage://foo/baz/asset.csv")]
        assert not task_with_options.persist_result

    def test_with_options_assets_allows_both(self):
        @materialize("storage://foo/bar/asset.csv", persist_result=False)
        def initial_task():
            pass

        task_with_options = initial_task.with_options(
            assets=["storage://foo/baz/asset.csv"], persist_result=True
        )

        assert task_with_options.assets == [Asset(key="storage://foo/baz/asset.csv")]
        assert task_with_options.persist_result

    def test_with_options_preserves_user_provided_persist_result_and_cache_policy(self):
        @materialize("storage://original/asset.csv")
        def initial_task():
            pass

        assert initial_task.cache_policy == DEFAULT
        assert initial_task.persist_result is None
        assert initial_task._user_persist_result is None

        task_with_options = initial_task.with_options(name="something")

        assert task_with_options.cache_policy == DEFAULT
        assert task_with_options.persist_result is None
        assert task_with_options._user_persist_result is None

    @pytest.mark.parametrize(
        "hook_name",
        ["on_completion", "on_failure", "on_running", "on_rollback", "on_commit"],
    )
    def test_with_options_hooks_are_copied_from_original_task(self, hook_name: str):
        "Ensure hooks added to the new task don't affect the original task"

        def original_hook(task, task_run, state):
            pass

        def added_hook(task, task_run, state):
            pass

        @materialize("storage://original/asset.csv", **{hook_name: [original_hook]})
        def initial_task():
            pass

        task_with_options = initial_task.with_options(name="With options task")
        getattr(task_with_options, hook_name)(added_hook)

        assert getattr(initial_task, f"{hook_name}_hooks") == [original_hook]
        assert getattr(task_with_options, f"{hook_name}_hooks") == [
            original_hook,
            added_hook,
        ]
