from unittest.mock import patch

import pytest

from prefect import flow, tags
from prefect._experimental.lineage import (
    emit_external_resource_lineage,
    emit_lineage_event,
    emit_result_read_event,
    emit_result_write_event,
    get_result_resource_uri,
)
from prefect.events.schemas.events import Event, RelatedResource
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


async def test_get_result_resource_uri_with_local_storage(
    local_storage: LocalFileSystem,
):
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
async def test_get_resource_uri_block_type_mapping(
    block_type: str, expected_prefix: str
):
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
    @pytest.mark.usefixtures("enable_lineage_events")
    async def test_emit_lineage_event_with_upstream_and_downstream(
        self, mock_emit_event: Event
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

    @pytest.mark.usefixtures("enable_lineage_events")
    async def test_emit_lineage_event_with_no_resources(self, mock_emit_event: Event):
        await emit_lineage_event(event_name="test.event")
        mock_emit_event.assert_not_called()

    async def test_emit_lineage_event_disabled(self, mock_emit_event: Event):
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

    @pytest.mark.usefixtures("enable_lineage_events")
    async def test_emit_lineage_event_includes_tags(self, mock_emit_event: Event):
        upstream_resources = [
            {
                "prefect.resource.id": "upstream1",
                "prefect.resource.role": "data-source",
            }
        ]
        downstream_resources = [
            {
                "prefect.resource.id": "downstream1",
                "prefect.resource.role": "data-destination",
            }
        ]

        @flow
        async def test_flow():
            await emit_lineage_event(
                event_name="test.event",
                upstream_resources=upstream_resources,
                downstream_resources=downstream_resources,
            )

        with tags("test-tag"):
            await test_flow()

        # Should have:
        # - 1 event for downstream1
        # - 1 event for flow
        # - 1 event for flow run
        assert mock_emit_event.call_count == 3

        # Check that all events include the tag in related resources
        for call in mock_emit_event.call_args_list:
            related_resources = call.kwargs["related"]
            tag_resources = [
                r for r in related_resources if r.get("prefect.resource.role") == "tag"
            ]
            assert len(tag_resources) == 1
            assert tag_resources[0]["prefect.resource.id"] == "prefect.tag.test-tag"


class TestEmitExternalResourceLineage:
    @pytest.mark.usefixtures("enable_lineage_events")
    async def test_emit_external_resource_lineage_with_upstream_only(
        self, mock_emit_event: Event
    ):
        upstream_resources = [
            {
                "prefect.resource.id": "upstream1",
                "prefect.resource.role": "data-source",
            }
        ]

        @flow
        async def test_flow():
            await emit_external_resource_lineage(upstream_resources=upstream_resources)

        await test_flow()

        # Should emit one event per context resource (flow and flow-run)
        assert mock_emit_event.call_count == 2
        for call in mock_emit_event.call_args_list:
            assert call.kwargs["event"] == "prefect.lineage.upstream-interaction"
            assert "prefect.resource.role" in call.kwargs["resource"]
            assert call.kwargs["related"] == [
                {
                    "prefect.resource.id": "upstream1",
                    "prefect.resource.role": "data-source",
                    "prefect.resource.lineage-group": "global",
                }
            ]

    @pytest.mark.usefixtures("enable_lineage_events")
    async def test_emit_external_resource_lineage_with_downstream_only(
        self, mock_emit_event: Event
    ):
        downstream_resources = [
            {
                "prefect.resource.id": "downstream1",
                "prefect.resource.role": "data-destination",
            }
        ]

        @flow
        async def test_flow():
            await emit_external_resource_lineage(
                downstream_resources=downstream_resources
            )

        await test_flow()

        mock_emit_event.assert_called_once()
        call_args = mock_emit_event.call_args.kwargs
        assert call_args["event"] == "prefect.lineage.downstream-interaction"
        assert call_args["resource"] == {
            "prefect.resource.id": "downstream1",
            "prefect.resource.role": "data-destination",
            "prefect.resource.lineage-group": "global",
        }
        assert len(call_args["related"]) == 2  # flow and flow-run
        assert call_args["related"][0]["prefect.resource.role"] == "flow-run"
        assert call_args["related"][1]["prefect.resource.role"] == "flow"

    @pytest.mark.usefixtures("enable_lineage_events")
    async def test_emit_external_resource_lineage_with_both(
        self, mock_emit_event: Event
    ):
        upstream_resources = [
            {
                "prefect.resource.id": "upstream1",
                "prefect.resource.role": "data-source",
            }
        ]
        downstream_resources = [
            {
                "prefect.resource.id": "downstream1",
                "prefect.resource.role": "data-destination",
            }
        ]

        @flow
        async def test_flow():
            await emit_external_resource_lineage(
                upstream_resources=upstream_resources,
                downstream_resources=downstream_resources,
            )

        await test_flow()

        # Should have:
        # - 2 events for context resources (flow and flow-run) consuming upstream
        # - 1 event for downstream resource being produced by context
        # - 1 event for direct lineage between upstream and downstream
        assert mock_emit_event.call_count == 4

        # Check context resources consuming upstream (first two events)
        context_calls = mock_emit_event.call_args_list[:2]
        for call in context_calls:
            assert call.kwargs["event"] == "prefect.lineage.upstream-interaction"
            assert "prefect.resource.role" in call.kwargs["resource"]
            assert call.kwargs["related"] == [
                {
                    "prefect.resource.id": "upstream1",
                    "prefect.resource.role": "data-source",
                    "prefect.resource.lineage-group": "global",
                }
            ]

        # Check downstream produced by context (third event)
        produced_call = mock_emit_event.call_args_list[2]
        assert produced_call.kwargs["event"] == "prefect.lineage.downstream-interaction"
        assert produced_call.kwargs["resource"] == {
            "prefect.resource.id": "downstream1",
            "prefect.resource.role": "data-destination",
            "prefect.resource.lineage-group": "global",
        }
        assert len(produced_call.kwargs["related"]) == 2  # flow + flow-run
        assert any(
            r["prefect.resource.role"] == "flow-run"
            for r in produced_call.kwargs["related"]
        )
        assert any(
            r["prefect.resource.role"] == "flow"
            for r in produced_call.kwargs["related"]
        )

        # Check direct lineage event (fourth event)
        direct_call = mock_emit_event.call_args_list[3]
        assert direct_call.kwargs["event"] == "prefect.lineage.event"
        assert direct_call.kwargs["resource"] == {
            "prefect.resource.id": "downstream1",
            "prefect.resource.role": "data-destination",
            "prefect.resource.lineage-group": "global",
        }
        assert direct_call.kwargs["related"] == [
            {
                "prefect.resource.id": "upstream1",
                "prefect.resource.role": "data-source",
                "prefect.resource.lineage-group": "global",
            }
        ]

    @pytest.mark.usefixtures("enable_lineage_events")
    async def test_emit_external_resource_lineage_with_neither(
        self, mock_emit_event: Event
    ):
        @flow
        async def test_flow():
            await emit_external_resource_lineage()

        await test_flow()
        mock_emit_event.assert_not_called()

    async def test_emit_external_resource_lineage_disabled(
        self, mock_emit_event: Event
    ):
        upstream_resources = [{"prefect.resource.id": "upstream1"}]
        downstream_resources = [{"prefect.resource.id": "downstream1"}]

        @flow
        async def test_flow():
            await emit_external_resource_lineage(
                upstream_resources=upstream_resources,
                downstream_resources=downstream_resources,
            )

        await test_flow()
        mock_emit_event.assert_not_called()

    @pytest.mark.usefixtures("enable_lineage_events")
    async def test_emit_external_resource_lineage_custom_event_name(
        self, mock_emit_event: Event
    ):
        upstream_resources = [
            {
                "prefect.resource.id": "upstream1",
                "prefect.resource.role": "data-source",
            }
        ]
        downstream_resources = [
            {
                "prefect.resource.id": "downstream1",
                "prefect.resource.role": "data-destination",
            }
        ]

        @flow
        async def test_flow():
            # Test with custom event name
            await emit_external_resource_lineage(
                event_name="custom.lineage.event",
                upstream_resources=upstream_resources,
                downstream_resources=downstream_resources,
            )

            # Test with default event name
            await emit_external_resource_lineage(
                upstream_resources=upstream_resources,
                downstream_resources=downstream_resources,
            )

        await test_flow()

        # We expect 8 total events (4 for each call):
        # - 2 upstream interaction events
        # - 1 downstream interaction event
        # - 1 direct lineage event
        assert mock_emit_event.call_count == 8

        # Check the direct lineage events (4th and 8th calls)
        custom_direct_call = mock_emit_event.call_args_list[3]
        assert custom_direct_call.kwargs["event"] == "custom.lineage.event"

        default_direct_call = mock_emit_event.call_args_list[7]
        assert default_direct_call.kwargs["event"] == "prefect.lineage.event"

        # Verify the rest of the event structure remains correct
        for direct_call in [custom_direct_call, default_direct_call]:
            assert direct_call.kwargs["resource"] == {
                "prefect.resource.id": "downstream1",
                "prefect.resource.role": "data-destination",
                "prefect.resource.lineage-group": "global",
            }
            assert direct_call.kwargs["related"] == [
                {
                    "prefect.resource.id": "upstream1",
                    "prefect.resource.role": "data-source",
                    "prefect.resource.lineage-group": "global",
                }
            ]

    @pytest.mark.usefixtures("enable_lineage_events")
    async def test_emit_external_resource_lineage_includes_tags(
        self, mock_emit_event: Event
    ):
        upstream_resources = [
            {
                "prefect.resource.id": "upstream1",
                "prefect.resource.role": "data-source",
            }
        ]
        downstream_resources = [
            {
                "prefect.resource.id": "downstream1",
                "prefect.resource.role": "data-destination",
            }
        ]

        @flow
        async def test_flow():
            await emit_external_resource_lineage(
                upstream_resources=upstream_resources,
                downstream_resources=downstream_resources,
            )

        with tags("test-tag"):
            await test_flow()

        # Should have:
        # - 2 events for context resources consuming upstream
        # - 1 event for downstream resource being produced by context
        # - 1 event for direct lineage between upstream and downstream
        assert mock_emit_event.call_count == 4

        # Check that all events include the tag in related resources
        for call in mock_emit_event.call_args_list:
            related_resources = call.kwargs["related"]
            tag_resources = [
                r for r in related_resources if r.get("prefect.resource.role") == "tag"
            ]
            assert len(tag_resources) == 1
            assert tag_resources[0]["prefect.resource.id"] == "prefect.tag.test-tag"

    @pytest.mark.usefixtures("enable_lineage_events")
    async def test_emit_external_resource_lineage_with_context_resources(
        self, mock_emit_event: Event
    ):
        upstream_resources = [
            {
                "prefect.resource.id": "upstream1",
                "prefect.resource.role": "data-source",
            }
        ]
        downstream_resources = [
            {
                "prefect.resource.id": "downstream1",
                "prefect.resource.role": "data-destination",
            }
        ]
        context_resources = [
            {
                "prefect.resource.id": "context1",
                "prefect.resource.role": "flow-run",
            },
            {
                "prefect.resource.id": "context2",
                "prefect.resource.role": "flow",
            },
            {
                "prefect.resource.id": "tag1",
                "prefect.resource.role": "tag",
            },
        ]

        await emit_external_resource_lineage(
            upstream_resources=upstream_resources,
            downstream_resources=downstream_resources,
            context_resources=context_resources,
        )

        # Should have:
        # - 2 events for context resources consuming upstream
        # - 1 event for downstream resource being produced by context
        # - 1 event for direct lineage between upstream and downstream
        assert mock_emit_event.call_count == 4

        # Check context resources consuming upstream
        context_calls = mock_emit_event.call_args_list[:2]
        for i, call in enumerate(context_calls):
            assert call.kwargs["event"] == "prefect.lineage.upstream-interaction"
            assert call.kwargs["resource"] == {
                "prefect.resource.id": f"context{i + 1}",
                "prefect.resource.role": "flow-run" if i == 0 else "flow",
                "prefect.resource.lineage-group": "global",
            }
            assert call.kwargs["related"] == [
                {
                    "prefect.resource.id": "upstream1",
                    "prefect.resource.role": "data-source",
                    "prefect.resource.lineage-group": "global",
                },
                {
                    "prefect.resource.id": "tag1",
                    "prefect.resource.role": "tag",
                },
            ]

        # Check downstream produced by context
        downstream_call = mock_emit_event.call_args_list[2]
        assert (
            downstream_call.kwargs["event"] == "prefect.lineage.downstream-interaction"
        )
        assert downstream_call.kwargs["resource"] == {
            "prefect.resource.id": "downstream1",
            "prefect.resource.role": "data-destination",
            "prefect.resource.lineage-group": "global",
        }
        assert downstream_call.kwargs["related"] == [
            {
                "prefect.resource.id": "context1",
                "prefect.resource.role": "flow-run",
                "prefect.resource.lineage-group": "global",
            },
            {
                "prefect.resource.id": "context2",
                "prefect.resource.role": "flow",
                "prefect.resource.lineage-group": "global",
            },
            {
                "prefect.resource.id": "tag1",
                "prefect.resource.role": "tag",
            },
        ]

        # Check direct lineage
        direct_call = mock_emit_event.call_args_list[3]
        assert direct_call.kwargs["event"] == "prefect.lineage.event"
        assert direct_call.kwargs["resource"] == {
            "prefect.resource.id": "downstream1",
            "prefect.resource.role": "data-destination",
            "prefect.resource.lineage-group": "global",
        }
        assert direct_call.kwargs["related"] == [
            {
                "prefect.resource.id": "upstream1",
                "prefect.resource.role": "data-source",
                "prefect.resource.lineage-group": "global",
            },
            {
                "prefect.resource.id": "tag1",
                "prefect.resource.role": "tag",
            },
        ]


class TestEmitResultEvents:
    @pytest.mark.usefixtures("enable_lineage_events")
    async def test_emit_result_read_event(
        self, result_store: ResultStore, mock_emit_event: Event
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

    @pytest.mark.usefixtures("enable_lineage_events")
    async def test_emit_result_write_event(
        self, result_store: ResultStore, mock_emit_event: Event
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

    @pytest.mark.usefixtures("enable_lineage_events")
    async def test_emit_result_read_event_with_none_uri(self, mock_emit_event: Event):
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

    @pytest.mark.usefixtures("enable_lineage_events")
    async def test_emit_result_write_event_with_none_uri(self, mock_emit_event: Event):
        store = ResultStore(result_storage=None)
        await emit_result_write_event(store, "test-key")
        mock_emit_event.assert_not_called()

    @pytest.mark.usefixtures("enable_lineage_events")
    async def test_emit_result_read_event_with_downstream_resources(
        self, result_store: ResultStore, mock_emit_event: Event
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
                "prefect.resource.id": f"downstream{i + 1}",
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

    @pytest.mark.usefixtures("enable_lineage_events")
    async def test_emit_result_write_event_with_upstream_resources(
        self, result_store: ResultStore, mock_emit_event: Event
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
