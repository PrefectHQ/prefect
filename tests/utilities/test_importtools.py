import importlib.util
import runpy
import sys
from pathlib import Path
from textwrap import dedent
from types import ModuleType
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

import prefect
from prefect import __development_base_path__
from prefect.exceptions import ScriptError
from prefect.utilities.dockerutils import docker_client
from prefect.utilities.filesystem import tmpchdir
from prefect.utilities.importtools import (
    from_qualified_name,
    import_object,
    lazy_import,
    safe_load_namespace,
    to_qualified_name,
)

TEST_PROJECTS_DIR = __development_base_path__ / "tests" / "test-projects"


def my_fn():
    pass


class Foo:
    pass


# Note we use the hosted API to avoid Postgres engine caching errors
pytest.mark.usefixtures("hosted_orion")


@pytest.mark.parametrize(
    "obj,expected",
    [
        (to_qualified_name, "prefect.utilities.importtools.to_qualified_name"),
        (prefect.tasks.Task, "prefect.tasks.Task"),
        (prefect.tasks.Task.__call__, "prefect.tasks.Task.__call__"),
        (lambda x: x + 1, "tests.utilities.test_importtools.<lambda>"),
        (my_fn, "tests.utilities.test_importtools.my_fn"),
    ],
)
def test_to_qualified_name(obj, expected):
    assert to_qualified_name(obj) == expected


@pytest.mark.parametrize("obj", [to_qualified_name, prefect.tasks.Task, my_fn, Foo])
def test_to_and_from_qualified_name_roundtrip(obj):
    assert from_qualified_name(to_qualified_name(obj)) == obj


@pytest.fixture
def pop_docker_module():
    # Allows testing of `lazy_import` on a clean sys
    original = sys.modules.pop("docker")
    try:
        yield
    finally:
        sys.modules["docker"] = original


@pytest.mark.usefixtures("pop_docker_module")
def test_lazy_import():
    docker: ModuleType("docker") = lazy_import("docker")
    assert isinstance(docker, importlib.util._LazyModule)
    assert isinstance(docker, ModuleType)
    assert callable(docker.from_env)


@pytest.mark.service("docker")
def test_cant_find_docker_error(monkeypatch):
    docker = lazy_import("docker")
    docker.errors = lazy_import("docker.errors")
    monkeypatch.setattr(
        "docker.DockerClient.from_env",
        MagicMock(side_effect=docker.errors.DockerException),
    )
    with pytest.raises(RuntimeError, match="Docker is not running"):
        with docker_client() as _:
            return None


@pytest.mark.service("docker")
def test_lazy_import_does_not_break_type_comparisons():
    docker = lazy_import("docker")
    docker.errors = lazy_import("docker.errors")

    with docker_client() as client:
        try:
            client.containers.get(uuid4().hex)  # Better not exist
        except docker.errors.NotFound:
            pass

    # The exception should not raise but can raise if `lazy_import` creates a duplicate
    # copy of the `docker` module


def test_lazy_import_fails_for_missing_modules():
    with pytest.raises(ModuleNotFoundError, match="flibbidy"):
        lazy_import("flibbidy", error_on_import=True)


def test_lazy_import_allows_deferred_failure_for_missing_module():
    module = lazy_import("flibbidy", error_on_import=False)
    assert isinstance(module, ModuleType)
    with pytest.raises(ModuleNotFoundError, match="No module named 'flibbidy'") as exc:
        module.foo
    assert (
        "module = lazy_import" in exc.exconly()
    ), "Exception should contain original line in message"


def test_lazy_import_includes_help_message_for_missing_modules():
    with pytest.raises(
        ModuleNotFoundError, match="No module named 'flibbidy'.\nHello world"
    ):
        lazy_import("flibbidy", error_on_import=True, help_message="Hello world")


def test_lazy_import_includes_help_message_in_deferred_failure():
    module = lazy_import(
        "flibbidy",
        error_on_import=False,
        help_message="No module named 'flibbidy'.*Hello world",
    )
    assert isinstance(module, ModuleType)
    with pytest.raises(
        ModuleNotFoundError, match="No module named 'flibbidy'.*Hello world"
    ):
        module.foo


