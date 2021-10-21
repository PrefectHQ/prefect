import pytest

from prefect.utilities.importtools import import_object


def test_import_object():
    rand = import_object("random")
    randint = import_object("random.randint")
    import random

    assert rand is random
    assert randint is random.randint


def test_import_object_submodule_not_an_attribute():
    # `hello_world` is not in the `prefect` top-level
    hello_world = import_object("prefect.hello_world")
    import prefect.hello_world

    assert hello_world is prefect.hello_world


def test_import_object_module_does_not_exist():
    with pytest.raises(ImportError):
        import_object("random_module_name_that_does_not_exist")


def test_import_object_attribute_does_not_exist():
    with pytest.raises(AttributeError):
        import_object("random.random_attribute_that_does_not_exist")
