"""Utilities for working with AWS services."""

from typing import Dict, List, Union

from prefect.utilities.collections import visit_collection


def hash_collection(collection) -> int:
    """Use visit_collection to transform and hash a collection.

    Args:
        collection (Any): The collection to hash.

    Returns:
        int: The hash of the transformed collection.

    Example:
        ```python
        from prefect_aws.utilities import hash_collection

        hash_collection({"a": 1, "b": 2})
        ```

    """

    def make_hashable(item):
        """Make an item hashable by converting it to a tuple."""
        if isinstance(item, dict):
            return tuple(sorted((k, make_hashable(v)) for k, v in item.items()))
        elif isinstance(item, list):
            return tuple(make_hashable(v) for v in item)
        return item

    hashable_collection = visit_collection(
        collection, visit_fn=make_hashable, return_data=True
    )
    return hash(hashable_collection)


def ensure_path_exists(doc: Union[Dict, List], path: List[str]):
    """
    Ensures the path exists in the document, creating empty dictionaries or lists as
    needed.

    Args:
        doc: The current level of the document or sub-document.
        path: The remaining path parts to ensure exist.
    """
    if not path:
        return
    current_path = path.pop(0)
    # Check if the next path part exists and is a digit
    next_path_is_digit = path and path[0].isdigit()

    # Determine if the current path is for an array or an object
    if isinstance(doc, list):  # Path is for an array index
        current_path = int(current_path)
        # Ensure the current level of the document is a list and long enough

        while len(doc) <= current_path:
            doc.append({})
        next_level = doc[current_path]
    else:  # Path is for an object
        if current_path not in doc or (
            next_path_is_digit and not isinstance(doc.get(current_path), list)
        ):
            doc[current_path] = [] if next_path_is_digit else {}
        next_level = doc[current_path]

    ensure_path_exists(next_level, path)


def assemble_document_for_patches(patches):
    """
    Assembles an initial document that can successfully accept the given JSON Patch
    operations.

    Args:
        patches: A list of JSON Patch operations.

    Returns:
        An initial document structured to accept the patches.

    Example:

    ```python
    patches = [
        {"op": "replace", "path": "/name", "value": "Jane"},
        {"op": "add", "path": "/contact/address", "value": "123 Main St"},
        {"op": "remove", "path": "/age"}
    ]

    initial_document = assemble_document_for_patches(patches)

    #output
    {
        "name": {},
        "contact": {},
        "age": {}
    }
    ```
    """
    document = {}

    for patch in patches:
        operation = patch["op"]
        path = patch["path"].lstrip("/").split("/")

        if operation == "add":
            # Ensure all but the last element of the path exists
            ensure_path_exists(document, path[:-1])
        elif operation in ["remove", "replace"]:
            # For remove and replace, the entire path should exist
            ensure_path_exists(document, path)

    return document
