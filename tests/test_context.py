import os
import textwrap
from contextvars import ContextVar
from copy import deepcopy
from unittest.mock import MagicMock

import pytest
from pendulum.datetime import DateTime

import prefect.settings
from prefect import flow, task
from prefect.context import (
    ContextModel,
    FlowRunContext,
    ProfileContext,
    TaskRunContext,
    enter_global_profile,
    get_profile_context,
    get_run_context,
    profile,
    temporary_environ,
)
from prefect.exceptions import MissingContextError
from prefect.task_runners import SequentialTaskRunner
from prefect.testing.utilities import temporary_settings


class ExampleContext(ContextModel):
    __var__ = ContextVar("test")

    x: int


def test_context_enforces_types():
    with pytest.raises(ValueError):
        ExampleContext(x="hello")


def test_context_get_outside_context_is_null():
    assert ExampleContext.get() is None


def test_single_context_object_cannot_be_entered_multiple_times():
    context = ExampleContext(x=1)
    with context:
        with pytest.raises(RuntimeError, match="Context already entered"):
            with context:
                pass


def test_copied_context_object_can_be_reentered():
    context = ExampleContext(x=1)
    with context:
        with context.copy():
            assert ExampleContext.get().x == 1


def test_exiting_a_context_more_than_entering_raises():
    context = ExampleContext(x=1)

    with pytest.raises(RuntimeError, match="Asymmetric use of context"):
        with context:
            context.__exit__()


def test_context_exit_restores_previous_context():
    with ExampleContext(x=1):
        with ExampleContext(x=2):
            with ExampleContext(x=3):
                assert ExampleContext.get().x == 3
            assert ExampleContext.get().x == 2
        assert ExampleContext.get().x == 1
    assert ExampleContext.get() is None


def test_temporary_environ_does_not_overwrite_falsy_values():
    """
    Covers case where temporary_environ was overwriting environment variables where an
    empty string was the value, due to `if dict.get(key):` logic
    """
    VAR = "PREFECT_API_URL"
    original_value = os.getenv(VAR)
    not_nones = [0, "False", ""]

    for not_none in not_nones:
        os.environ[VAR] = str(not_none)
        start = deepcopy(os.environ)

        with temporary_environ({VAR: "Other Value"}):
            pass

        assert start.get(VAR) == os.environ.get(VAR)

    if original_value is not None:
        os.environ[VAR] = original_value
    else:
        del os.environ[VAR]


async def test_flow_run_context(orion_client, local_storage_block):
    @flow
    def foo():
        pass

    test_task_runner = SequentialTaskRunner()
    flow_run = await orion_client.create_flow_run(foo)

    with FlowRunContext(
        flow=foo,
        flow_run=flow_run,
        client=orion_client,
        task_runner=test_task_runner,
        result_storage=local_storage_block,
    ):
        ctx = FlowRunContext.get()
        assert ctx.flow is foo
        assert ctx.flow_run == flow_run
        assert ctx.client is orion_client
        assert ctx.task_runner is test_task_runner
        assert ctx.result_storage == local_storage_block
        assert isinstance(ctx.start_time, DateTime)


async def test_task_run_context(orion_client, flow_run, local_storage_block):
    @task
    def foo():
        pass

    task_run = await orion_client.create_task_run(foo, flow_run.id, dynamic_key="")

    with TaskRunContext(
        task=foo,
        task_run=task_run,
        client=orion_client,
        result_storage=local_storage_block,
    ):
        ctx = TaskRunContext.get()
        assert ctx.task is foo
        assert ctx.task_run == task_run
        assert ctx.result_storage == local_storage_block
        assert isinstance(ctx.start_time, DateTime)


async def test_get_run_context(orion_client, local_storage_block):
    @flow
    def foo():
        pass

    @task
    def bar():
        pass

    test_task_runner = SequentialTaskRunner()
    flow_run = await orion_client.create_flow_run(foo)
    task_run = await orion_client.create_task_run(bar, flow_run.id, dynamic_key="")

    with pytest.raises(RuntimeError):
        get_run_context()

    with pytest.raises(MissingContextError):
        get_run_context()

    with FlowRunContext(
        flow=foo,
        flow_run=flow_run,
        client=orion_client,
        task_runner=test_task_runner,
        result_storage=local_storage_block,
    ) as flow_ctx:
        assert get_run_context() is flow_ctx

        with TaskRunContext(
            task=bar,
            task_run=task_run,
            client=orion_client,
            result_storage=local_storage_block,
        ) as task_ctx:
            assert get_run_context() is task_ctx, "Task context takes precendence"

        assert get_run_context() is flow_ctx, "Flow context is restored and retrieved"


