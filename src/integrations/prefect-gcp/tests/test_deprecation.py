"""Verify the legacy `prefect_gcp.experimental` import paths still work and warn."""

import importlib
import warnings


def _reimport(module_name: str):
    import sys

    for key in list(sys.modules):
        if key == module_name or key.startswith(f"{module_name}."):
            del sys.modules[key]
    return importlib.import_module(module_name)


def test_experimental_package_warns_and_exports_decorators():
    with warnings.catch_warnings(record=True) as captured:
        warnings.simplefilter("always")
        module = _reimport("prefect_gcp.experimental")

    assert hasattr(module, "cloud_run")
    assert hasattr(module, "vertex_ai")
    assert any(
        "prefect_gcp.experimental" in str(w.message)
        for w in captured
        if issubclass(w.category, DeprecationWarning)
    )


def test_experimental_decorators_module_warns_and_exports_decorators():
    with warnings.catch_warnings(record=True) as captured:
        warnings.simplefilter("always")
        module = _reimport("prefect_gcp.experimental.decorators")

    assert hasattr(module, "cloud_run")
    assert hasattr(module, "vertex_ai")
    assert any(
        "prefect_gcp.experimental.decorators" in str(w.message)
        for w in captured
        if issubclass(w.category, DeprecationWarning)
    )


def test_experimental_bundles_upload_warns_and_exposes_main():
    with warnings.catch_warnings(record=True) as captured:
        warnings.simplefilter("always")
        module = _reimport("prefect_gcp.experimental.bundles.upload")

    assert callable(getattr(module, "main", None))
    assert any(
        "prefect_gcp.experimental.bundles.upload" in str(w.message)
        for w in captured
        if issubclass(w.category, DeprecationWarning)
    )


def test_experimental_bundles_execute_warns_and_exposes_main():
    with warnings.catch_warnings(record=True) as captured:
        warnings.simplefilter("always")
        module = _reimport("prefect_gcp.experimental.bundles.execute")

    assert callable(getattr(module, "main", None))
    assert any(
        "prefect_gcp.experimental.bundles.execute" in str(w.message)
        for w in captured
        if issubclass(w.category, DeprecationWarning)
    )
