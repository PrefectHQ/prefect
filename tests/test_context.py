import textwrap
from contextvars import ContextVar
from unittest.mock import ANY, MagicMock

import pytest
from pendulum.datetime import DateTime

import prefect.settings
from prefect import flow, task
from prefect.cli.config import profile_app
from prefect.context import (
    DEFAULT_PROFILES,
    ContextModel,
    FlowRunContext,
    ProfileContext,
    TaskRunContext,
    get_profile_context,
    get_run_context,
    initialize_module_profile,
    load_profile,
    load_profiles,
    profile,
    write_profiles,
)
from prefect.exceptions import MissingContextError
from prefect.task_runners import SequentialTaskRunner
from prefect.utilities.testing import temporary_settings


class ExampleContext(ContextModel):
    __var__ = ContextVar("test")

    x: int


def test_context_enforces_types():
    with pytest.raises(ValueError):
        ExampleContext(x="hello")


def test_context_get_outside_context_is_null():
    assert ExampleContext.get() is None


def test_context_exit_restores_previous_context():
    with ExampleContext(x=1):
        with ExampleContext(x=2):
            with ExampleContext(x=3):
                assert ExampleContext.get().x == 3
            assert ExampleContext.get().x == 2
        assert ExampleContext.get().x == 1
    assert ExampleContext.get() is None


async def test_flow_run_context(orion_client):
    @flow
    def foo():
        pass

    test_task_runner = SequentialTaskRunner()
    flow_run = await orion_client.create_flow_run(foo)

    with FlowRunContext(
        flow=foo, flow_run=flow_run, client=orion_client, task_runner=test_task_runner
    ):
        ctx = FlowRunContext.get()
        assert ctx.flow is foo
        assert ctx.flow_run == flow_run
        assert ctx.client is orion_client
        assert ctx.task_runner is test_task_runner
        assert isinstance(ctx.start_time, DateTime)


async def test_task_run_context(orion_client, flow_run):
    @task
    def foo():
        pass

    task_run = await orion_client.create_task_run(foo, flow_run.id, dynamic_key="")

    with TaskRunContext(task=foo, task_run=task_run, client=orion_client):
        ctx = TaskRunContext.get()
        assert ctx.task is foo
        assert ctx.task_run == task_run
        assert isinstance(ctx.start_time, DateTime)


async def test_get_run_context(orion_client):
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
        flow=foo, flow_run=flow_run, client=orion_client, task_runner=test_task_runner
    ) as flow_ctx:
        assert get_run_context() is flow_ctx

        with TaskRunContext(
            task=bar, task_run=task_run, client=orion_client
        ) as task_ctx:
            assert get_run_context() is task_ctx, "Task context takes precendence"

        assert get_run_context() is flow_ctx, "Flow context is restored and retrieved"


