from typing import List, Type
from unittest.mock import PropertyMock

import pytest

from prefect.storage import Local, Docker, Storage, get_default_storage_class
from prefect.utilities.configuration import set_temporary_config


@pytest.fixture
def sub() -> Type[Storage]:
    class Subclass(Local):
        """
        Subclassing `Local` storage instead of `Base` to avoid
        other test failures that ensure all subclasses of the `Base`
        have an accompanying serialization Schema.

        The goal of this subclass is to test all methods of `Base`
        that don't require actual implementation details, so
        we override those methods to ensure we don't interact
        with the external world.
        """

        def __contains__(self, other):

            return False

        def add_flow(self, flow):
            pass

        def build(self, flow):
            pass

        @property
        def default_labels(self) -> List[str]:
            return []

    return Subclass


@pytest.fixture
def inst(sub) -> Storage:
    return sub(
        secrets=["secret1", "secret2"],
        labels=["label1", "label2"],
        add_default_labels=True,
    )


def test_default_storage():
    assert get_default_storage_class() is Local


def test_default_storage_responds_to_config():
    with set_temporary_config(
        {"flows.defaults.storage.default_class": "prefect.storage.Docker"}
    ):
        assert get_default_storage_class() is Docker


def test_default_storage_ignores_bad_config():
    with set_temporary_config({"flows.defaults.storage.default_class": "FOOBAR"}):

        with pytest.warns(UserWarning):
            assert get_default_storage_class() is Local


def test_create_base_storage():
    with pytest.raises(TypeError):
        Storage()


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

    @pytest.mark.parametrize("flag", [True, False])
    def test_uses_provided_default_label_flag(self, sub, flag: bool):
        inst = sub(add_default_labels=flag)
        assert inst.add_default_labels == flag

    @pytest.mark.parametrize("config_value", [True, "test", "hello, world!"])
    def test_uses_config_value_if_not_provided(self, sub, config_value):
        with set_temporary_config(
            {"flows.defaults.storage.add_default_labels": config_value}
        ):
            inst = sub()
            assert inst.add_default_labels == config_value

    def test_add_default_labels_default_true(self, inst):
        assert inst.add_default_labels is True
