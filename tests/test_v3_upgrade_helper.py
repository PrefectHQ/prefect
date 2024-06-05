"""
Tests for the migration_helper module.
"""
import importlib
import sys

import pytest

from prefect._internal.compatibility.v3_upgrade_helper import (
    ModuleMovedError,
    ModuleRemovedError,
    handle_moved_objects,
)


class MockModule:
    pass


@pytest.fixture
def setup_module():
    module_name = "mock_module"
    module = MockModule()
    sys.modules[module_name] = module

    moved_modules = {
        "mock_module.GCS": ("class", "mock_module_new.GCS"),
        "mock_module.Azure": ("class", "mock_module_new.Azure"),
        "mock_module.OldClass": (
            "class",
            "Removed: Use mock_module_new.NewClass instead",
        ),
    }

    yield module_name, moved_modules

    del sys.modules[module_name]


def test_special_attributes(setup_module):
    module_name, moved_modules = setup_module
    handle_moved_objects(module_name, moved_modules)

    module = sys.modules[module_name]

    with pytest.raises(AttributeError):
        getattr(module, "__name__")

    with pytest.raises(AttributeError):
        getattr(module, "__path__")


def test_moved_module(setup_module):
    module_name, moved_modules = setup_module
    handle_moved_objects(module_name, moved_modules)

    module = sys.modules[module_name]

    with pytest.raises(
        ModuleMovedError,
        match="Class 'mock_module.Azure' has been moved to 'mock_module_new.Azure'. Please update your import.",
    ):
        getattr(module, "Azure")

    with pytest.raises(
        ModuleMovedError,
        match="Class 'mock_module.Azure' has been moved to 'mock_module_new.Azure'. Please update your import.",
    ):
        getattr(importlib.import_module("mock_module"), "Azure")


def test_removed_module(setup_module):
    module_name, moved_modules = setup_module
    handle_moved_objects(module_name, moved_modules)

    module = sys.modules[module_name]

    with pytest.raises(
        ModuleRemovedError,
        match="Class 'mock_module.OldClass' has been removed. Use mock_module_new.NewClass instead",
    ):
        getattr(module, "OldClass")


def test_nonexistent_module(setup_module):
    module_name, moved_modules = setup_module
    handle_moved_objects(module_name, moved_modules)

    module = sys.modules[module_name]

    with pytest.raises(
        AttributeError, match="'Nonexistent' not found in 'mock_module'."
    ):
        getattr(module, "Nonexistent")
