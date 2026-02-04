"""Tasks for interacting with Google Cloud Firestore."""

from typing import Any, Dict, List, Optional, Tuple

from anyio import to_thread

from prefect import task
from prefect._internal.compatibility.async_dispatch import async_dispatch
from prefect.logging import get_run_logger
from prefect_gcp.credentials import GcpCredentials

try:
    from google.cloud.firestore_v1.base_query import FieldFilter
except ModuleNotFoundError:
    pass


def _get_client(
    gcp_credentials: "GcpCredentials",
    project: Optional[str] = None,
    database: str = "(default)",
):
    """Helper to get a Firestore client."""
    return gcp_credentials.get_firestore_client(project=project, database=database)


@task
async def aset_document(
    collection: str,
    document: str,
    data: Dict[str, Any],
    gcp_credentials: "GcpCredentials",
    project: Optional[str] = None,
    database: str = "(default)",
    merge: bool = False,
) -> str:
    """
    Creates or overwrites a document in a Firestore collection.

    Args:
        collection: The collection path (supports nested paths like
            ``"users/uid/orders"``).
        document: The document ID.
        data: The document data as a dictionary.
        gcp_credentials: Credentials to use for authentication with GCP.
        project: Name of the project to use; overrides the
            gcp_credentials project if provided.
        database: Name of the Firestore database to use.
        merge: If ``True``, merge data into an existing document instead of
            overwriting.

    Returns:
        The full document path.

    Example:
        ```python
        from prefect import flow
        from prefect_gcp import GcpCredentials
        from prefect_gcp.firestore import aset_document

        @flow()
        async def example_set_document_flow():
            gcp_credentials = GcpCredentials(project="project")
            path = await aset_document(
                "my_collection", "my_doc", {"key": "value"}, gcp_credentials
            )
            return path

        example_set_document_flow()
        ```
    """
    logger = get_run_logger()
    logger.info("Setting document %s/%s", collection, document)

    client = _get_client(gcp_credentials, project=project, database=database)
    doc_ref = client.collection(collection).document(document)
    await to_thread.run_sync(lambda: doc_ref.set(data, merge=merge))
    return doc_ref.path


@task
@async_dispatch(aset_document)
def set_document(
    collection: str,
    document: str,
    data: Dict[str, Any],
    gcp_credentials: "GcpCredentials",
    project: Optional[str] = None,
    database: str = "(default)",
    merge: bool = False,
) -> str:
    """
    Creates or overwrites a document in a Firestore collection.

    Args:
        collection: The collection path (supports nested paths like
            ``"users/uid/orders"``).
        document: The document ID.
        data: The document data as a dictionary.
        gcp_credentials: Credentials to use for authentication with GCP.
        project: Name of the project to use; overrides the
            gcp_credentials project if provided.
        database: Name of the Firestore database to use.
        merge: If ``True``, merge data into an existing document instead of
            overwriting.

    Returns:
        The full document path.

    Example:
        ```python
        from prefect import flow
        from prefect_gcp import GcpCredentials
        from prefect_gcp.firestore import set_document

        @flow()
        def example_set_document_flow():
            gcp_credentials = GcpCredentials(project="project")
            path = set_document(
                "my_collection", "my_doc", {"key": "value"}, gcp_credentials
            )
            return path

        example_set_document_flow()
        ```
    """
    client = _get_client(gcp_credentials, project=project, database=database)
    doc_ref = client.collection(collection).document(document)
    doc_ref.set(data, merge=merge)
    return doc_ref.path


@task
async def aget_document(
    collection: str,
    document: str,
    gcp_credentials: "GcpCredentials",
    project: Optional[str] = None,
    database: str = "(default)",
) -> Optional[Dict[str, Any]]:
    """
    Reads a single document from a Firestore collection.

    Args:
        collection: The collection path (supports nested paths like
            ``"users/uid/orders"``).
        document: The document ID.
        gcp_credentials: Credentials to use for authentication with GCP.
        project: Name of the project to use; overrides the
            gcp_credentials project if provided.
        database: Name of the Firestore database to use.

    Returns:
        The document data as a dictionary, or ``None`` if the document
        does not exist.

    Example:
        ```python
        from prefect import flow
        from prefect_gcp import GcpCredentials
        from prefect_gcp.firestore import aget_document

        @flow()
        async def example_get_document_flow():
            gcp_credentials = GcpCredentials(project="project")
            data = await aget_document("my_collection", "my_doc", gcp_credentials)
            return data

        example_get_document_flow()
        ```
    """
    logger = get_run_logger()
    logger.info("Getting document %s/%s", collection, document)

    client = _get_client(gcp_credentials, project=project, database=database)
    doc_ref = client.collection(collection).document(document)
    snapshot = await to_thread.run_sync(lambda: doc_ref.get())
    if snapshot.exists:
        return snapshot.to_dict()
    return None


