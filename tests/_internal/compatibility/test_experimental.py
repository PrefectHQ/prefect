import re
import typing

import pytest

from prefect._internal.compatibility.experimental import (
    ExperimentalFeature,
    ExperimentalFeatureDisabled,
    enabled_experiments,
    experiment_enabled,
    experimental,
    experimental_parameter,
)
from prefect.settings import (
    PREFECT_EXPERIMENTAL_WARN,
    SETTING_VARIABLES,
    Setting,
    temporary_settings,
)


@pytest.fixture(autouse=True)
def prefect_experimental_test_setting(
    monkeypatch: pytest.MonkeyPatch,
) -> typing.Generator[Setting[bool], None, None]:
    """
    Injects a new setting for the TEST feature group.
    """
    PREFECT_EXPERIMENTAL_WARN_TEST = Setting(bool, default=False)
    PREFECT_EXPERIMENTAL_WARN_TEST.name = "PREFECT_EXPERIMENTAL_WARN_TEST"
    monkeypatch.setitem(
        SETTING_VARIABLES,
        "PREFECT_EXPERIMENTAL_WARN_TEST",
        PREFECT_EXPERIMENTAL_WARN_TEST,
    )
    monkeypatch.setattr(
        "prefect.settings.Settings.PREFECT_EXPERIMENTAL_WARN_TEST", True, raising=False
    )

    yield PREFECT_EXPERIMENTAL_WARN_TEST


@pytest.fixture
def disable_prefect_experimental_test_setting(
    monkeypatch: pytest.MonkeyPatch,
    prefect_experimental_test_setting: typing.Callable[
        [pytest.MonkeyPatch], typing.Generator[Setting[bool], None, None]
    ],
):
    monkeypatch.setattr(
        "prefect.settings.Settings.PREFECT_EXPERIMENTAL_WARN_TEST", False, raising=False
    )


@pytest.fixture(autouse=True)
def prefect_experimental_test_opt_in_setting(monkeypatch: pytest.MonkeyPatch):
    """
    Injects a new opt-in setting for the TEST feature group.
    """
    PREFECT_EXPERIMENTAL_ENABLE_TEST = Setting(bool, default=False)
    PREFECT_EXPERIMENTAL_ENABLE_TEST.name = "PREFECT_EXPERIMENTAL_ENABLE_TEST"
    monkeypatch.setitem(
        SETTING_VARIABLES,
        "PREFECT_EXPERIMENTAL_ENABLE_TEST",
        PREFECT_EXPERIMENTAL_ENABLE_TEST,
    )
    monkeypatch.setattr(
        "prefect.settings.Settings.PREFECT_EXPERIMENTAL_ENABLE_TEST",
        False,
        raising=False,
    )

    yield PREFECT_EXPERIMENTAL_ENABLE_TEST


@pytest.fixture
def enable_prefect_experimental_test_opt_in_setting(
    monkeypatch: pytest.MonkeyPatch,
    prefect_experimental_test_opt_in_setting: typing.Callable[
        [pytest.MonkeyPatch], typing.Generator[Setting[bool], None, None]
    ],
):
    monkeypatch.setattr(
        "prefect.settings.Settings.PREFECT_EXPERIMENTAL_ENABLE_TEST",
        True,
        raising=False,
    )


def test_experimental_marker_on_function():
    @experimental(
        "A test function", group="test", help="This is just a test, don't worry."
    )
    def foo():
        return 1

    with pytest.warns(
        ExperimentalFeature,
        match=(
            "A test function is experimental. This is just a test, don't worry. "
            "The interface or behavior may change without warning, we recommend "
            "pinning versions to prevent unexpected changes. "
            "To disable warnings for this group of experiments, "
            "disable PREFECT_EXPERIMENTAL_WARN_TEST."
        ),
    ):
        assert foo() == 1


def test_experimental_marker_on_class():
    @experimental(
        "A test class", group="test", help="This is just a test, don't worry."
    )
    class Foo:
        pass

    with pytest.warns(
        ExperimentalFeature,
        match=(
            "A test class is experimental. This is just a test, don't worry. "
            "The interface or behavior may change without warning, we recommend "
            "pinning versions to prevent unexpected changes. "
            "To disable warnings for this group of experiments, "
            "disable PREFECT_EXPERIMENTAL_WARN_TEST."
        ),
    ):
        assert Foo()


def test_experimental_parameter_warning():
    @experimental_parameter(
        "return_value",
        group="test",
        help="This is just a test, don't worry.",
    )
    def foo(return_value: int = 1):
        return return_value

    with pytest.warns(
        ExperimentalFeature,
        match=(
            "The parameter 'return_value' is experimental. This is just a test, "
            "don't worry. The interface or behavior may change without warning, "
            "we recommend pinning versions to prevent unexpected changes. "
            "To disable warnings for this group of experiments, disable "
            "PREFECT_EXPERIMENTAL_WARN_TEST."
        ),
    ):
        assert foo(return_value=2) == 2


def test_experimental_parameter_no_warning_when_not_passed():
    @experimental_parameter(
        "return_value",
        group="test",
        help="This is just a test, don't worry.",
    )
    def foo(return_value: int = 1):
        return return_value

    assert foo() == 1


def test_experimental_parameter_positional():
    @experimental_parameter(
        "return_value",
        group="test",
        help="This is just a test, don't worry.",
    )
    def foo(return_value: int = 1):
        return return_value

    with pytest.warns(ExperimentalFeature):
        assert foo(1) == 1


