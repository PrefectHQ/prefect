import importlib
import sys

import pytest

import prefect.server


@pytest.fixture(autouse=True)
def reset_sys_modules():
    original_modules = sys.modules.copy()

    yield

    # Delete all of the module objects that were introduced so they are not cached
    for module in set(sys.modules.keys()):
        if module not in original_modules:
            del sys.modules[module]

    importlib.invalidate_caches()
    sys.modules = original_modules


def test_import_orion_module():
    with pytest.warns(
        DeprecationWarning,
        match="The 'prefect.orion' module has been deprecated. It will not be available after Aug 2023. Use 'prefect.server' instead.",
    ):
        pass


def test_import_orion_submodule():
    with pytest.warns(
        DeprecationWarning,
        match="The 'prefect.orion' module has been deprecated. It will not be available after Aug 2023. Use 'prefect.server' instead.",
    ):
        import prefect.orion.schemas

    assert prefect.orion.schemas is prefect.server.schemas


def test_import_module_from_orion_module():
    with pytest.warns(
        DeprecationWarning,
        match="The 'prefect.orion' module has been deprecated. It will not be available after Aug 2023. Use 'prefect.server' instead.",
    ):
        from prefect.orion import models

    assert models is prefect.server.models


def test_import_object_from_from_orion_submodule():
    with pytest.warns(
        DeprecationWarning,
        match="The 'prefect.orion' module has been deprecated. It will not be available after Aug 2023. Use 'prefect.server' instead.",
    ):
        from prefect.orion.schemas.states import State

    assert State is prefect.server.schemas.states.State