@task
@async_dispatch(aget_document)
def get_document(
    collection: str,
    document: str,
    gcp_credentials: "GcpCredentials",
    project: Optional[str] = None,
    database: str = "(default)",
) -> Optional[Dict[str, Any]]:
    """
    Reads a single document from a Firestore collection.

    Args:
        collection: The collection path (supports nested paths like
            ``"users/uid/orders"``).
        document: The document ID.
        gcp_credentials: Credentials to use for authentication with GCP.
        project: Name of the project to use; overrides the
            gcp_credentials project if provided.
        database: Name of the Firestore database to use.

    Returns:
        The document data as a dictionary, or ``None`` if the document
        does not exist.

    Example:
        ```python
        from prefect import flow
        from prefect_gcp import GcpCredentials
        from prefect_gcp.firestore import get_document

        @flow()
        def example_get_document_flow():
            gcp_credentials = GcpCredentials(project="project")
            data = get_document("my_collection", "my_doc", gcp_credentials)
            return data

        example_get_document_flow()
        ```
    """
    client = _get_client(gcp_credentials, project=project, database=database)
    doc_ref = client.collection(collection).document(document)
    snapshot = doc_ref.get()
    if snapshot.exists:
        return snapshot.to_dict()
    return None


@task
async def alist_documents(
    collection: str,
    gcp_credentials: "GcpCredentials",
    project: Optional[str] = None,
    database: str = "(default)",
    limit: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """
    Lists documents in a Firestore collection.

    Args:
        collection: The collection path (supports nested paths like
            ``"users/uid/orders"``).
        gcp_credentials: Credentials to use for authentication with GCP.
        project: Name of the project to use; overrides the
            gcp_credentials project if provided.
        database: Name of the Firestore database to use.
        limit: Maximum number of documents to return.

    Returns:
        A list of dictionaries, each containing an ``"id"`` key with the
        document ID and the document data.

    Example:
        ```python
        from prefect import flow
        from prefect_gcp import GcpCredentials
        from prefect_gcp.firestore import alist_documents

        @flow()
        async def example_list_documents_flow():
            gcp_credentials = GcpCredentials(project="project")
            docs = await alist_documents("my_collection", gcp_credentials)
            return docs

        example_list_documents_flow()
        ```
    """
    logger = get_run_logger()
    logger.info("Listing documents in %s", collection)

    client = _get_client(gcp_credentials, project=project, database=database)
    col_ref = client.collection(collection)
    if limit is not None:
        col_ref = col_ref.limit(limit)
    docs = await to_thread.run_sync(lambda: col_ref.stream())
    return [{"id": doc.id, **doc.to_dict()} for doc in docs]


@task
@async_dispatch(alist_documents)
def list_documents(
    collection: str,
    gcp_credentials: "GcpCredentials",
    project: Optional[str] = None,
    database: str = "(default)",
    limit: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """
    Lists documents in a Firestore collection.

    Args:
        collection: The collection path (supports nested paths like
            ``"users/uid/orders"``).
        gcp_credentials: Credentials to use for authentication with GCP.
        project: Name of the project to use; overrides the
            gcp_credentials project if provided.
        database: Name of the Firestore database to use.
        limit: Maximum number of documents to return.

    Returns:
        A list of dictionaries, each containing an ``"id"`` key with the
        document ID and the document data.

    Example:
        ```python
        from prefect import flow
        from prefect_gcp import GcpCredentials
        from prefect_gcp.firestore import list_documents

        @flow()
        def example_list_documents_flow():
            gcp_credentials = GcpCredentials(project="project")
            docs = list_documents("my_collection", gcp_credentials)
            return docs

        example_list_documents_flow()
        ```
    """
    client = _get_client(gcp_credentials, project=project, database=database)
    col_ref = client.collection(collection)
    if limit is not None:
        col_ref = col_ref.limit(limit)
    docs = col_ref.stream()
    return [{"id": doc.id, **doc.to_dict()} for doc in docs]


@task
async def aupdate_document(
    collection: str,
    document: str,
    data: Dict[str, Any],
    gcp_credentials: "GcpCredentials",
    project: Optional[str] = None,
    database: str = "(default)",
) -> str:
    """
    Updates an existing document in a Firestore collection. Raises
    ``google.api_core.exceptions.NotFound`` if the document does not exist.

    Args:
        collection: The collection path (supports nested paths like
            ``"users/uid/orders"``).
        document: The document ID.
        data: The fields to update as a dictionary.
        gcp_credentials: Credentials to use for authentication with GCP.
        project: Name of the project to use; overrides the
            gcp_credentials project if provided.
        database: Name of the Firestore database to use.

    Returns:
        The full document path.

    Example:
        ```python
        from prefect import flow
        from prefect_gcp import GcpCredentials
        from prefect_gcp.firestore import aupdate_document

        @flow()
        async def example_update_document_flow():
            gcp_credentials = GcpCredentials(project="project")
            path = await aupdate_document(
                "my_collection", "my_doc", {"key": "new_value"}, gcp_credentials
            )
            return path

        example_update_document_flow()
        ```
    """
    logger = get_run_logger()
    logger.info("Updating document %s/%s", collection, document)

    client = _get_client(gcp_credentials, project=project, database=database)
    doc_ref = client.collection(collection).document(document)
    await to_thread.run_sync(doc_ref.update, data)
    return doc_ref.path


@task
@async_dispatch(aupdate_document)
def update_document(
    collection: str,
    document: str,
    data: Dict[str, Any],
    gcp_credentials: "GcpCredentials",
    project: Optional[str] = None,
    database: str = "(default)",
) -> str:
    """
    Updates an existing document in a Firestore collection. Raises
    ``google.api_core.exceptions.NotFound`` if the document does not exist.

    Args:
        collection: The collection path (supports nested paths like
            ``"users/uid/orders"``).
        document: The document ID.
        data: The fields to update as a dictionary.
        gcp_credentials: Credentials to use for authentication with GCP.
        project: Name of the project to use; overrides the
            gcp_credentials project if provided.
        database: Name of the Firestore database to use.

    Returns:
        The full document path.

    Example:
        ```python
        from prefect import flow
        from prefect_gcp import GcpCredentials
        from prefect_gcp.firestore import update_document

        @flow()
        def example_update_document_flow():
            gcp_credentials = GcpCredentials(project="project")
            path = update_document(
                "my_collection", "my_doc", {"key": "new_value"}, gcp_credentials
            )
            return path

        example_update_document_flow()
        ```
    """
    client = _get_client(gcp_credentials, project=project, database=database)
    doc_ref = client.collection(collection).document(document)
    doc_ref.update(data)
    return doc_ref.path


@task
async def adelete_document(
    collection: str,
    document: str,
    gcp_credentials: "GcpCredentials",
    project: Optional[str] = None,
    database: str = "(default)",
) -> str:
    """
    Deletes a document from a Firestore collection.

    Args:
        collection: The collection path (supports nested paths like
            ``"users/uid/orders"``).
        document: The document ID.
        gcp_credentials: Credentials to use for authentication with GCP.
        project: Name of the project to use; overrides the
            gcp_credentials project if provided.
        database: Name of the Firestore database to use.

    Returns:
        The full document path.

    Example:
        ```python
        from prefect import flow
        from prefect_gcp import GcpCredentials
        from prefect_gcp.firestore import adelete_document

        @flow()
        async def example_delete_document_flow():
            gcp_credentials = GcpCredentials(project="project")
            path = await adelete_document(
                "my_collection", "my_doc", gcp_credentials
            )
            return path

        example_delete_document_flow()
        ```
    """
    logger = get_run_logger()
    logger.info("Deleting document %s/%s", collection, document)

    client = _get_client(gcp_credentials, project=project, database=database)
    doc_ref = client.collection(collection).document(document)
    await to_thread.run_sync(lambda: doc_ref.delete())
    return doc_ref.path


@task
@async_dispatch(adelete_document)
def delete_document(
    collection: str,
    document: str,
    gcp_credentials: "GcpCredentials",
    project: Optional[str] = None,
    database: str = "(default)",
) -> str:
    """
    Deletes a document from a Firestore collection.

    Args:
        collection: The collection path (supports nested paths like
            ``"users/uid/orders"``).
        document: The document ID.
        gcp_credentials: Credentials to use for authentication with GCP.
        project: Name of the project to use; overrides the
            gcp_credentials project if provided.
        database: Name of the Firestore database to use.

    Returns:
        The full document path.

    Example:
        ```python
        from prefect import flow
        from prefect_gcp import GcpCredentials
        from prefect_gcp.firestore import delete_document

        @flow()
        def example_delete_document_flow():
            gcp_credentials = GcpCredentials(project="project")
            path = delete_document(
                "my_collection", "my_doc", gcp_credentials
            )
            return path

        example_delete_document_flow()
        ```
    """
    client = _get_client(gcp_credentials, project=project, database=database)
    doc_ref = client.collection(collection).document(document)
    doc_ref.delete()
    return doc_ref.path


@task
async def aquery_collection(
    collection: str,
    gcp_credentials: "GcpCredentials",
    project: Optional[str] = None,
    database: str = "(default)",
    filters: Optional[List[Tuple[str, str, Any]]] = None,
    order_by: Optional[str] = None,
    limit: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """
    Queries documents in a Firestore collection with optional filters,
    ordering, and limits.

    Args:
        collection: The collection path (supports nested paths like
            ``"users/uid/orders"``).
        gcp_credentials: Credentials to use for authentication with GCP.
        project: Name of the project to use; overrides the
            gcp_credentials project if provided.
        database: Name of the Firestore database to use.
        filters: A list of filter tuples, each in the form
            ``(field, operator, value)`` (e.g., ``[("age", ">=", 21)]``).
        order_by: Field name to order results by.
        limit: Maximum number of documents to return.

    Returns:
        A list of dictionaries, each containing an ``"id"`` key with the
        document ID and the document data.

    Example:
        ```python
        from prefect import flow
        from prefect_gcp import GcpCredentials
        from prefect_gcp.firestore import aquery_collection

        @flow()
        async def example_query_collection_flow():
            gcp_credentials = GcpCredentials(project="project")
            docs = await aquery_collection(
                "my_collection",
                gcp_credentials,
                filters=[("age", ">=", 21)],
                order_by="age",
                limit=10,
            )
            return docs

        example_query_collection_flow()
        ```
    """
    logger = get_run_logger()
    logger.info("Querying collection %s", collection)

    client = _get_client(gcp_credentials, project=project, database=database)
    query = client.collection(collection)

    if filters:
        for field, op, value in filters:
            query = query.where(filter=FieldFilter(field, op, value))

    if order_by is not None:
        query = query.order_by(order_by)

    if limit is not None:
        query = query.limit(limit)

    docs = await to_thread.run_sync(lambda: query.stream())
    return [{"id": doc.id, **doc.to_dict()} for doc in docs]


@task
@async_dispatch(aquery_collection)
def query_collection(
    collection: str,
    gcp_credentials: "GcpCredentials",
    project: Optional[str] = None,
    database: str = "(default)",
    filters: Optional[List[Tuple[str, str, Any]]] = None,
    order_by: Optional[str] = None,
    limit: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """
    Queries documents in a Firestore collection with optional filters,
    ordering, and limits.

    Args:
        collection: The collection path (supports nested paths like
            ``"users/uid/orders"``).
        gcp_credentials: Credentials to use for authentication with GCP.
        project: Name of the project to use; overrides the
            gcp_credentials project if provided.
        database: Name of the Firestore database to use.
        filters: A list of filter tuples, each in the form
            ``(field, operator, value)`` (e.g., ``[("age", ">=", 21)]``).
        order_by: Field name to order results by.
        limit: Maximum number of documents to return.

    Returns:
        A list of dictionaries, each containing an ``"id"`` key with the
        document ID and the document data.

    Example:
        ```python
        from prefect import flow
        from prefect_gcp import GcpCredentials
        from prefect_gcp.firestore import query_collection

        @flow()
        def example_query_collection_flow():
            gcp_credentials = GcpCredentials(project="project")
            docs = query_collection(
                "my_collection",
                gcp_credentials,
                filters=[("age", ">=", 21)],
                order_by="age",
                limit=10,
            )
            return docs

        example_query_collection_flow()
        ```
    """
    client = _get_client(gcp_credentials, project=project, database=database)
    query = client.collection(collection)

    if filters:
        for field, op, value in filters:
            query = query.where(filter=FieldFilter(field, op, value))

    if order_by is not None:
        query = query.order_by(order_by)

    if limit is not None:
        query = query.limit(limit)

    docs = query.stream()
    return [{"id": doc.id, **doc.to_dict()} for doc in docs]
