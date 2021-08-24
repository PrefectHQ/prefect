"""
Tests for `TenantView`
"""
import pytest
from unittest.mock import MagicMock

from prefect.backend import TenantView
from prefect.utilities.graphql import EnumValue

TENANT_DATA_1 = {
    "id": "id-1",
    "name": "name-1",
    "slug": "slug-1",
}


def test_tenant_view_query_for_tenants_raises_bad_responses(patch_post):
    patch_post({})

    with pytest.raises(ValueError, match="bad result while querying for tenants"):
        TenantView._query_for_tenants(where={})


def test_tenant_view_query_for_tenants_raises_when_not_found(patch_post):
    patch_post({"data": {"tenant": []}})

    with pytest.raises(ValueError, match="No results found while querying for tenants"):
        TenantView._query_for_tenants(where={})


def test_tenant_view_query_for_tenants_allows_return_when_not_found(patch_post):
    patch_post({"data": {"tenant": []}})

    assert TenantView._query_for_tenants(where={}, error_on_empty=False) == []


def test_tenant_view_query_for_tenants_allows_returns_all_tenant_data(patch_post):
    patch_post({"data": {"tenant": [1, 2]}})

    assert TenantView._query_for_tenants(where={}) == [1, 2]


def test_tenant_view_query_for_tenants_uses_where_in_query(monkeypatch):
    post = MagicMock(return_value={"data": {"tenant": [TENANT_DATA_1]}})
    monkeypatch.setattr("prefect.client.client.Client.post", post)

    TenantView._query_for_tenants(where={"foo": {"_eq": "bar"}})

    assert (
        'tenant(where: { foo: { _eq: "bar" } })' in post.call_args[1]["params"]["query"]
    )


def test_tenant_view_query_for_tenants_uses_order_by_in_query(monkeypatch):
    post = MagicMock(return_value={"data": {"tenant": [TENANT_DATA_1]}})
    monkeypatch.setattr("prefect.client.client.Client.post", post)

    TenantView._query_for_tenants(where={}, order_by={"foo": EnumValue("asc")})

    assert (
        "tenant(where: {}, order_by: { foo: asc })"
        in post.call_args[1]["params"]["query"]
    )


def test_tenant_view_query_for_tenants_includes_all_required_data(monkeypatch):
    graphql = MagicMock(return_value={"data": {"tenant": [TENANT_DATA_1]}})
    monkeypatch.setattr("prefect.client.client.Client.graphql", graphql)

    TenantView._query_for_tenants(where={})

    query_dict = graphql.call_args[0][0]
    selection_set = query_dict["query"]["tenant(where: {})"]
    assert selection_set == {"id", "name", "slug"}


def test_tenant_view_query_for_tenant_errors_on_multiple_tenants(patch_post):
    patch_post({"data": {"tenant": [1, 2]}})

    with pytest.raises(ValueError, match=r"multiple \(2\) tenants"):
        TenantView._query_for_tenant(where={})


def test_tenant_view_query_for_tenant_unpacks_singleton_result(patch_post):
    patch_post({"data": {"tenant": [1]}})

    assert TenantView._query_for_tenant(where={}) == 1


@pytest.mark.parametrize("from_method", ["tenant_id", "current_tenant"])
def test_tenant_view_from_returns_instance(patch_post, from_method, monkeypatch):
    patch_post({"data": {"tenant": [TENANT_DATA_1]}})

    if from_method == "tenant_id":
        tenant = TenantView.from_tenant_id("fake-id")
    elif from_method == "current_tenant":
        monkeypatch.setattr(
            "prefect.client.client.Client._get_auth_tenant",
            MagicMock(return_value="fake-id"),
        )
        tenant = TenantView.from_current_tenant()

    assert tenant.tenant_id == "id-1"
    assert tenant.name == "name-1"
    assert tenant.slug == "slug-1"


def test_tenant_view_from_tenant_id_where_clause(monkeypatch):
    post = MagicMock(return_value={"data": {"tenant": [TENANT_DATA_1]}})
    monkeypatch.setattr("prefect.client.client.Client.post", post)

    TenantView.from_tenant_id(tenant_id="id-1")

    assert (
        'tenant(where: { id: { _eq: "id-1" } })' in post.call_args[1]["params"]["query"]
    )
