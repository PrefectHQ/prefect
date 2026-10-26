"""Regression tests for prefect-azure packaging metadata.

``prefect-azure`` used to declare an unconditional ``setuptools<81`` runtime
dependency so that ``pkg_resources`` remained importable for ``azureml-core``
(AzureML imports ``pkg_resources`` at runtime on older supported versions).
AzureML is optional, so the cap belongs on the ML extras — an unconditional
cap forces resolvers to downgrade ``prefect-azure`` (or hold back
``setuptools``) for users who never install AzureML. See
https://github.com/PrefectHQ/prefect/pull/23583.
"""

import subprocess
import sys
import tomllib
import zipfile
from email.parser import Parser
from pathlib import Path

import pytest

PACKAGE_DIR = Path(__file__).resolve().parent.parent
PYPROJECT_TOML = PACKAGE_DIR / "pyproject.toml"


@pytest.fixture(scope="module")
def pyproject():
    with PYPROJECT_TOML.open("rb") as f:
        return tomllib.load(f)


def _deps_starting_with(deps, name):
    return [d for d in deps if d.split(";")[0].strip().lower().startswith(name)]


def test_base_dependencies_do_not_require_setuptools(pyproject):
    """Ordinary installs must not inherit AzureML's setuptools cap."""
    base_deps = pyproject["project"]["dependencies"]
    assert _deps_starting_with(base_deps, "setuptools") == []


def test_ml_extras_carry_the_setuptools_cap(pyproject):
    """extras that pull in azureml-core must still pin setuptools<81 so
    pkg_resources is available for older supported AzureML versions."""
    extras = pyproject["project"]["optional-dependencies"]
    for extra in ("ml_datastore", "all_extras"):
        deps = extras[extra]
        assert any(dep.startswith("azureml-core") for dep in deps), (
            f"{extra} should install azureml-core"
        )
        assert _deps_starting_with(deps, "setuptools") == ["setuptools<81"], (
            f"{extra} must cap setuptools<81 for pkg_resources"
        )


def test_dev_dependency_group_pins_setuptools(pyproject):
    """The dev group installs azureml-core, so it needs pkg_resources too."""
    dev_deps = pyproject["dependency-groups"]["dev"]
    assert any(dep.startswith("azureml-core") for dep in dev_deps)
    assert _deps_starting_with(dev_deps, "setuptools") == ["setuptools<81"]


def test_built_wheel_scopes_setuptools_to_ml_extras(tmp_path, pyproject):
    """Build the wheel and assert the setuptools requirement only appears in
    the ml_datastore/all_extras extras' Requires-Dist metadata."""
    expected_extras = set(pyproject["project"]["optional-dependencies"])

    subprocess.run(
        ["uv", "build", "--wheel", "--out-dir", str(tmp_path)],
        cwd=PACKAGE_DIR,
        check=True,
        capture_output=True,
        text=True,
    )
    wheels = list(tmp_path.glob("*.whl"))
    assert len(wheels) == 1, f"expected one wheel, got {wheels}"

    with zipfile.ZipFile(wheels[0]) as zf:
        metadata_name = next(n for n in zf.namelist() if n.endswith("METADATA"))
        metadata = Parser().parsestr(zf.read(metadata_name).decode())

    requires = metadata.get_all("Requires-Dist") or []
    setuptools_reqs = [r for r in requires if r.lower().startswith("setuptools")]
    # non-setuptools requirements must not be conditioned on ML extras
    other_extra_reqs = [
        r
        for r in requires
        if not r.lower().startswith("setuptools")
        and ('extra == "ml-datastore"' in r or 'extra == "all-extras"' in r)
    ]

    assert setuptools_reqs, "wheel should still require setuptools for ML extras"
    for req in setuptools_reqs:
        assert "setuptools<81" in req.replace(" ", "")
        assert "extra ==" in req
        # wheel metadata normalizes extra names per PEP 685 ('-' not '_')
        marker_extra = req.split('extra == "')[1].rstrip('"').replace("-", "_")
        assert marker_extra in {"ml_datastore", "all_extras"}

    marked_extras = {
        req.split('extra == "')[1].rstrip('"').replace("-", "_")
        for req in setuptools_reqs
    }
    assert marked_extras == {"ml_datastore", "all_extras"}
    # sanity: azureml is only ever required by those same extras, and no
    # unrelated extra (blob_storage/cosmos_db) carries a setuptools requirement
    assert expected_extras >= marked_extras
    assert not any(r.lower().startswith("setuptools") for r in other_extra_reqs)


BASE_MODULES = [
    "prefect_azure",
    "prefect_azure.credentials",
    "prefect_azure.blob_storage",
    "prefect_azure.cosmos_db",
    "prefect_azure.container_instance",
    "prefect_azure.workers.container_instance",
    "prefect_azure.repository",
    "prefect_azure.plugins",
]


def test_base_modules_import_without_pkg_resources():
    """Smoke test: importing the base package and its non-ML modules must not
    touch ``pkg_resources`` (which only exists under setuptools<81).

    ``prefect_azure.ml_datastore`` is intentionally excluded: it imports
    ``azureml-core``, which is exactly the code path that still needs
    ``pkg_resources``. ``prefect_azure.deployments.steps`` is also excluded:
    it requires the ``blob_storage`` extra.
    """
    blocker = """
import sys

class _BlockPkgResources:
    def find_spec(self, name, path=None, target=None):
        if name == "pkg_resources" or name.startswith("pkg_resources."):
            raise ImportError("pkg_resources is not available (setuptools>=81)")
        return None

sys.meta_path.insert(0, _BlockPkgResources())
sys.modules.pop("pkg_resources", None)
"""
    imports = "\n".join(f"import {mod}" for mod in BASE_MODULES)
    result = subprocess.run(
        [sys.executable, "-c", blocker + imports],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, (
        "base prefect_azure modules must import without pkg_resources:\n"
        f"{result.stderr}"
    )
