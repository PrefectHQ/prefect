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
