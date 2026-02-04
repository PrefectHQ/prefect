import pytest
from google.api_core.exceptions import NotFound
from prefect_gcp.firestore import (
    delete_document,
    get_document,
    list_documents,
    query_collection,
    set_document,
    update_document,
)

from prefect import flow


def test_set_document(gcp_credentials):
    @flow
    def test_flow():
        return set_document(
            "my_collection", "doc1", {"key": "value"}, gcp_credentials
        )

    result = test_flow()
    assert result == "my_collection/doc1"


def test_get_document(gcp_credentials):
    @flow
    def test_flow():
        set_document("my_collection", "doc1", {"key": "value"}, gcp_credentials)
        return get_document("my_collection", "doc1", gcp_credentials)

    result = test_flow()
    assert result == {"key": "value"}


def test_get_document_not_found(gcp_credentials):
    @flow
    def test_flow():
        return get_document("my_collection", "nonexistent", gcp_credentials)

    result = test_flow()
    assert result is None


def test_set_document_with_merge(gcp_credentials):
    @flow
    def test_flow():
        set_document(
            "my_collection", "doc1", {"a": 1, "b": 2}, gcp_credentials
        )
        set_document(
            "my_collection", "doc1", {"b": 3, "c": 4}, gcp_credentials, merge=True
        )
        return get_document("my_collection", "doc1", gcp_credentials)

    result = test_flow()
    assert result == {"a": 1, "b": 3, "c": 4}


def test_list_documents(gcp_credentials):
    @flow
    def test_flow():
        set_document("col", "d1", {"x": 1}, gcp_credentials)
        set_document("col", "d2", {"x": 2}, gcp_credentials)
        set_document("col", "d3", {"x": 3}, gcp_credentials)
        return list_documents("col", gcp_credentials)

    result = test_flow()
    assert len(result) == 3
    ids = {doc["id"] for doc in result}
    assert ids == {"d1", "d2", "d3"}


def test_list_documents_with_limit(gcp_credentials):
    @flow
    def test_flow():
        set_document("col", "d1", {"x": 1}, gcp_credentials)
        set_document("col", "d2", {"x": 2}, gcp_credentials)
        set_document("col", "d3", {"x": 3}, gcp_credentials)
        return list_documents("col", gcp_credentials, limit=2)

    result = test_flow()
    assert len(result) == 2


def test_update_document(gcp_credentials):
    @flow
    def test_flow():
        set_document(
            "my_collection", "doc1", {"a": 1, "b": 2}, gcp_credentials
        )
        update_document(
            "my_collection", "doc1", {"b": 99}, gcp_credentials
        )
        return get_document("my_collection", "doc1", gcp_credentials)

    result = test_flow()
    assert result == {"a": 1, "b": 99}


def test_update_nonexistent_document(gcp_credentials):
    @flow
    def test_flow():
        return update_document(
            "my_collection", "missing", {"a": 1}, gcp_credentials
        )

    with pytest.raises(NotFound):
        test_flow()


def test_delete_document(gcp_credentials):
    @flow
    def test_flow():
        set_document("my_collection", "doc1", {"key": "value"}, gcp_credentials)
        delete_document("my_collection", "doc1", gcp_credentials)
        return get_document("my_collection", "doc1", gcp_credentials)

    result = test_flow()
    assert result is None


def test_query_collection(gcp_credentials):
    @flow
    def test_flow():
        set_document("people", "p1", {"name": "Alice", "age": 30}, gcp_credentials)
        set_document("people", "p2", {"name": "Bob", "age": 20}, gcp_credentials)
        set_document("people", "p3", {"name": "Charlie", "age": 25}, gcp_credentials)
        return query_collection(
            "people",
            gcp_credentials,
            filters=[("age", ">=", 25)],
            order_by="age",
        )

    result = test_flow()
    assert len(result) == 2
    assert result[0]["name"] == "Charlie"
    assert result[1]["name"] == "Alice"
