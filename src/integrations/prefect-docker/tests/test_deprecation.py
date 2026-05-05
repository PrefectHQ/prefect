"""Verify the legacy `prefect_docker.experimental` import paths still work and warn."""

import importlib
import warnings


def _reimport(module_name: str):
    import sys

    for key in list(sys.modules):
        if key == module_name or key.startswith(f"{module_name}."):
            del sys.modules[key]
    return importlib.import_module(module_name)


def test_experimental_package_warns_and_exports_decorator():
    with warnings.catch_warnings(record=True) as captured:
        warnings.simplefilter("always")
        module = _reimport("prefect_docker.experimental")

    assert hasattr(module, "docker")
    assert any(
        "prefect_docker.experimental" in str(w.message)
        for w in captured
        if issubclass(w.category, DeprecationWarning)
    )


def test_experimental_decorators_module_warns_and_exports_decorator():
    with warnings.catch_warnings(record=True) as captured:
        warnings.simplefilter("always")
        module = _reimport("prefect_docker.experimental.decorators")

    assert hasattr(module, "docker")
    assert any(
        "prefect_docker.experimental.decorators" in str(w.message)
        for w in captured
        if issubclass(w.category, DeprecationWarning)
    )