class TestProfiles:
    @pytest.fixture(autouse=True)
    def temporary_profiles_path(self, tmp_path):
        path = tmp_path / "profiles.toml"
        with temporary_settings(PREFECT_PROFILES_PATH=path):
            yield path

    def test_load_profiles_no_profiles_file(self):
        assert load_profiles() == DEFAULT_PROFILES

    def test_load_profiles_missing_default(self, temporary_profiles_path):
        temporary_profiles_path.write_text(
            textwrap.dedent(
                """
                [foo]
                test = "bar"
                """
            )
        )
        assert load_profiles() == {**DEFAULT_PROFILES, "foo": {"test": "bar"}}

    def test_load_profiles_with_default(self, temporary_profiles_path):
        temporary_profiles_path.write_text(
            textwrap.dedent(
                """
                [default]
                test = "foo"

                [foo]
                test = "bar"
                """
            )
        )
        assert load_profiles() == {"default": {"test": "foo"}, "foo": {"test": "bar"}}

    def test_write_profiles_includes_default(self, temporary_profiles_path):
        write_profiles({})
        assert (
            temporary_profiles_path.read_text()
            == textwrap.dedent(
                """
                [default]
                """
            ).lstrip()
        )

    def test_write_profiles_allows_default_override(self, temporary_profiles_path):
        write_profiles({"default": {"test": "foo"}})
        assert (
            temporary_profiles_path.read_text()
            == textwrap.dedent(
                """
                [default]
                test = "foo"
                """
            ).lstrip()
        )

    def test_write_profiles_additional_profiles(self, temporary_profiles_path):
        write_profiles({"foo": {"test": "bar"}, "foobar": {"test": 1}})
        assert (
            temporary_profiles_path.read_text()
            == textwrap.dedent(
                """
                [default]

                [foo]
                test = "bar"

                [foobar]
                test = 1
                """
            ).lstrip()
        )

    def test_load_profile_default(self):
        assert load_profile("default") == {}

    def test_load_profile_missing(self):
        with pytest.raises(ValueError, match="Profile 'foo' not found."):
            load_profile("foo")

    def test_load_profile(self, temporary_profiles_path):
        temporary_profiles_path.write_text(
            textwrap.dedent(
                """
                [foo]
                test = "bar"
                number = 1
                """
            )
        )
        assert load_profile("foo") == {"test": "bar", "number": "1"}

    def test_load_profile_casts_nested_data_to_strings(self, temporary_profiles_path):
        # Not a suggested pattern, but not banned yet
        temporary_profiles_path.write_text(
            textwrap.dedent(
                """
                [foo]
                test = "bar"
                [foo.nested]
                test = "okay"
                """
            )
        )
        assert load_profile("foo") == {"test": "bar", "nested": "{'test': 'okay'}"}

    def test_profile_context_variable(self):
        with ProfileContext(
            name="test", settings=prefect.settings.from_env(), env={"FOO": "BAR"}
        ) as context:
            assert get_profile_context() is context
            assert context.name == "test"
            assert context.settings == prefect.settings.from_env()
            assert context.env == {"FOO": "BAR"}

    def test_get_profile_context_missing(self, monkeypatch):
        # It's kind of hard to actually exit the default profile, so we patch `get`
        monkeypatch.setattr(
            "prefect.context.ProfileContext.get", MagicMock(return_value=None)
        )
        with pytest.raises(MissingContextError, match="No profile"):
            get_profile_context()

    def test_profile_context_creates_home_if_asked(
        self, tmp_path, temporary_profiles_path
    ):
        home = tmp_path / "home"
        assert not home.exists()
        temporary_profiles_path.write_text(
            textwrap.dedent(
                f"""
                [foo]
                PREFECT_HOME = "{home}"
                """
            )
        )
        with profile("foo", create_home=True):
            pass

        assert home.exists()

    def test_profile_context_uses_settings(self, temporary_profiles_path):
        temporary_profiles_path.write_text(
            textwrap.dedent(
                """
                [foo]
                PREFECT_ORION_HOST="test"
                """
            )
        )
        with profile("foo") as ctx:
            assert prefect.settings.from_context().orion_host == "test"
            assert ctx.settings == prefect.settings.from_context()
            assert ctx.env == {"PREFECT_ORION_HOST": "test"}
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
                [foo]
                PREFECT_ORION_HOST = "test"
                """
            )
        )
        with profile("foo", setup_logging=True) as ctx:
            setup_logging.assert_called_once_with(ctx.settings)

    def test_profile_context_does_not_setup_logging_by_default(self, monkeypatch):
        setup_logging = MagicMock()
        monkeypatch.setattr(
            "prefect.logging.configuration.setup_logging", setup_logging
        )

        with profile("default"):
            setup_logging.assert_not_called()

    def test_profile_context_nesting(self, temporary_profiles_path):
        temporary_profiles_path.write_text(
            textwrap.dedent(
                """
                [foo]
                PREFECT_ORION_HOST="foo"

                [bar]
                PREFECT_ORION_HOST="bar"
                """
            )
        )
        with profile("foo") as foo_context:
            with profile("bar") as bar_context:
                assert bar_context.settings == prefect.settings.from_context()
                assert bar_context.settings.orion_host == "bar"
                assert bar_context.env == {"PREFECT_ORION_HOST": "bar"}
                assert bar_context.name == "bar"
            assert foo_context.settings == prefect.settings.from_context()
            assert foo_context.settings.orion_host == "foo"
            assert foo_context.env == {"PREFECT_ORION_HOST": "foo"}
            assert foo_context.name == "foo"

    def test_initialize_module_profile(self, monkeypatch):
        profile = MagicMock()
        monkeypatch.setattr("prefect.context.profile", profile)
        initialize_module_profile()
        profile.assert_called_once_with(
            name="default", create_home=True, setup_logging=True
        )
        profile().__enter__.assert_called_once_with()

    def test_initialize_module_profile_respects_name_env_variable(self, monkeypatch):
        profile = MagicMock()
        monkeypatch.setattr("prefect.context.profile", profile)
        monkeypatch.setenv("PREFECT_PROFILE", "test")
        initialize_module_profile()
        profile.assert_called_once_with(
            name="test", create_home=True, setup_logging=True
        )
