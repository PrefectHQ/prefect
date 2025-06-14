"""Tests for the @materialize decorator."""

import pytest

from prefect.assets import Asset
from prefect.assets.materialize import materialize
from prefect.tasks import MaterializingTask


class TestMaterializeDecorator:
    """Test the @materialize decorator functionality."""

    def test_materialize_without_arguments(self):
        """Test using @materialize without any arguments."""

        @materialize
        def my_task():
            return "hello"

        assert isinstance(my_task, MaterializingTask)
        assert my_task.name == "my_task"
        assert my_task.assets == []
        assert my_task.materialized_by is None

        # Test that the function still works
        result = my_task()
        assert result == "hello"

    def test_materialize_with_single_asset_string(self):
        """Test using @materialize with a single asset string."""

        @materialize("s3://bucket/my_asset.csv")
        def my_task():
            return "hello"

        assert isinstance(my_task, MaterializingTask)
        assert len(my_task.assets) == 1
        assert my_task.assets[0].key == "s3://bucket/my_asset.csv"
        assert isinstance(my_task.assets[0], Asset)

    def test_materialize_with_multiple_asset_strings(self):
        """Test using @materialize with multiple asset strings."""

        @materialize(
            "s3://bucket/asset1.csv",
            "gs://bucket/asset2.parquet",
            "file:///data/asset3.json",
        )
        def my_task():
            return "hello"

        assert isinstance(my_task, MaterializingTask)
        assert len(my_task.assets) == 3
        assert my_task.assets[0].key == "s3://bucket/asset1.csv"
        assert my_task.assets[1].key == "gs://bucket/asset2.parquet"
        assert my_task.assets[2].key == "file:///data/asset3.json"

    def test_materialize_with_asset_objects(self):
        """Test using @materialize with Asset objects."""
        asset1 = Asset(key="s3://bucket/my_asset1.csv")
        asset2 = Asset(key="gs://bucket/my_asset2.parquet")

        @materialize(asset1, asset2)
        def my_task():
            return "hello"

        assert isinstance(my_task, MaterializingTask)
        assert len(my_task.assets) == 2
        assert my_task.assets[0] is asset1
        assert my_task.assets[1] is asset2

    def test_materialize_with_mixed_assets(self):
        """Test using @materialize with both strings and Asset objects."""
        asset1 = Asset(key="s3://bucket/my_asset1.csv")

        @materialize(asset1, "file:///data/string_asset.json")
        def my_task():
            return "hello"

        assert isinstance(my_task, MaterializingTask)
        assert len(my_task.assets) == 2
        assert my_task.assets[0] is asset1
        assert my_task.assets[1].key == "file:///data/string_asset.json"

    def test_materialize_with_by_parameter(self):
        """Test using @materialize with the 'by' parameter."""

        @materialize("s3://bucket/my_asset.csv", by="dbt")
        def my_task():
            return "hello"

        assert isinstance(my_task, MaterializingTask)
        assert my_task.materialized_by == "dbt"

    def test_materialize_with_task_kwargs(self):
        """Test using @materialize with task keyword arguments."""

        @materialize(
            "s3://bucket/my_asset.csv", name="custom_name", description="A test task"
        )
        def my_task():
            return "hello"

        assert isinstance(my_task, MaterializingTask)
        assert my_task.name == "custom_name"
        assert my_task.description == "A test task"

    def test_materialize_with_all_parameters(self):
        """Test using @materialize with assets, by, and task kwargs."""

        @materialize(
            "s3://bucket/asset1.csv",
            "gs://bucket/asset2.parquet",
            by="spark",
            name="spark_task",
            retries=3,
            tags=["etl", "spark"],
        )
        def my_task():
            return "hello"

        assert isinstance(my_task, MaterializingTask)
        assert len(my_task.assets) == 2
        assert my_task.materialized_by == "spark"
        assert my_task.name == "spark_task"
        assert my_task.retries == 3
        assert "etl" in my_task.tags
        assert "spark" in my_task.tags

    def test_materialize_preserves_function_signature(self):
        """Test that @materialize preserves the function signature."""

        @materialize
        def my_task(x: int, y: str = "default") -> str:
            return f"{x} - {y}"

        # Test that the function still works with its original signature
        result = my_task(42)
        assert result == "42 - default"

        result = my_task(42, "custom")
        assert result == "42 - custom"

    def test_materialize_works_with_async_functions(self):
        """Test that @materialize works with async functions."""

        @materialize("s3://bucket/async_asset.csv")
        async def async_task():
            return "async hello"

        assert isinstance(async_task, MaterializingTask)
        assert async_task.isasync is True

    def test_materialize_callable_syntax(self):
        """Test that materialize can be called as a function."""

        def my_task():
            return "hello"

        decorated_task = materialize(my_task)

        assert isinstance(decorated_task, MaterializingTask)
        assert decorated_task.assets == []

    def test_materialize_callable_with_assets(self):
        """Test materialize called as function with assets."""

        def my_task():
            return "hello"

        decorated_task = materialize(
            "s3://bucket/asset1.csv", "gs://bucket/asset2.parquet"
        )(my_task)

        assert isinstance(decorated_task, MaterializingTask)
        assert len(decorated_task.assets) == 2

    def test_materialize_type_hints_preserved(self):
        """Test that type hints are preserved through decoration."""

        @materialize
        def typed_task(x: int) -> int:
            return x * 2

        # This test mainly ensures the decorator doesn't break type checking
        # In practice, type checkers would verify this
        assert typed_task.__annotations__ == {"x": int, "return": int}

    def test_materialize_with_only_kwargs(self):
        """Test using @materialize with only keyword arguments."""

        @materialize(by="custom_tool", name="kwarg_only_task")
        def my_task():
            return "hello"

        assert isinstance(my_task, MaterializingTask)
        assert my_task.assets == []
        assert my_task.materialized_by == "custom_tool"
        assert my_task.name == "kwarg_only_task"

    def test_materialize_error_with_non_callable(self):
        """Test that materialize raises appropriate error with non-callable."""
        # When passing a string directly to materialize, it's treated as an asset
        # and returns a decorator function, not an error
        decorator = materialize("s3://bucket/asset.csv")

        # The error should occur when trying to decorate a non-callable
        with pytest.raises(TypeError, match="must be callable"):
            decorator("not a function")

    def test_materialize_complex_task_kwargs(self):
        """Test materialize with complex task configuration."""
        from datetime import timedelta

        from prefect.tasks import task_input_hash

        @materialize(
            "s3://bucket/cached_asset.csv",
            cache_key_fn=task_input_hash,
            cache_expiration=timedelta(hours=1),
            persist_result=True,
            timeout_seconds=300,
        )
        def complex_task(data: dict) -> dict:
            return {"processed": data}

        assert isinstance(complex_task, MaterializingTask)
        assert complex_task.cache_key_fn == task_input_hash
        assert complex_task.cache_expiration == timedelta(hours=1)
        assert complex_task.persist_result is True
        assert complex_task.timeout_seconds == 300.0
