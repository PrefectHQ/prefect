import importlib.util
import os
import runpy
import sys
from contextlib import contextmanager
from types import ModuleType
from uuid import uuid4

import pytest

import prefect
from prefect import __root_path__
from prefect.docker import docker_client
from prefect.exceptions import ScriptError
from prefect.utilities.importtools import (
    from_qualified_name,
    import_object,
    lazy_import,
    to_qualified_name,
)


@contextmanager
def tmp_chdir(dirpath):
    original = os.getcwd()
    os.chdir(dirpath)
    try:
        yield
    finally:
        os.chdir(original)


TEST_PROJECTS_DIR = __root_path__ / "tests" / "test-projects"


def my_fn():
    pass


class Foo:
    pass


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
    orginal = sys.modules.pop("docker")
    try:
        yield
    finally:
        sys.modules["docker"] = orginal


@pytest.mark.usefixtures("pop_docker_module")
def test_lazy_import():
    docker: ModuleType("docker") = lazy_import("docker")
    assert isinstance(docker, importlib.util._LazyModule)
    assert isinstance(docker, ModuleType)
    assert callable(docker.from_env)


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
    with pytest.raises(ModuleNotFoundError, match=f"No module named 'flibbidy'") as exc:
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
    "script_path",
    [
        TEST_PROJECTS_DIR / "flat-project" / "explicit_relative.py",
        TEST_PROJECTS_DIR / "flat-project" / "implicit_relative.py",
        TEST_PROJECTS_DIR / "nested-project" / "implicit_relative.py",
    ],
)
def test_import_object_from_script_with_relative_imports(script_path):
    # Remove shared_libs if it exists from a prior test or the module can be cached
    sys.modules.pop("shared_libs", None)
    foobar = import_object(f"{script_path}:foobar")
    assert foobar() == "foobar"


@pytest.mark.parametrize(
    "script_path",
    [
        TEST_PROJECTS_DIR / "nested-project" / "explicit_relative.py",
        TEST_PROJECTS_DIR / "tree-project" / "imports" / "explicit_relative.py",
        TEST_PROJECTS_DIR / "tree-project" / "imports" / "implicit_relative.py",
    ],
)
def test_import_object_from_script_with_relative_imports_expected_failures(script_path):
    # Remove shared_libs if it exists from a prior test or the module can be cached
    sys.modules.pop("shared_libs", None)
    with pytest.raises(ScriptError):
        import_object(f"{script_path}:foobar")

    # Python would raise the same error if running `python <script>`
    with pytest.raises(ImportError):
        runpy.run_path(script_path)


@pytest.mark.parametrize(
    "path",
    [
        "flat-project.implicit_relative.foobar",
        "nested-project.implicit_relative.foobar",
        "tree-project.imports.implicit_relative.foobar",
    ],
)
def test_import_object_from_module_with_relative_imports(path: str):
    # Remove shared_libs if it exists from a prior test or the module can be cached
    sys.modules.pop("shared_libs", None)
    project_name, _, import_path = path.partition(".")

    with tmp_chdir(TEST_PROJECTS_DIR / project_name):
        foobar = import_object(import_path)
        assert foobar() == "foobar"


@pytest.mark.parametrize(
    "path",
    [
        "flat-project.explicit_relative.foobar",
        "nested-project.explicit_relative.foobar",
        "tree-project.imports.explicit_relative.foobar",
    ],
)
def test_import_object_from_module_with_relative_imports_expected_failures(path: str):
    # Remove shared_libs if it exists from a prior test or the module can be cached
    sys.modules.pop("shared_libs", None)
    project_name, _, import_path = path.partition(".")

    with tmp_chdir(TEST_PROJECTS_DIR / project_name):
        with pytest.raises(
            (ValueError, ImportError), match="attempted relative import"
        ):
            import_object(import_path)

        # Python would raise the same error
        with pytest.raises(
            (ValueError, ImportError), match="attempted relative import"
        ):
            runpy.run_module(import_path)