@pytest.mark.parametrize(
    "working_directory,script_path",
    [
        # Working directory is not necessary for these imports to work
        (
            __development_base_path__,
            TEST_PROJECTS_DIR / "flat-project" / "implicit_relative.py",
        ),
        (
            __development_base_path__,
            TEST_PROJECTS_DIR / "flat-project" / "explicit_relative.py",
        ),
        (
            __development_base_path__,
            TEST_PROJECTS_DIR / "nested-project" / "implicit_relative.py",
        ),
        (
            __development_base_path__,
            TEST_PROJECTS_DIR / "nested-project" / "explicit_relative.py",
        ),
        # They also work with the working directory set to the project
        (TEST_PROJECTS_DIR / "flat-project", "implicit_relative.py"),
        (TEST_PROJECTS_DIR / "flat-project", "explicit_relative.py"),
        (TEST_PROJECTS_DIR / "nested-project", "implicit_relative.py"),
        (TEST_PROJECTS_DIR / "nested-project", "explicit_relative.py"),
        # The tree structure requires the working directory to be at the base
        (TEST_PROJECTS_DIR / "tree-project", Path("imports") / "implicit_relative.py"),
    ],
)
def test_import_object_from_script_with_relative_imports(
    working_directory, script_path
):
    with tmpchdir(working_directory):
        foobar = import_object(f"{script_path}:foobar")

    assert callable(foobar), f"Expected callable, got {foobar!r}"
    assert foobar() == "foobar"


@pytest.mark.parametrize(
    "working_directory,script_path",
    [
        # Explicit relative imports cannot go up levels with script-based imports
        (TEST_PROJECTS_DIR / "tree-project", Path("imports") / "explicit_relative.py"),
        # Note here the working directory is too far up in the structure
        (
            TEST_PROJECTS_DIR,
            Path("tree-project") / "imports" / "implicit_relative.py",
        ),
        # Note here the working directory is too far down in the structure
        (TEST_PROJECTS_DIR / "tree-project" / "imports", "implicit_relative.py"),
    ],
)
def test_import_object_from_script_with_relative_imports_expected_failures(
    working_directory, script_path
):
    with tmpchdir(working_directory):
        with pytest.raises(ScriptError):
            import_object(f"{script_path}:foobar")

        # Python would raise the same error if running `python <script>`
        with pytest.raises(ImportError):
            runpy.run_path(str(script_path))


@pytest.mark.parametrize(
    "working_directory,import_path",
    [
        # Implicit relative imports work if the working directory is the project
        (TEST_PROJECTS_DIR / "flat-project", "implicit_relative.foobar"),
        (TEST_PROJECTS_DIR / "nested-project", "implicit_relative.foobar"),
        (TEST_PROJECTS_DIR / "tree-project", "imports.implicit_relative.foobar"),
    ],
)
def test_import_object_from_module_with_relative_imports(
    working_directory, import_path
):
    with tmpchdir(working_directory):
        foobar = import_object(import_path)
        assert foobar() == "foobar"


@pytest.mark.parametrize(
    "working_directory,import_path",
    [
        # Explicit relative imports not expected to work
        (TEST_PROJECTS_DIR / "flat-project", "explicit_relative.foobar"),
        (TEST_PROJECTS_DIR / "nested-project", "explicit_relative.foobar"),
        (TEST_PROJECTS_DIR / "tree-project", "imports.explicit_relative.foobar"),
        # Not expected to work if the working directory is not the project
        (TEST_PROJECTS_DIR, "implicit_relative.foobar"),
    ],
)
def test_import_object_from_module_with_relative_imports_expected_failures(
    working_directory, import_path
):
    with tmpchdir(working_directory):
        with pytest.raises((ValueError, ImportError)):
            import_object(import_path)

        # Python would raise the same error
        with pytest.raises((ValueError, ImportError)):
            runpy.run_module(import_path)


def test_safe_load_namespace():
    source_code = dedent(
        """
        import math
        from datetime import datetime
        from pydantic import BaseModel
                         
        class MyModel(BaseModel):
            x: int
                         
        def my_fn():
            return 42

        x = 10
        y = math.sqrt(x)
        now = datetime.now()
    """
    )

    namespace = safe_load_namespace(source_code)

    # module-level imports should be present
    assert "math" in namespace
    assert "datetime" in namespace
    assert "BaseModel" in namespace
    # module-level variables should not be present
    assert "x" not in namespace
    assert "y" not in namespace
    assert "now" not in namespace
    # module-level classes should be present
    assert "MyModel" in namespace
    # module-level functions should not be present
    assert "my_fn" not in namespace

    assert namespace["MyModel"].__name__ == "MyModel"


def test_safe_load_namespace_ignores_import_errors():
    source_code = dedent(
        """
        import flibbidy
                         
        from pydantic import BaseModel
                         
        class MyModel(BaseModel):
            x: int
    """
    )

    # should not raise an ImportError
    namespace = safe_load_namespace(source_code)

    assert "flibbidy" not in namespace
    # other imports and classes should be present
    assert "BaseModel" in namespace
    assert "MyModel" in namespace
    assert namespace["MyModel"].__name__ == "MyModel"


def test_safe_load_namespace_ignore_class_declaration_errors():
    source_code = dedent(
        """
        from fake_pandas import DataFrame
                         
        class CoolDataFrame(DataFrame):
            pass
    """
    )

    # should not raise any errors
    namespace = safe_load_namespace(source_code)

    assert "DataFrame" not in namespace
    assert "CoolDataFrame" not in namespace
