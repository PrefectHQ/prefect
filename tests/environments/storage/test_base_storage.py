from typing import Type
from unittest.mock import PropertyMock

import pytest

import prefect
from prefect.environments.storage import Storage


@pytest.fixture
def sub() -> Type[Storage]:
    class Subclass(Storage):
        def __contains__(self, other):
            return False

        def add_flow(self, flow):
            pass

        def build(self, flow):
            pass

    return Subclass


@pytest.fixture
def inst(sub) -> Storage:
    return sub(
        secrets=["secret1", "secret2"],
        labels=["label1", "label2"],
        add_default_labels=True,
    )


def test_create_base_storage():
    with pytest.raises(TypeError):
        storage = Storage()


class TestStorageLabels:
    def test_doesnt_include_default_labels(self, inst):

        type(inst).default_labels = PropertyMock(
            return_value=["default_1", "default_2"]
        )

        inst.add_default_labels = False

        assert inst.labels == inst._labels

    def test_includes_default_labels(self, inst):

        type(inst).default_labels = PropertyMock(
            return_value=["default_1", "default_2"]
        )

        assert sorted(inst.labels) == sorted(
            ["label1", "label2", "default_1", "default_2"]
        )

    def test_deduplicates_labels(self, inst):
        type(inst).default_labels = PropertyMock(return_value=["label1"])
        assert sorted(inst.labels) == ["label1", "label2"]

    def test_no_default_labels(self, inst):
        assert inst.default_labels == []