def test_experimental_parameter_when():
    @experimental_parameter(
        "return_value",
        group="test",
        help="This is just a test, don't worry.",
        when=lambda x: x == 3,
    )
    def foo(return_value: int = 1):
        return return_value

    assert foo() == 1
    assert foo(return_value=2) == 2

    with pytest.warns(ExperimentalFeature):
        assert foo(return_value=3) == 3


def test_experimental_parameter_opt_in():
    @experimental_parameter(
        "return_value",
        group="test",
        help="This is just a test, don't worry.",
        opt_in=True,
    )
    def foo(return_value: int = 1):
        return return_value

    with pytest.raises(ExperimentalFeatureDisabled):
        assert foo(return_value=1) == 1


def test_experimental_parameter_retains_error_with_invalid_arguments():
    @experimental_parameter(
        "return_value",
        group="test",
        help="This is just a test, don't worry.",
    )
    def foo(return_value: int = 1):
        return return_value

    with pytest.raises(
        TypeError, match=re.escape("foo() got an unexpected keyword argument 'z'")
    ):
        foo(z=3)  # type: ignore


def test_experimental_warning_without_help():
    @experimental("A test function", group="test")
    def foo():
        return 1

    with pytest.warns(
        ExperimentalFeature,
        match=(
            "A test function is experimental. "
            "The interface or behavior may change without warning, we recommend "
            "pinning versions to prevent unexpected changes. "
            "To disable warnings for this group of experiments, "
            "disable PREFECT_EXPERIMENTAL_WARN_TEST."
        ),
    ):
        assert foo() == 1


@pytest.mark.usefixtures("disable_prefect_experimental_test_setting")
def test_experimental_marker_does_not_warn_with_group_setting():
    @experimental(
        "A test function", group="test", help="This is just a test, don't worry."
    )
    def foo():
        return 1

    assert foo() == 1


def test_experimental_marker_does_not_warn_with_global_setting():
    @experimental(
        "A test function", group="test", help="This is just a test, don't worry."
    )
    def foo():
        return 1

    with temporary_settings({PREFECT_EXPERIMENTAL_WARN: False}):
        assert foo() == 1


def test_experimental_marker_raises_without_opt_in():
    @experimental(
        "A test function",
        group="test",
        help="This is just a test, don't worry.",
        opt_in=True,
    )
    def foo():
        return 1

    with pytest.raises(
        ExperimentalFeatureDisabled,
        match=(
            "A test function is experimental and requires opt-in for usage. "
            "This is just a test, don't worry. "
            "To use this feature, enable PREFECT_EXPERIMENTAL_ENABLE_TEST."
        ),
    ):
        assert foo() == 1


@pytest.mark.usefixtures("enable_prefect_experimental_test_opt_in_setting")
def test_experimental_marker_does_not_raise_with_opt_in():
    @experimental(
        "A test function",
        group="test",
        help="This is just a test, don't worry.",
        opt_in=True,
    )
    def foo():
        return 1

    # A warning is still expected unless that has been opted out of
    with pytest.warns(ExperimentalFeature):
        assert foo() == 1


@pytest.mark.usefixtures("enable_prefect_experimental_test_opt_in_setting")
def test_experiment_enabled_with_opt_in():
    assert experiment_enabled("test") is True


def test_experiment_enabled_without_opt_in():
    assert experiment_enabled("test") is False


def test_experiment_enabled_with_unknown_group():
    with pytest.raises(
        ValueError,
        match=(
            "A opt-in setting for experimental feature 'foo' does not exist yet. "
            "'PREFECT_EXPERIMENTAL_ENABLE_FOO' must be created before the group can "
            "be used."
        ),
    ):
        assert experiment_enabled("foo") is False


def test_experimental_marker_cannot_be_used_without_warn_setting():
    with pytest.raises(
        ValueError,
        match=(
            "A warn setting for experimental feature 'ANOTHER_GROUP' does not exist "
            "yet. 'PREFECT_EXPERIMENTAL_WARN_ANOTHER_GROUP' must be created before "
            "the group can be used."
        ),
    ):

        @experimental(
            feature="A test feature",
            group="ANOTHER_GROUP",
        )
        def foo():  # type: ignore
            return 1


def test_experimental_marker_cannot_be_used_without_opt_in_setting_if_required():
    with pytest.raises(
        ValueError,
        match=(
            "A opt-in setting for experimental feature 'ANOTHER_GROUP' does not exist "
            "yet. 'PREFECT_EXPERIMENTAL_ENABLE_ANOTHER_GROUP' must be created before "
            "the group can be used."
        ),
    ):

        @experimental(feature="A test feature", group="ANOTHER_GROUP", opt_in=True)
        def foo():  # type: ignore
            return 1


@pytest.mark.usefixtures("enable_prefect_experimental_test_opt_in_setting")
def test_enabled_experiments_with_opt_in():
    assert enabled_experiments() == {
        "test",
        "workers",
        "enhanced_cancellation",
        "artifacts_on_flow_run_graph",
        "states_on_flow_run_graph",
    }


def test_enabled_experiments_without_opt_in():
    assert enabled_experiments() == {
        "workers",
        "enhanced_cancellation",
        "artifacts_on_flow_run_graph",
        "states_on_flow_run_graph",
    }
