"""
Import smoke tests for prefect modules.

These tests verify that key prefect modules can be imported without errors
in a clean subprocess, catching circular-import and import-order regressions.
"""

import subprocess
import sys
import textwrap

import pytest

IMPORT_MODULES = [
    "prefect",
    "prefect.client.schemas",
    "prefect.client.schemas.objects",
    "prefect.flows",
    "prefect.deployments",
    "prefect.events",
    "prefect.events.clients",
    "prefect.server",
    "prefect.server.schemas",
    "prefect.server.schemas.core",
    "prefect.server.schemas.actions",
    "prefect.server.models",
    "prefect.server.models.flow_runs",
    "prefect.server.api",
    "prefect.server.api.flow_runs",
    "prefect.server.api.server",
    "prefect.task_runners",
]


@pytest.mark.parametrize("module_name", IMPORT_MODULES, ids=IMPORT_MODULES)
def test_import_module(module_name: str):
    """Each module should import without errors in a fresh subprocess."""
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            textwrap.dedent(f"""\
                import sys
                import {module_name}
                count = sum(1 for k in sys.modules if k.startswith("prefect"))
                print(f"loaded {{count}} prefect modules")
            """),
        ],
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, (
        f"Failed to import {module_name}.\n"
        f"stdout: {result.stdout}\n"
        f"stderr: {result.stderr}"
    )


def test_import_server_subpackages():
    """from prefect.server import schemas, models"""
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            textwrap.dedent("""\
                import sys
                from prefect.server import schemas, models
                count = sum(1 for k in sys.modules if k.startswith("prefect"))
                print(f"loaded {count} prefect modules")
            """),
        ],
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, (
        f"Failed: from prefect.server import schemas, models\n"
        f"stdout: {result.stdout}\n"
        f"stderr: {result.stderr}"
    )


def test_import_server_schema_submodules():
    """from prefect.server.schemas import core, actions"""
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            textwrap.dedent("""\
                import sys
                from prefect.server.schemas import core, actions
                count = sum(1 for k in sys.modules if k.startswith("prefect"))
                print(f"loaded {count} prefect modules")
            """),
        ],
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, (
        f"Failed: from prefect.server.schemas import core, actions\n"
        f"stdout: {result.stdout}\n"
        f"stderr: {result.stderr}"
    )


def test_create_app():
    """from prefect.server.api.server import create_app; create_app()"""
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            textwrap.dedent("""\
                import sys
                from prefect.server.api.server import create_app
                app = create_app()
                count = sum(1 for k in sys.modules if k.startswith("prefect"))
                print(f"loaded {count} prefect modules")
                print(f"app type: {type(app).__name__}")
            """),
        ],
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, (
        f"Failed: create_app()\nstdout: {result.stdout}\nstderr: {result.stderr}"
    )