class TestProfilesContext:
    @pytest.fixture(autouse=True)
    def temporary_profiles_path(self, tmp_path):
        path = tmp_path / "profiles.toml"
        with temporary_settings(PREFECT_HOME=tmp_path, PREFECT_PROFILES_PATH=path):
            yield path

    def test_profile_context_variable(self):
        with ProfileContext(
            name="test",
            settings=prefect.settings.get_settings_from_env(),
            env={"FOO": "BAR"},
        ) as context:
            assert get_profile_context() is context
            assert context.name == "test"
            assert context.settings == prefect.settings.get_settings_from_env()
            assert context.env == {"FOO": "BAR"}

    def test_get_profile_context_missing(self, monkeypatch):
        # It's kind of hard to actually exit the default profile, so we patch `get`
        monkeypatch.setattr(
            "prefect.context.ProfileContext.get", MagicMock(return_value=None)
        )
        with pytest.raises(MissingContextError, match="No profile"):
            get_profile_context()

    def test_creates_home_if_asked(self, tmp_path, temporary_profiles_path):
        home = tmp_path / "home"
        assert not home.exists()
        with temporary_settings(PREFECT_HOME=home):
            with profile("default", initialize=False) as ctx:
                ctx.initialize(create_home=True)

        assert home.exists()

    def test_profile_context_uses_settings(self, temporary_profiles_path):
        temporary_profiles_path.write_text(
            textwrap.dedent(
                """
                [profiles.foo]
                PREFECT_API_URL="test"
                """
            )
        )
        with profile("foo") as ctx:
            assert prefect.settings.PREFECT_API_URL.value() == "test"
            assert ctx.settings == prefect.settings.get_current_settings()
            assert ctx.env == {"PREFECT_API_URL": "test"}
            assert ctx.name == "foo"

    def test_profile_context_sets_up_logging_if_asked(
        self, monkeypatch, temporary_profiles_path
    ):
        setup_logging = MagicMock()
        monkeypatch.setattr(
            "prefect.logging.configuration.setup_logging", setup_logging
        )
        temporary_profiles_path.write_text(
            textwrap.dedent(
                """
                [profiles.foo]
                PREFECT_API_URL = "test"
                """
            )
        )
        with profile("foo", initialize=False) as ctx:
            ctx.initialize(setup_logging=True)
            setup_logging.assert_called_once_with(ctx.settings)

    def test_profile_context_does_not_setup_logging_if_asked(self, monkeypatch):
        setup_logging = MagicMock()
        monkeypatch.setattr(
            "prefect.logging.configuration.setup_logging", setup_logging
        )

        with profile("default", initialize=False) as ctx:
            ctx.initialize(setup_logging=False)
            setup_logging.assert_not_called()

    def test_profile_context_nesting(self, temporary_profiles_path):
        temporary_profiles_path.write_text(
            textwrap.dedent(
                """
                [profiles.foo]
                PREFECT_API_URL="foo"

                [profiles.bar]
                PREFECT_API_URL="bar"
                """
            )
        )
        with profile("foo") as foo_context:
            with profile("bar") as bar_context:
                assert bar_context.settings == prefect.settings.get_current_settings()
                assert (
                    prefect.settings.PREFECT_API_URL.value_from(bar_context.settings)
                    == "bar"
                )
                assert bar_context.env == {"PREFECT_API_URL": "bar"}
                assert bar_context.name == "bar"
            assert foo_context.settings == prefect.settings.get_current_settings()
            assert (
                prefect.settings.PREFECT_API_URL.value_from(foo_context.settings)
                == "foo"
            )
            assert foo_context.env == {"PREFECT_API_URL": "foo"}
            assert foo_context.name == "foo"

    def test_enter_global_profile(self, monkeypatch):
        profile = MagicMock()
        monkeypatch.setattr("prefect.context.profile", profile)
        monkeypatch.setattr("prefect.context.GLOBAL_PROFILE_CM", None)
        enter_global_profile()
        profile.assert_called_once_with(name="default", initialize=False)
        profile().__enter__.assert_called_once_with()
        assert prefect.context.GLOBAL_PROFILE_CM is not None

    def test_enter_global_profile_is_idempotent(self, monkeypatch):
        profile = MagicMock()
        monkeypatch.setattr("prefect.context.profile", profile)
        monkeypatch.setattr("prefect.context.GLOBAL_PROFILE_CM", None)
        enter_global_profile()
        enter_global_profile()
        enter_global_profile()
        profile.assert_called_once()
        profile().__enter__.assert_called_once()

    def test_enter_global_profile_respects_name_env_variable(
        self, monkeypatch, temporary_profiles_path
    ):
        profile = MagicMock()
        temporary_profiles_path.write_text(
            textwrap.dedent(
                """
                [profiles.test]
                PREFECT_API_KEY = "xxx"
                """
            )
        )
        monkeypatch.setattr("prefect.context.profile", profile)
        monkeypatch.setattr("prefect.context.GLOBAL_PROFILE_CM", None)
        monkeypatch.setenv("PREFECT_PROFILE", "test")
        enter_global_profile()
        profile.assert_called_once_with(name="test", initialize=False)
