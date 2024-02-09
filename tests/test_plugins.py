import importlib
import pathlib
import textwrap
from unittest.mock import Mock

import pytest

import prefect
from prefect.plugins import load_extra_entrypoints
from prefect.settings import PREFECT_EXTRA_ENTRYPOINTS, temporary_settings
from prefect.testing.utilities import exceptions_equal


@pytest.fixture
def module_fixture(tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.syspath_prepend(tmp_path)
    (tmp_path / "test_module_name.py").write_text(
        textwrap.dedent(
            """
            import os
            from unittest.mock import MagicMock

            def returns_test():
                return "test"

            def returns_foo():
                return "foo"

            def returns_bar():
                return "bar"

            def raises_value_error():
                raise ValueError("test")

            def raises_base_exception():
                raise BaseException("test")

            def mock_function(*args, **kwargs):
                mock = MagicMock()
                mock(*args, **kwargs)
                return mock
            """
        )
    )

    yield

    importlib.invalidate_caches()


@pytest.fixture
def raising_module_fixture(tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.syspath_prepend(tmp_path)
    (tmp_path / "raising_module_name.py").write_text(
        textwrap.dedent(
            """
            raise RuntimeError("test")
            """
        )
    )

    yield

    importlib.invalidate_caches()


@pytest.mark.usefixtures("module_fixture")
def test_load_extra_entrypoints_imports_module():
    with temporary_settings({PREFECT_EXTRA_ENTRYPOINTS: "test_module_name"}):
        result = load_extra_entrypoints()

    assert set(result.keys()) == {"test_module_name"}
    assert result["test_module_name"] == importlib.import_module("test_module_name")


@pytest.mark.usefixtures("module_fixture")
def test_load_extra_entrypoints_strips_spaces():
    with temporary_settings({PREFECT_EXTRA_ENTRYPOINTS: "   test_module_name "}):
        result = load_extra_entrypoints()

    assert set(result.keys()) == {"test_module_name"}
    assert result["test_module_name"] == importlib.import_module("test_module_name")


@pytest.mark.usefixtures("module_fixture")
def test_load_extra_entrypoints_unparsable_entrypoint(capsys):
    with temporary_settings({PREFECT_EXTRA_ENTRYPOINTS: "foo$bar"}):
        result = load_extra_entrypoints()

    assert set(result.keys()) == {"foo$bar"}
    assert exceptions_equal(
        result["foo$bar"], AttributeError("'NoneType' object has no attribute 'group'")
    )

    _, stderr = capsys.readouterr()
    assert (
        "Warning! Failed to load extra entrypoint 'foo$bar': "
        "AttributeError: 'NoneType' object has no attribute 'group'" in stderr
    )


@pytest.mark.usefixtures("module_fixture")
def test_load_extra_entrypoints_callable():
    with temporary_settings(
        {PREFECT_EXTRA_ENTRYPOINTS: "test_module_name:returns_test"}
    ):
        result = load_extra_entrypoints()

    assert set(result.keys()) == {"test_module_name:returns_test"}
    assert result["test_module_name:returns_test"] == "test"


@pytest.mark.usefixtures("module_fixture")
def test_load_extra_entrypoints_multiple_entrypoints():
    with temporary_settings(
        {
            PREFECT_EXTRA_ENTRYPOINTS: (
                "test_module_name:returns_foo,test_module_name:returns_bar"
            )
        }
    ):
        result = load_extra_entrypoints()

    assert result == {
        "test_module_name:returns_foo": "foo",
        "test_module_name:returns_bar": "bar",
    }


@pytest.mark.usefixtures("module_fixture")
def test_load_extra_entrypoints_callable_given_no_arguments():
    with temporary_settings(
        {PREFECT_EXTRA_ENTRYPOINTS: "test_module_name:mock_function"}
    ):
        result = load_extra_entrypoints()

    assert set(result.keys()) == {"test_module_name:mock_function"}
    result["test_module_name:mock_function"].assert_called_once_with()


@pytest.mark.usefixtures("module_fixture")
def test_load_extra_entrypoints_callable_that_raises(capsys):
    with temporary_settings(
        {PREFECT_EXTRA_ENTRYPOINTS: "test_module_name:raises_value_error"}
    ):
        result = load_extra_entrypoints()

    assert set(result.keys()) == {"test_module_name:raises_value_error"}
    assert exceptions_equal(
        result["test_module_name:raises_value_error"], ValueError("test")
    )

    _, stderr = capsys.readouterr()
    assert (
        "Warning! Failed to run callable entrypoint "
        "'test_module_name:raises_value_error': ValueError: test" in stderr
    )


@pytest.mark.usefixtures("module_fixture")
def test_load_extra_entrypoints_callable_that_raises_base_exception():
    with temporary_settings(
        {PREFECT_EXTRA_ENTRYPOINTS: "test_module_name:raises_base_exception"}
    ):
        with pytest.raises(BaseException, match="test"):
            load_extra_entrypoints()


@pytest.mark.usefixtures("raising_module_fixture")
def test_load_extra_entrypoints_error_on_import(capsys):
    with temporary_settings({PREFECT_EXTRA_ENTRYPOINTS: "raising_module_name"}):
        result = load_extra_entrypoints()

    assert set(result.keys()) == {"raising_module_name"}
    assert exceptions_equal(result["raising_module_name"], RuntimeError("test"))

    _, stderr = capsys.readouterr()
    assert (
        "Warning! Failed to load extra entrypoint 'raising_module_name': "
        "RuntimeError: test" in stderr
    )


@pytest.mark.usefixtures("module_fixture")
def test_load_extra_entrypoints_missing_module(capsys):
    with temporary_settings({PREFECT_EXTRA_ENTRYPOINTS: "nonexistant_module"}):
        result = load_extra_entrypoints()

    assert set(result.keys()) == {"nonexistant_module"}
    assert exceptions_equal(
        result["nonexistant_module"],
        ModuleNotFoundError("No module named 'nonexistant_module'"),
    )

    _, stderr = capsys.readouterr()
    assert (
        "Warning! Failed to load extra entrypoint 'nonexistant_module': "
        "ModuleNotFoundError" in stderr
    )


@pytest.mark.usefixtures("module_fixture")
def test_load_extra_entrypoints_missing_submodule(capsys):
    with temporary_settings(
        {PREFECT_EXTRA_ENTRYPOINTS: "test_module_name.missing_module"}
    ):
        result = load_extra_entrypoints()

    assert set(result.keys()) == {"test_module_name.missing_module"}
    assert exceptions_equal(
        result["test_module_name.missing_module"],
        ModuleNotFoundError(
            "No module named 'test_module_name.missing_module'; "
            "'test_module_name' is not a package"
        ),
    )

    _, stderr = capsys.readouterr()
    assert (
        "Warning! Failed to load extra entrypoint 'test_module_name.missing_module': "
        "ModuleNotFoundError" in stderr
    )


@pytest.mark.usefixtures("module_fixture")
def test_load_extra_entrypoints_missing_attribute(capsys):
    with temporary_settings(
        {PREFECT_EXTRA_ENTRYPOINTS: "test_module_name:missing_attr"}
    ):
        result = load_extra_entrypoints()

    assert set(result.keys()) == {"test_module_name:missing_attr"}
    assert exceptions_equal(
        result["test_module_name:missing_attr"],
        AttributeError("module 'test_module_name' has no attribute 'missing_attr'"),
    )

    _, stderr = capsys.readouterr()
    assert (
        "Warning! Failed to load extra entrypoint 'test_module_name:missing_attr': "
        "AttributeError" in stderr
    )


def test_plugin_load_on_prefect_package_init(monkeypatch):
    mock_load_prefect_collections = Mock()
    mock_load_extra_entrypoints = Mock()

    monkeypatch.setattr(
        prefect.plugins, "load_prefect_collections", mock_load_prefect_collections
    )
    monkeypatch.setattr(
        prefect.plugins, "load_extra_entrypoints", mock_load_extra_entrypoints
    )

    importlib.reload(prefect)

    mock_load_prefect_collections.assert_not_called()  # We no longer load collections on import due to high performance cost
    mock_load_extra_entrypoints.assert_called_once()
