"""Verify the legacy `prefect_aws.experimental` import paths still work and warn."""

import importlib
import warnings


def _reimport(module_name: str):
    """Re-import a module so a fresh import-time warning is emitted."""
    import sys

    for key in list(sys.modules):
        if key == module_name or key.startswith(f"{module_name}."):
            del sys.modules[key]
    return importlib.import_module(module_name)


def test_experimental_package_warns_and_exports_decorator():
    with warnings.catch_warnings(record=True) as captured:
        warnings.simplefilter("always")
        module = _reimport("prefect_aws.experimental")

    assert hasattr(module, "ecs")
    deprecations = [w for w in captured if issubclass(w.category, DeprecationWarning)]
    assert any("prefect_aws.experimental" in str(w.message) for w in deprecations)


def test_experimental_decorators_module_warns_and_exports_decorator():
    with warnings.catch_warnings(record=True) as captured:
        warnings.simplefilter("always")
        module = _reimport("prefect_aws.experimental.decorators")

    assert hasattr(module, "ecs")
    assert any(
        "prefect_aws.experimental.decorators" in str(w.message)
        for w in captured
        if issubclass(w.category, DeprecationWarning)
    )


def test_experimental_bundles_upload_warns_and_exposes_main():
    with warnings.catch_warnings(record=True) as captured:
        warnings.simplefilter("always")
        module = _reimport("prefect_aws.experimental.bundles.upload")

    assert callable(getattr(module, "main", None))
    assert any(
        "prefect_aws.experimental.bundles.upload" in str(w.message)
        for w in captured
        if issubclass(w.category, DeprecationWarning)
    )


def test_experimental_bundles_execute_warns_and_exposes_main():
    with warnings.catch_warnings(record=True) as captured:
        warnings.simplefilter("always")
        module = _reimport("prefect_aws.experimental.bundles.execute")

    assert callable(getattr(module, "main", None))
    assert any(
        "prefect_aws.experimental.bundles.execute" in str(w.message)
        for w in captured
        if issubclass(w.category, DeprecationWarning)
    )
