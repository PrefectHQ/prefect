from unittest.mock import patch

import pytest

from prefect import flow
from prefect._experimental.lineage import (
    emit_lineage_event,
    emit_result_read_event,
    emit_result_write_event,
    get_result_resource_uri,
)
from prefect.events.schemas.events import RelatedResource
from prefect.filesystems import (
    LocalFileSystem,
    WritableDeploymentStorage,
    WritableFileSystem,
)
from prefect.results import ResultStore


@pytest.fixture
async def local_storage(tmp_path):
    return LocalFileSystem(basepath=str(tmp_path))


@pytest.fixture
def result_store(local_storage):
    return ResultStore(result_storage=local_storage)


@pytest.fixture
def mock_emit_event():
    """Mock the emit_event function used by all lineage event emission."""
    with patch("prefect._experimental.lineage.emit_event") as mock:
        yield mock


class CustomStorage(WritableFileSystem, WritableDeploymentStorage):
    _block_type_slug = "custom-storage"

    def _resolve_path(self, path):
        return path

    @classmethod
    def get_block_type_slug(cls):
        return "custom-storage"

    def get_directory(self, path: str) -> str:
        raise NotImplementedError

    def put_directory(self, path: str, directory_path: str) -> None:
        raise NotImplementedError

    def read_path(self, path: str) -> bytes:
        raise NotImplementedError

    def write_path(self, path: str, contents: bytes) -> None:
        raise NotImplementedError


async def test_get_result_resource_uri_with_local_storage(local_storage):
    uri = get_result_resource_uri(ResultStore(result_storage=local_storage), "test-key")
    assert uri is not None
    assert uri.startswith("file://")
    assert uri.endswith("/test-key")


async def test_get_resource_uri_with_none_storage():
    store = ResultStore(result_storage=None)
    uri = get_result_resource_uri(store, "test-key")
    assert uri is None


async def test_get_resource_uri_with_unknown_storage():
    store = ResultStore(result_storage=CustomStorage())
    uri = get_result_resource_uri(store, "test-key")
    assert uri == "prefect://custom-storage/test-key"


@pytest.mark.parametrize(
    "block_type,expected_prefix",
    [
        ("local-file-system", "file://"),
        ("s3-bucket", "s3://"),
        ("gcs-bucket", "gs://"),
        ("azure-blob-storage", "azure-blob://"),
    ],
)
async def test_get_resource_uri_block_type_mapping(block_type, expected_prefix):
    if block_type == "local-file-system":
        cls = LocalFileSystem
    else:

        class MockStorage(CustomStorage):
            _block_type_slug = block_type

            def _resolve_path(self, path):
                return path

            @classmethod
            def get_block_type_slug(cls):
                return block_type

            # Add required attributes based on block type
            bucket_name: str = "test-bucket"
            bucket: str = "test-bucket"
            container_name: str = "test-container"

        cls = MockStorage

    store = ResultStore(result_storage=cls())
    uri = get_result_resource_uri(store, "test-key")
    assert uri is not None
    assert uri.startswith(expected_prefix), f"Failed for {block_type}"


class TestEmitLineageEvent:
    async def test_emit_lineage_event_with_upstream_and_downstream(
        self, enable_lineage_events, mock_emit_event
    ):
        await emit_lineage_event(
            event_name="test.event",
            upstream_resources=[
                {
                    "prefect.resource.id": "upstream1",
                    "prefect.resource.role": "some-purpose",
                },
                {
                    "prefect.resource.id": "upstream2",
                    "prefect.resource.role": "some-purpose",
                },
            ],
            downstream_resources=[
                {
                    "prefect.resource.id": "downstream1",
                    "prefect.resource.role": "some-purpose",
                },
                {
                    "prefect.resource.id": "downstream2",
                    "prefect.resource.role": "some-purpose",
                },
            ],
        )

        assert mock_emit_event.call_count == 2  # One call per downstream resource

        # Check first downstream resource event
        first_call = mock_emit_event.call_args_list[0]
        assert first_call.kwargs["event"] == "test.event"
        assert first_call.kwargs["resource"] == {
            "prefect.resource.id": "downstream1",
            "prefect.resource.lineage-group": "global",
            "prefect.resource.role": "some-purpose",
        }
        assert first_call.kwargs["related"] == [
            {
                "prefect.resource.id": "upstream1",
                "prefect.resource.role": "some-purpose",
                "prefect.resource.lineage-group": "global",
            },
            {
                "prefect.resource.id": "upstream2",
                "prefect.resource.role": "some-purpose",
                "prefect.resource.lineage-group": "global",
            },
        ]

        # Check second downstream resource event
        second_call = mock_emit_event.call_args_list[1]
        assert second_call.kwargs["event"] == "test.event"
        assert second_call.kwargs["resource"] == {
            "prefect.resource.id": "downstream2",
            "prefect.resource.lineage-group": "global",
            "prefect.resource.role": "some-purpose",
        }
        assert second_call.kwargs["related"] == [
            {
                "prefect.resource.id": "upstream1",
                "prefect.resource.role": "some-purpose",
                "prefect.resource.lineage-group": "global",
            },
            {
                "prefect.resource.id": "upstream2",
                "prefect.resource.role": "some-purpose",
                "prefect.resource.lineage-group": "global",
            },
        ]

    async def test_emit_lineage_event_with_no_resources(
        self, enable_lineage_events, mock_emit_event
    ):
        await emit_lineage_event(event_name="test.event")
        mock_emit_event.assert_not_called()

    async def test_emit_lineage_event_disabled(self, mock_emit_event):
        await emit_lineage_event(
            event_name="test.event",
            upstream_resources=[
                {
                    "prefect.resource.id": "upstream",
                    "prefect.resource.role": "some-purpose",
                }
            ],
            downstream_resources=[
                {
                    "prefect.resource.id": "downstream",
                    "prefect.resource.role": "result",
                }
            ],
        )
        mock_emit_event.assert_not_called()


