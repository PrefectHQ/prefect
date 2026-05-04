import uuid
from typing import Generator
from unittest.mock import AsyncMock, MagicMock

import pytest
from prefect_gcp.decorators import cloud_run, vertex_ai
from prefect_gcp.workers.cloud_run_v2 import CloudRunWorkerV2
from prefect_gcp.workers.vertex import VertexAIWorker

import prefect
from prefect.client.schemas.actions import WorkPoolCreate
from prefect.client.schemas.objects import WorkPool, WorkPoolStorageConfiguration
from prefect.futures import PrefectFuture


class TestCloudRunDecorator:
    @pytest.fixture
    def mock_submit(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> Generator[AsyncMock, None, None]:
        """Create a mock for the CloudRunWorkerV2.submit method"""
        # Create a mock state
        mock_state = MagicMock(spec=prefect.State)
        mock_state.is_completed.return_value = True
        mock_state.message = "Success"

        # Create a mock future
        mock_future = MagicMock(spec=PrefectFuture)
        mock_future.aresult = AsyncMock(return_value="test_result")
        mock_future.wait_async = AsyncMock()
        mock_future.state = mock_state

        mock = AsyncMock(return_value=mock_future)

        monkeypatch.setattr(CloudRunWorkerV2, "submit", mock)
        yield mock

    @pytest.fixture
    async def work_pool_without_storage_configuration(self):
        async with prefect.get_client() as client:
            work_pool = await client.create_work_pool(
                WorkPoolCreate(
                    name=f"test-{uuid.uuid4()}",
                    base_job_template=CloudRunWorkerV2.get_default_base_job_template(),
                )
            )
            try:
                yield work_pool
            finally:
                await client.delete_work_pool(work_pool.name)

    @pytest.fixture
    async def work_pool_with_storage_configuration(self):
        UPLOAD_STEP = {
            "prefect_mock.experimental.bundles.upload": {
                "requires": "prefect-mock==0.5.5",
                "bucket": "test-bucket",
                "credentials_block_name": "my-creds",
            }
        }

        EXECUTE_STEP = {
            "prefect_mock.experimental.bundles.execute": {
                "requires": "prefect-mock==0.5.5",
                "bucket": "test-bucket",
                "credentials_block_name": "my-creds",
            }
        }

        async with prefect.get_client() as client:
            work_pool = await client.create_work_pool(
                WorkPoolCreate(
                    name=f"test-{uuid.uuid4()}",
                    base_job_template=CloudRunWorkerV2.get_default_base_job_template(),
                    storage_configuration=WorkPoolStorageConfiguration(
                        bundle_execution_step=EXECUTE_STEP,
                        bundle_upload_step=UPLOAD_STEP,
                    ),
                )
            )
            try:
                yield work_pool
            finally:
                await client.delete_work_pool(work_pool.name)

    def test_cloud_run_decorator_sync_flow(self, mock_submit: AsyncMock) -> None:
        """Test that a synchronous flow is correctly decorated and executed"""

        @cloud_run(work_pool="test-pool", memory="2Gi")
        @prefect.flow
        def sync_test_flow(param1: str, param2: str = "default") -> str:
            return f"{param1}-{param2}"

        result = sync_test_flow("test")

        mock_submit.assert_called_once()
        _args, kwargs = mock_submit.call_args
        assert kwargs["parameters"] == {"param1": "test", "param2": "default"}
        assert kwargs["job_variables"] == {"memory": "2Gi"}
        assert result == "test_result"

    async def test_cloud_run_decorator_async_flow(self, mock_submit: AsyncMock) -> None:
        """Test that an asynchronous flow is correctly decorated and executed"""

        @cloud_run(work_pool="test-pool", cpu="1")
        @prefect.flow
        async def async_test_flow(param1: str) -> str:
            return f"async-{param1}"

        result = await async_test_flow("test")

        mock_submit.assert_called_once()
        _args, kwargs = mock_submit.call_args
        assert kwargs["parameters"] == {"param1": "test"}
        assert kwargs["job_variables"] == {"cpu": "1"}
        assert result == "test_result"

    @pytest.mark.usefixtures("mock_submit")
    def test_cloud_run_decorator_return_state(self) -> None:
        """Test that return_state=True returns the state instead of the result"""

        @cloud_run(work_pool="test-pool")
        @prefect.flow
        def test_flow():
            return "completed"

        state = test_flow(return_state=True)

        assert state.is_completed()
        assert state.message == "Success"

    @pytest.mark.usefixtures("mock_submit")
    def test_cloud_run_decorator_preserves_flow_attributes(self) -> None:
        """Test that the decorator preserves the original flow's attributes"""

        @prefect.flow(name="custom-flow-name", description="Custom description")
        def original_flow():
            return "test"

        original_name = original_flow.name
        original_description = original_flow.description

        decorated_flow = cloud_run(work_pool="test-pool")(original_flow)

        assert decorated_flow.name == original_name
        assert decorated_flow.description == original_description

        result = decorated_flow()
        assert result == "test_result"

    def test_submit_method_receives_work_pool_name(
        self, mock_submit: AsyncMock
    ) -> None:
        """Test that the correct work pool name is passed to submit"""

        @cloud_run(work_pool="specific-pool")
        @prefect.flow
        def test_flow():
            return "test"

        test_flow()

        mock_submit.assert_called_once()
        kwargs = mock_submit.call_args.kwargs
        assert "flow" in kwargs
        assert "parameters" in kwargs
        assert "job_variables" in kwargs

    def test_runtime_error_when_work_pool_is_missing_storage_configuration(
        self,
        work_pool_without_storage_configuration: WorkPool,
    ) -> None:
        """Test that a runtime error is raised when the work pool is missing a storage configuration"""

        @cloud_run(work_pool=work_pool_without_storage_configuration.name)
        @prefect.flow
        def test_flow():
            return "test"

        with pytest.raises(
            RuntimeError,
            match=f"Storage is not configured for work pool {work_pool_without_storage_configuration.name!r}. "
            "Please configure storage for the work pool by running `prefect work-pool storage configure`.",
        ):
            test_flow()


class TestCloudRunDecoratorIncludeFiles:
    """Tests for the include_files parameter of the @cloud_run decorator"""

    @pytest.fixture
    def mock_submit(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> Generator[AsyncMock, None, None]:
        mock_state = MagicMock(spec=prefect.State)
        mock_state.is_completed.return_value = True
        mock_state.message = "Success"
        mock_future = MagicMock(spec=PrefectFuture)
        mock_future.aresult = AsyncMock(return_value="test_result")
        mock_future.wait_async = AsyncMock()
        mock_future.state = mock_state
        mock = AsyncMock(return_value=mock_future)
        monkeypatch.setattr(CloudRunWorkerV2, "submit", mock)
        yield mock

    def test_include_files_none_passes_none_to_bound_flow(
        self, mock_submit: AsyncMock
    ) -> None:
        @cloud_run(work_pool="test-pool")
        @prefect.flow
        def test_flow():
            return "test"

        assert test_flow.include_files is None

    def test_include_files_empty_list_passes_empty_list(
        self, mock_submit: AsyncMock
    ) -> None:
        @cloud_run(work_pool="test-pool", include_files=[])
        @prefect.flow
        def test_flow():
            return "test"

        assert test_flow.include_files == []

    def test_include_files_with_valid_strings(self, mock_submit: AsyncMock) -> None:
        @cloud_run(work_pool="test-pool", include_files=["config.yaml", "data/"])
        @prefect.flow
        def test_flow():
            return "test"

        assert test_flow.include_files == ["config.yaml", "data/"]

    def test_include_files_tuple_converted_to_list(
        self, mock_submit: AsyncMock
    ) -> None:
        @cloud_run(work_pool="test-pool", include_files=("a.txt", "b.txt"))
        @prefect.flow
        def test_flow():
            return "test"

        assert test_flow.include_files == ["a.txt", "b.txt"]
        assert isinstance(test_flow.include_files, list)

    def test_include_files_non_string_item_raises_value_error(self) -> None:
        with pytest.raises(
            ValueError, match=r"include_files\[1\] must be a string, got int"
        ):

            @cloud_run(work_pool="test-pool", include_files=["valid", 123])
            @prefect.flow
            def test_flow():
                return "test"

    def test_include_files_empty_string_raises_value_error(self) -> None:
        with pytest.raises(
            ValueError, match=r"include_files\[0\] cannot be empty or whitespace-only"
        ):

            @cloud_run(work_pool="test-pool", include_files=[""])
            @prefect.flow
            def test_flow():
                return "test"

    def test_include_files_whitespace_only_raises_value_error(self) -> None:
        with pytest.raises(
            ValueError, match=r"include_files\[1\] cannot be empty or whitespace-only"
        ):

            @cloud_run(work_pool="test-pool", include_files=["valid", "  "])
            @prefect.flow
            def test_flow():
                return "test"

    def test_include_files_none_type_item_raises_value_error(self) -> None:
        with pytest.raises(
            ValueError, match=r"include_files\[0\] must be a string, got NoneType"
        ):

            @cloud_run(work_pool="test-pool", include_files=[None])  # type: ignore[list-item]
            @prefect.flow
            def test_flow():
                return "test"


class TestVertexAIDecorator:
    @pytest.fixture
    def mock_submit(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> Generator[AsyncMock, None, None]:
        """Create a mock for the VertexAIWorker.submit method"""
        # Create a mock state
        mock_state = MagicMock(spec=prefect.State)
        mock_state.is_completed.return_value = True
        mock_state.message = "Success"

        # Create a mock future
        mock_future = MagicMock(spec=PrefectFuture)
        mock_future.aresult = AsyncMock(return_value="test_result")
        mock_future.wait_async = AsyncMock()
        mock_future.state = mock_state

        mock = AsyncMock(return_value=mock_future)

        monkeypatch.setattr(VertexAIWorker, "submit", mock)
        yield mock

    @pytest.fixture
    async def work_pool_without_storage_configuration(self):
        async with prefect.get_client() as client:
            work_pool = await client.create_work_pool(
                WorkPoolCreate(
                    name=f"test-{uuid.uuid4()}",
                    base_job_template=VertexAIWorker.get_default_base_job_template(),
                )
            )
            try:
                yield work_pool
            finally:
                await client.delete_work_pool(work_pool.name)

    @pytest.fixture
    async def work_pool_with_storage_configuration(self):
        UPLOAD_STEP = {
            "prefect_mock.experimental.bundles.upload": {
                "requires": "prefect-mock==0.5.5",
                "bucket": "test-bucket",
                "credentials_block_name": "my-creds",
            }
        }

        EXECUTE_STEP = {
            "prefect_mock.experimental.bundles.execute": {
                "requires": "prefect-mock==0.5.5",
                "bucket": "test-bucket",
                "credentials_block_name": "my-creds",
            }
        }

        async with prefect.get_client() as client:
            work_pool = await client.create_work_pool(
                WorkPoolCreate(
                    name=f"test-{uuid.uuid4()}",
                    base_job_template=VertexAIWorker.get_default_base_job_template(),
                    storage_configuration=WorkPoolStorageConfiguration(
                        bundle_execution_step=EXECUTE_STEP,
                        bundle_upload_step=UPLOAD_STEP,
                    ),
                )
            )
            try:
                yield work_pool
            finally:
                await client.delete_work_pool(work_pool.name)

    def test_cloud_run_decorator_sync_flow(self, mock_submit: AsyncMock) -> None:
        """Test that a synchronous flow is correctly decorated and executed"""

        @vertex_ai(work_pool="test-pool", memory="2Gi")
        @prefect.flow
        def sync_test_flow(param1: str, param2: str = "default") -> str:
            return f"{param1}-{param2}"

        result = sync_test_flow("test")

        mock_submit.assert_called_once()
        _args, kwargs = mock_submit.call_args
        assert kwargs["parameters"] == {"param1": "test", "param2": "default"}
        assert kwargs["job_variables"] == {"memory": "2Gi"}
        assert result == "test_result"

    async def test_cloud_run_decorator_async_flow(self, mock_submit: AsyncMock) -> None:
        """Test that an asynchronous flow is correctly decorated and executed"""

        @vertex_ai(work_pool="test-pool", cpu="1")
        @prefect.flow
        async def async_test_flow(param1: str) -> str:
            return f"async-{param1}"

        result = await async_test_flow("test")

        mock_submit.assert_called_once()
        _args, kwargs = mock_submit.call_args
        assert kwargs["parameters"] == {"param1": "test"}
        assert kwargs["job_variables"] == {"cpu": "1"}
        assert result == "test_result"

    @pytest.mark.usefixtures("mock_submit")
    def test_cloud_run_decorator_return_state(self) -> None:
        """Test that return_state=True returns the state instead of the result"""

        @vertex_ai(work_pool="test-pool")
        @prefect.flow
        def test_flow():
            return "completed"

        state = test_flow(return_state=True)

        assert state.is_completed()
        assert state.message == "Success"

    @pytest.mark.usefixtures("mock_submit")
    def test_vertex_ai_decorator_preserves_flow_attributes(self) -> None:
        """Test that the decorator preserves the original flow's attributes"""

        @prefect.flow(name="custom-flow-name", description="Custom description")
        def original_flow():
            return "test"

        original_name = original_flow.name
        original_description = original_flow.description

        decorated_flow = vertex_ai(work_pool="test-pool")(original_flow)

        assert decorated_flow.name == original_name
        assert decorated_flow.description == original_description

        result = decorated_flow()
        assert result == "test_result"

    def test_submit_method_receives_work_pool_name(
        self, mock_submit: AsyncMock
    ) -> None:
        """Test that the correct work pool name is passed to submit"""

        @vertex_ai(work_pool="specific-pool")
        @prefect.flow
        def test_flow():
            return "test"

        test_flow()

        mock_submit.assert_called_once()
        kwargs = mock_submit.call_args.kwargs
        assert "flow" in kwargs
        assert "parameters" in kwargs
        assert "job_variables" in kwargs

    def test_runtime_error_when_work_pool_is_missing_storage_configuration(
        self,
        work_pool_without_storage_configuration: WorkPool,
    ) -> None:
        """Test that a runtime error is raised when the work pool is missing a storage configuration"""

        @vertex_ai(work_pool=work_pool_without_storage_configuration.name)
        @prefect.flow
        def test_flow():
            return "test"

        with pytest.raises(
            RuntimeError,
            match=f"Storage is not configured for work pool {work_pool_without_storage_configuration.name!r}. "
            "Please configure storage for the work pool by running `prefect work-pool storage configure`.",
        ):
            test_flow()


class TestVertexAIDecoratorIncludeFiles:
    """Tests for the include_files parameter of the @vertex_ai decorator"""

    @pytest.fixture
    def mock_submit(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> Generator[AsyncMock, None, None]:
        mock_state = MagicMock(spec=prefect.State)
        mock_state.is_completed.return_value = True
        mock_state.message = "Success"
        mock_future = MagicMock(spec=PrefectFuture)
        mock_future.aresult = AsyncMock(return_value="test_result")
        mock_future.wait_async = AsyncMock()
        mock_future.state = mock_state
        mock = AsyncMock(return_value=mock_future)
        monkeypatch.setattr(VertexAIWorker, "submit", mock)
        yield mock

    def test_include_files_none_passes_none_to_bound_flow(
        self, mock_submit: AsyncMock
    ) -> None:
        @vertex_ai(work_pool="test-pool")
        @prefect.flow
        def test_flow():
            return "test"

        assert test_flow.include_files is None

    def test_include_files_empty_list_passes_empty_list(
        self, mock_submit: AsyncMock
    ) -> None:
        @vertex_ai(work_pool="test-pool", include_files=[])
        @prefect.flow
        def test_flow():
            return "test"

        assert test_flow.include_files == []

    def test_include_files_with_valid_strings(self, mock_submit: AsyncMock) -> None:
        @vertex_ai(work_pool="test-pool", include_files=["config.yaml", "data/"])
        @prefect.flow
        def test_flow():
            return "test"

        assert test_flow.include_files == ["config.yaml", "data/"]

    def test_include_files_tuple_converted_to_list(
        self, mock_submit: AsyncMock
    ) -> None:
        @vertex_ai(work_pool="test-pool", include_files=("a.txt", "b.txt"))
        @prefect.flow
        def test_flow():
            return "test"

        assert test_flow.include_files == ["a.txt", "b.txt"]
        assert isinstance(test_flow.include_files, list)

    def test_include_files_non_string_item_raises_value_error(self) -> None:
        with pytest.raises(
            ValueError, match=r"include_files\[1\] must be a string, got int"
        ):

            @vertex_ai(work_pool="test-pool", include_files=["valid", 123])
            @prefect.flow
            def test_flow():
                return "test"

    def test_include_files_empty_string_raises_value_error(self) -> None:
        with pytest.raises(
            ValueError, match=r"include_files\[0\] cannot be empty or whitespace-only"
        ):

            @vertex_ai(work_pool="test-pool", include_files=[""])
            @prefect.flow
            def test_flow():
                return "test"

    def test_include_files_whitespace_only_raises_value_error(self) -> None:
        with pytest.raises(
            ValueError, match=r"include_files\[1\] cannot be empty or whitespace-only"
        ):

            @vertex_ai(work_pool="test-pool", include_files=["valid", "  "])
            @prefect.flow
            def test_flow():
                return "test"

    def test_include_files_none_type_item_raises_value_error(self) -> None:
        with pytest.raises(
            ValueError, match=r"include_files\[0\] must be a string, got NoneType"
        ):

            @vertex_ai(work_pool="test-pool", include_files=[None])  # type: ignore[list-item]
            @prefect.flow
            def test_flow():
                return "test"
