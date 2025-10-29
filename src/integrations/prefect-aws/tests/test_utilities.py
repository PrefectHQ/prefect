import pytest
from prefect_aws.utilities import (
    assemble_document_for_patches,
    ensure_path_exists,
    hash_collection,
)


class TestHashCollection:
    def test_simple_dict(self):
        simple_dict = {"key1": "value1", "key2": "value2"}
        assert hash_collection(simple_dict) == hash_collection(
            simple_dict
        ), "Simple dictionary hashing failed"

    def test_nested_dict(self):
        nested_dict = {"key1": {"subkey1": "subvalue1"}, "key2": "value2"}
        assert hash_collection(nested_dict) == hash_collection(
            nested_dict
        ), "Nested dictionary hashing failed"

    def test_complex_structure(self):
        complex_structure = {
            "key1": [1, 2, 3],
            "key2": {"subkey1": {"subsubkey1": "value"}},
        }
        assert hash_collection(complex_structure) == hash_collection(
            complex_structure
        ), "Complex structure hashing failed"

    def test_unhashable_structure(self):
        typically_unhashable_structure = dict(key=dict(subkey=[1, 2, 3]))
        with pytest.raises(TypeError):
            hash(typically_unhashable_structure)
        assert hash_collection(typically_unhashable_structure) == hash_collection(
            typically_unhashable_structure
        ), "Unhashable structure hashing failed after transformation"


class TestAssembleDocumentForPatches:
    def test_initial_document(self):
        patches = [
            {"op": "replace", "path": "/name", "value": "Jane"},
            {"op": "add", "path": "/contact/address", "value": "123 Main St"},
            {"op": "remove", "path": "/age"},
        ]

        initial_document = assemble_document_for_patches(patches)

        expected_document = {"name": {}, "contact": {}, "age": {}}

        assert initial_document == expected_document, "Initial document assembly failed"


class TestEnsurePathExists:
    def test_existing_path(self):
        doc = {"key1": {"subkey1": "value1"}}
        path = ["key1", "subkey1"]
        ensure_path_exists(doc, path)
        assert doc == {
            "key1": {"subkey1": "value1"}
        }, "Existing path modification failed"

    def test_new_path_object(self):
        doc = {}
        path = ["key1", "subkey1"]
        ensure_path_exists(doc, path)
        assert doc == {"key1": {"subkey1": {}}}, "New path creation for object failed"

    def test_new_path_array(self):
        doc = {}
        path = ["key1", "0"]
        ensure_path_exists(doc, path)
        assert doc == {"key1": [{}]}, "New path creation for array failed"

    def test_existing_path_array(self):
        doc = {"key1": [{"subkey1": "value1"}]}
        path = ["key1", "0", "subkey1"]
        ensure_path_exists(doc, path)
        assert doc == {
            "key1": [{"subkey1": "value1"}]
        }, "Existing path modification for array failed"

    def test_existing_path_array_index_out_of_range(self):
        doc = {"key1": []}
        path = ["key1", "0", "subkey1"]
        ensure_path_exists(doc, path)
        assert doc == {
            "key1": [{"subkey1": {}}]
        }, "Existing path modification for array index out of range failed"