class TestEmitResultEvents:
    async def test_emit_result_read_event(
        self, result_store, enable_lineage_events, mock_emit_event
    ):
        await emit_result_read_event(
            result_store,
            "test-key",
            [
                {
                    "prefect.resource.id": "downstream",
                    "prefect.resource.role": "flow-run",
                }
            ],
        )

        mock_emit_event.assert_called_once()
        call_args = mock_emit_event.call_args.kwargs
        assert call_args["event"] == "prefect.result.read"
        resource_uri = get_result_resource_uri(result_store, "test-key")
        assert resource_uri is not None
        assert call_args["resource"] == {
            "prefect.resource.id": "downstream",
            "prefect.resource.lineage-group": "global",
            "prefect.resource.role": "flow-run",
        }
        assert call_args["related"] == [
            RelatedResource(
                root={
                    "prefect.resource.id": resource_uri,
                    "prefect.resource.role": "result",
                    "prefect.resource.lineage-group": "global",
                }
            )
        ]

    async def test_emit_result_write_event(
        self, result_store, enable_lineage_events, mock_emit_event
    ):
        @flow
        async def foo():
            await emit_result_write_event(result_store, "test-key")

        await foo()

        mock_emit_event.assert_called_once()
        call_args = mock_emit_event.call_args.kwargs
        assert call_args["event"] == "prefect.result.write"
        assert call_args["resource"] == {
            "prefect.resource.id": get_result_resource_uri(result_store, "test-key"),
            "prefect.resource.lineage-group": "global",
            "prefect.resource.role": "result",
        }
        assert len(call_args["related"]) == 2

        related = call_args["related"][0]
        assert related["prefect.resource.role"] == "flow-run"
        assert related["prefect.resource.lineage-group"] == "global"

        related = call_args["related"][1]
        assert related["prefect.resource.role"] == "flow"
        assert related["prefect.resource.lineage-group"] == "global"

    async def test_emit_result_read_event_with_none_uri(
        self, enable_lineage_events, mock_emit_event
    ):
        store = ResultStore(result_storage=None)
        await emit_result_read_event(
            store,
            "test-key",
            [
                {
                    "prefect.resource.id": "downstream",
                    "prefect.resource.role": "flow-run",
                }
            ],
        )
        mock_emit_event.assert_not_called()

    async def test_emit_result_write_event_with_none_uri(
        self, enable_lineage_events, mock_emit_event
    ):
        store = ResultStore(result_storage=None)
        await emit_result_write_event(store, "test-key")
        mock_emit_event.assert_not_called()

    async def test_emit_result_read_event_with_downstream_resources(
        self, result_store, enable_lineage_events, mock_emit_event
    ):
        await emit_result_read_event(
            result_store,
            "test-key",
            downstream_resources=[
                {"prefect.resource.id": "downstream1"},
                {"prefect.resource.id": "downstream2"},
            ],
        )

        calls = mock_emit_event.call_args_list
        assert len(calls) == 2

        for i, call in enumerate(calls):
            resource_uri = get_result_resource_uri(result_store, "test-key")
            assert resource_uri is not None
            assert call.kwargs["event"] == "prefect.result.read"
            assert call.kwargs["resource"] == {
                "prefect.resource.id": f"downstream{i+1}",
                "prefect.resource.lineage-group": "global",
            }
            assert call.kwargs["related"] == [
                RelatedResource(
                    root={
                        "prefect.resource.id": resource_uri,
                        "prefect.resource.role": "result",
                        "prefect.resource.lineage-group": "global",
                    }
                )
            ]

    async def test_emit_result_write_event_with_upstream_resources(
        self, result_store, enable_lineage_events, mock_emit_event
    ):
        await emit_result_write_event(
            result_store,
            "test-key",
            upstream_resources=[
                {
                    "prefect.resource.id": "upstream",
                    "prefect.resource.role": "my-role",
                }
            ],
        )

        resolved_key_path = result_store._resolved_key_path("test-key")
        resource_uri = get_result_resource_uri(result_store, resolved_key_path)

        mock_emit_event.assert_called_once_with(
            event="prefect.result.write",
            resource={
                "prefect.resource.id": resource_uri,
                "prefect.resource.lineage-group": "global",
                "prefect.resource.role": "result",
            },
            related=[
                {
                    "prefect.resource.id": "upstream",
                    "prefect.resource.role": "my-role",
                    "prefect.resource.lineage-group": "global",
                }
            ],
        )
