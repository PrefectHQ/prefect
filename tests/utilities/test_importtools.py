import asyncio
import importlib.util
import runpy
import sys
from pathlib import Path
from textwrap import dedent
from types import ModuleType

import pytest

import prefect
from prefect import __development_base_path__
from prefect.exceptions import ScriptError
from prefect.utilities.filesystem import tmpchdir
from prefect.utilities.importtools import (
    from_qualified_name,
    import_object,
    lazy_import,
    load_script_as_module,
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


def test_lazy_import_fails_for_missing_modules():
    with pytest.raises(ModuleNotFoundError, match="flibbidy"):
        lazy_import("flibbidy", error_on_import=True)


def test_lazy_import_allows_deferred_failure_for_missing_module():
    module = lazy_import("flibbidy", error_on_import=False)
    assert isinstance(module, ModuleType)
    with pytest.raises(ModuleNotFoundError, match="No module named 'flibbidy'") as exc:
        module.foo
    assert "No module named 'flibbidy'" in exc.exconly(), (
        "Exception should contain error message"
    )


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
        # below are cases that used to fail; see https://github.com/PrefectHQ/prefect/pull/17524
        (
            TEST_PROJECTS_DIR,
            Path("tree-project") / "imports" / "implicit_relative.py",
        ),
        (TEST_PROJECTS_DIR / "tree-project" / "imports", "implicit_relative.py"),
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
        # below are cases that used to fail; see https://github.com/PrefectHQ/prefect/pull/17524
        (TEST_PROJECTS_DIR, "implicit_relative.foobar"),
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
    # module-level variables should be present
    assert "x" in namespace
    assert "y" in namespace
    assert "now" in namespace
    # module-level classes should be present
    assert "MyModel" in namespace
    # module-level functions should be present
    assert "my_fn" in namespace

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


def test_safe_load_namespace_ignores_code_in_if_name_equals_main_block():
    source_code = dedent(
        """
        import math

        x = 10
        y = math.sqrt(x)


        if __name__ == "__main__":
            z = 10
    """
    )

    # should not raise any errors
    namespace = safe_load_namespace(source_code)

    assert "x" in namespace
    assert "y" in namespace
    assert "z" not in namespace


def test_safe_load_namespace_does_not_execute_function_body():
    """
    Regression test for https://github.com/PrefectHQ/prefect/issues/14402
    """
    source_code = dedent(
        """
        you_done_goofed = False

        def my_fn():
            nonlocal you_done_goofed
            you_done_goofed = True

        def my_other_fn():
            foo = my_fn()
    """
    )

    # should not raise any errors
    namespace = safe_load_namespace(source_code)

    assert not namespace["you_done_goofed"]


def test_safe_load_namespace_implicit_relative_imports():
    """
    Regression test for https://github.com/PrefectHQ/prefect/issues/15352
    """
    path = TEST_PROJECTS_DIR / "flat-project" / "implicit_relative.py"
    source_code = path.read_text()

    namespace = safe_load_namespace(source_code, filepath=str(path))
    assert "get_foo" in namespace
    assert "get_bar" in namespace


def test_concurrent_script_loading(tmpdir: Path):
    """Test that loading multiple scripts concurrently is thread-safe.

    This is a regression test for https://github.com/PrefectHQ/prefect/issues/16452
    """
    script_contents = """
def hello():
    return "Hello from {}"
"""

    scripts: list[str] = []

    for i in range(5):
        path = tmpdir / f"script_{i}.py"
        path.write_text(script_contents.format(i), encoding="utf-8")
        scripts.append(str(path))

    loaded_modules: list[ModuleType] = []
    errors: list[Exception] = []

    async def load_script(path: str) -> str:
        try:
            module = load_script_as_module(path)
            loaded_modules.append(module)
            return module.hello()
        except Exception as e:
            errors.append(e)
            raise

    async def run_concurrent_loads():
        futures = [load_script(script) for script in scripts]
        return await asyncio.gather(*futures)

    results = asyncio.run(run_concurrent_loads())

    assert not errors, f"Errors occurred during concurrent loading: {errors}"
    assert len(results) == 5
    assert sorted(results) == [f"Hello from {i}" for i in range(5)]

    module_names = [m.__name__ for m in loaded_modules]
    assert len(module_names) == len(set(module_names)), "Duplicate module names found"
