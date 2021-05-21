"""
Tests for `FlowView`
"""
import pendulum
import pytest
from unittest.mock import MagicMock

from prefect import Flow
from prefect.backend import FlowView
from prefect.run_configs import UniversalRun
from prefect.storage import Local

FLOW_DATA_1 = {
    "id": "id-1",
    "name": "name-1",
    "settings": {"key-1": "value-1"},
    "run_config": UniversalRun(env={"ENV-1": "VAL-1"}).serialize(),
    "serialized_flow": Flow("flow-1").serialize(),
    "archived": False,
    "project": {"name": "project-1"},
    "flow_group": {"labels": ["label-1"]},
    "core_version": "0.0.0",
    "storage": Local(stored_as_script=True, path="fake-path-1.py").serialize(),
}

FLOW_DATA_2 = {
    "id": "id-2",
    "name": "name-2",
    "settings": {"key-2": "value-2"},
    "run_config": UniversalRun(env={"ENV-2": "VAL-2"}).serialize(),
    "serialized_flow": Flow("flow-2").serialize(),
    "archived": False,
    "project": {"name": "project-2"},
    "flow_group": {"labels": ["label-2"]},
    "core_version": "0.0.0",
    "storage": Local(stored_as_script=True, path="fake-path-2.py").serialize(),
}


def test_flow_view_query_for_flow_raises_bad_responses(patch_post):
    patch_post({})

    with pytest.raises(ValueError, match="bad result while querying for flows"):
        FlowView._query_for_flow(where={})


def test_flow_view_query_for_flow_raises_when_not_found(patch_post):
    patch_post({"data": {"flow": []}})

    with pytest.raises(ValueError, match="No results found while querying for flows"):
        FlowView._query_for_flow(where={})


def test_flow_view_query_for_flow_errors_on_multiple_flows(patch_post):
    patch_post({"data": {"flow": [1, 2]}})

    with pytest.raises(ValueError, match=r"multiple \(2\) flows"):
        FlowView._query_for_flow(where={})


def test_flow_view_query_for_flow_unpacks_result_singleton(patch_post):
    patch_post({"data": {"flow": [1]}})

    assert FlowView._query_for_flow(where={}) == 1


def test_flow_view_query_for_flow_uses_where_in_query(monkeypatch):
    post = MagicMock(return_value={"data": {"flow": [FLOW_DATA_1]}})
    monkeypatch.setattr("prefect.client.client.Client.post", post)

    FlowView._query_for_flow(where={"foo": {"_eq": "bar"}})

    assert (
        'flow(where: { foo: { _eq: "bar" } })' in post.call_args[1]["params"]["query"]
    )


def test_flow_view_query_for_flow_includes_all_required_data(monkeypatch):
    graphql = MagicMock(return_value={"data": {"flow": [FLOW_DATA_1]}})
    monkeypatch.setattr("prefect.client.client.Client.graphql", graphql)

    FlowView._query_for_flow(where={})

    query_dict = graphql.call_args[0][0]
    selection_set = query_dict["query"]["flow(where: {})"]
    assert selection_set == {
        "id": True,
        "settings": True,
        "run_config": True,
        "serialized_flow": True,
        "flow_group": {"labels"},
        "name": True,
        "archived": True,
        "project": {"name"},
        "core_version": True,
        "storage": True,
    }


@pytest.mark.parametrize("from_method", ["flow_id", "flow_data"])
def test_flow_view_from_returns_instance(patch_post, from_method):
    patch_post({"data": {"flow": [FLOW_DATA_1]}})

    if from_method == "flow_id":
        flow = FlowView.from_flow_id("id-1")
    elif from_method == "flow_data":
        # Note the post patch will not be used since there is no query here
        flow = FlowView._from_flow_data(FLOW_DATA_1)

    assert flow.flow_id == "id-1"
    assert flow.serialized_flow == FLOW_DATA_1["serialized_flow"]
    assert flow.flow == Flow("flow-1")
    assert flow.name == "name-1"
    assert flow.settings == {"key-1": "value-1"}
    assert flow.flow_group_labels == ["label-1"]
    assert isinstance(flow.run_config, UniversalRun)
    assert flow.run_config.env == {"ENV-1": "VAL-1"}
    assert flow.archived is False
    assert flow.project_name == "project-1"
    assert flow.core_version == "0.0.0"
    assert isinstance(flow.storage, Local)
    assert flow.storage.stored_as_script is True
    assert flow.storage.path == "fake-path-1.py"


def test_flow_view_from_flow_id_where_clause(monkeypatch):
    post = MagicMock(return_value={"data": {"flow": [FLOW_DATA_1]}})
    monkeypatch.setattr("prefect.client.client.Client.post", post)

    FlowView.from_flow_id(flow_id="id-1")

    assert (
        'flow(where: { id: { _eq: "id-1" } })' in post.call_args[1]["params"]["query"]
    )


def test_flow_view_from_flow_name_where_and_order_clauses(monkeypatch):
    post = MagicMock(return_value={"data": {"flow": [FLOW_DATA_1]}})
    monkeypatch.setattr("prefect.client.client.Client.post", post)

    FlowView.from_flow_name(flow_name="name-1")

    assert (
        'where: { name: { _eq: "name-1" }, archived: { _eq: false } }'
        in post.call_args[1]["params"]["query"]
    )
    assert "order_by: { created: desc }" in post.call_args[1]["params"]["query"]


def test_flow_view_from_flow_name_and_project_where_and_order_clauses(monkeypatch):
    post = MagicMock(return_value={"data": {"flow": [FLOW_DATA_1]}})
    monkeypatch.setattr("prefect.client.client.Client.post", post)

    FlowView.from_flow_name(flow_name="name-1", project_name="project-1")

    assert (
        'where: { name: { _eq: "name-1" }, archived: { _eq: false }, '
        'project: { name: { _eq: "project-1" } }'
    ) in post.call_args[1]["params"]["query"]
    assert "order_by: { created: desc }" in post.call_args[1]["params"]["query"]


def test_flow_view_from_flow_group_id_where_and_order_clauses(monkeypatch):
    post = MagicMock(return_value={"data": {"flow": [FLOW_DATA_1]}})
    monkeypatch.setattr("prefect.client.client.Client.post", post)

    FlowView.from_flow_group_id(flow_group_id="flow-group-id-1")

    assert (
        'where: { flow_group_id: { _eq: "flow-group-id-1" } }'
        in post.call_args[1]["params"]["query"]
    )
    assert "order_by: { created: desc }" in post.call_args[1]["params"]["query"]
