import textwrap
from contextvars import ContextVar
from unittest.mock import MagicMock

import anyio
import pytest
from pendulum.datetime import DateTime

import prefect.settings
from prefect import flow, task
from prefect.context import (
    GLOBAL_SETTINGS_CONTEXT,
    ContextModel,
    FlowRunContext,
    SettingsContext,
    TaskRunContext,
    get_run_context,
    get_settings_context,
    root_settings_context,
    use_profile,
)
from prefect.exceptions import MissingContextError
from prefect.results import ResultFactory
from prefect.settings import (
    DEFAULT_PROFILES_PATH,
    PREFECT_API_KEY,
    PREFECT_API_URL,
    PREFECT_HOME,
    PREFECT_PROFILES_PATH,
    Profile,
    ProfilesCollection,
    save_profiles,
    temporary_settings,
)
from prefect.task_runners import SequentialTaskRunner


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


async def test_flow_run_context(orion_client):
    @flow
    def foo():
        pass

    test_task_runner = SequentialTaskRunner()
    flow_run = await orion_client.create_flow_run(foo)
    result_factory = await ResultFactory.from_flow(foo)

    async with anyio.create_task_group() as task_group:
        with FlowRunContext(
            flow=foo,
            flow_run=flow_run,
            client=orion_client,
            task_runner=test_task_runner,
            result_factory=result_factory,
            background_tasks=task_group,
        ):
            ctx = FlowRunContext.get()
            assert ctx.flow is foo
            assert ctx.flow_run == flow_run
            assert ctx.client is orion_client
            assert ctx.task_runner is test_task_runner
            assert ctx.result_factory == result_factory
            assert isinstance(ctx.start_time, DateTime)


async def test_task_run_context(orion_client, flow_run):
    @task
    def foo():
        pass

    task_run = await orion_client.create_task_run(foo, flow_run.id, dynamic_key="")
    result_factory = await ResultFactory.default_factory()

    with TaskRunContext(
        task=foo,
        task_run=task_run,
        client=orion_client,
        result_factory=result_factory,
    ):
        ctx = TaskRunContext.get()
        assert ctx.task is foo
        assert ctx.task_run == task_run
        assert ctx.result_factory == result_factory
        assert isinstance(ctx.start_time, DateTime)


@pytest.fixture
def remove_existing_settings_context():
    token = SettingsContext.__var__.set(None)
    try:
        yield
    finally:
        SettingsContext.__var__.reset(token)


async def test_get_run_context(orion_client, local_filesystem):
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

    async with anyio.create_task_group() as task_group:
        with FlowRunContext(
            flow=foo,
            flow_run=flow_run,
            client=orion_client,
            task_runner=test_task_runner,
            background_tasks=task_group,
            result_factory=await ResultFactory.from_flow(foo, client=orion_client),
        ) as flow_ctx:
            assert get_run_context() is flow_ctx

            with TaskRunContext(
                task=bar,
                task_run=task_run,
                client=orion_client,
                result_factory=await ResultFactory.from_task(bar, client=orion_client),
            ) as task_ctx:
                assert get_run_context() is task_ctx, "Task context takes precendence"

            assert (
                get_run_context() is flow_ctx
            ), "Flow context is restored and retrieved"


class TestSettingsContext:
    @pytest.fixture(autouse=True)
    def temporary_profiles_path(self, tmp_path):
        path = tmp_path / "profiles.toml"
        with temporary_settings(
            updates={PREFECT_HOME: tmp_path, PREFECT_PROFILES_PATH: path}
        ):
            yield path

    def test_settings_context_variable(self):
        with SettingsContext(
            profile=Profile(name="test", settings={}),
            settings=prefect.settings.get_settings_from_env(),
        ) as context:
            assert get_settings_context() is context
            assert context.profile == Profile(name="test", settings={})
            assert context.settings == prefect.settings.get_settings_from_env()

    def test_get_settings_context_missing(self, monkeypatch):
        # It's kind of hard to actually exit the default profile, so we patch `get`
        monkeypatch.setattr(
            "prefect.context.SettingsContext.get", MagicMock(return_value=None)
        )
        with pytest.raises(MissingContextError, match="No settings context found"):
            get_settings_context()

    def test_creates_home(self, tmp_path):
        home = tmp_path / "home"
        assert not home.exists()
        with temporary_settings(updates={PREFECT_HOME: home}):
            pass

        assert home.exists()

    def test_settings_context_uses_settings(self, temporary_profiles_path):
        temporary_profiles_path.write_text(
            textwrap.dedent(
                """
                [profiles.foo]
                PREFECT_API_URL="test"
                """
            )
        )
        with use_profile("foo") as ctx:
            assert prefect.settings.PREFECT_API_URL.value() == "test"
            assert ctx.settings == prefect.settings.get_current_settings()
            assert ctx.profile == Profile(
                name="foo",
                settings={PREFECT_API_URL: "test"},
                source=temporary_profiles_path,
            )

    def test_settings_context_does_not_setup_logging(self, monkeypatch):
        setup_logging = MagicMock()
        monkeypatch.setattr(
            "prefect.logging.configuration.setup_logging", setup_logging
        )
        with use_profile("default"):
            setup_logging.assert_not_called()

    def test_settings_context_nesting(self, temporary_profiles_path):
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
        with use_profile("foo") as foo_context:
            with use_profile("bar") as bar_context:
                assert bar_context.settings == prefect.settings.get_current_settings()
                assert (
                    prefect.settings.PREFECT_API_URL.value_from(bar_context.settings)
                    == "bar"
                )
                assert bar_context.profile == Profile(
                    name="bar",
                    settings={PREFECT_API_URL: "bar"},
                    source=temporary_profiles_path,
                )
            assert foo_context.settings == prefect.settings.get_current_settings()
            assert (
                prefect.settings.PREFECT_API_URL.value_from(foo_context.settings)
                == "foo"
            )
            assert foo_context.profile == Profile(
                name="foo",
                settings={PREFECT_API_URL: "foo"},
                source=temporary_profiles_path,
            )

    @pytest.fixture
    def foo_profile(self, temporary_profiles_path):
        profile = Profile(
            name="foo",
            settings={PREFECT_API_KEY: "xxx"},
            source=temporary_profiles_path,
        )
        save_profiles(ProfilesCollection(profiles=[profile]))
        return profile

    def test_root_settings_context_default(self, monkeypatch):
        use_profile = MagicMock()
        monkeypatch.setattr("prefect.context.use_profile", use_profile)
        result = root_settings_context()
        use_profile.assert_called_once_with(
            Profile(name="default", settings={}, source=DEFAULT_PROFILES_PATH),
            override_environment_variables=False,
        )
        use_profile().__enter__.assert_called_once_with()
        assert result is not None

    @pytest.mark.parametrize(
        "cli_command",
        [
            # No profile name provided
            ["prefect", "--profile"],
            # Not called via `prefect` CLI
            ["foobar", "--profile", "test"],
        ],
    )
    def test_root_settings_context_default_if_cli_args_do_not_match_format(
        self, monkeypatch, cli_command
    ):
        use_profile = MagicMock()
        monkeypatch.setattr("prefect.context.use_profile", use_profile)
        monkeypatch.setattr("sys.argv", cli_command)
        result = root_settings_context()
        use_profile.assert_called_once_with(
            Profile(name="default", settings={}, source=DEFAULT_PROFILES_PATH),
            override_environment_variables=False,
        )
        use_profile().__enter__.assert_called_once_with()
        assert result is not None

    def test_root_settings_context_respects_cli(self, monkeypatch, foo_profile):
        use_profile = MagicMock()
        monkeypatch.setattr("prefect.context.use_profile", use_profile)
        monkeypatch.setattr("sys.argv", ["/prefect", "--profile", "foo"])
        result = root_settings_context()
        use_profile.assert_called_once_with(
            foo_profile,
            override_environment_variables=True,
        )
        use_profile().__enter__.assert_called_once_with()
        assert result is not None

    def test_root_settings_context_respects_environment_variable(
        self, monkeypatch, foo_profile
    ):
        use_profile = MagicMock()
        monkeypatch.setattr("prefect.context.use_profile", use_profile)
        monkeypatch.setenv("PREFECT_PROFILE", "foo")
        root_settings_context()
        use_profile.assert_called_once_with(
            foo_profile, override_environment_variables=False
        )

    def test_root_settings_context_missing_cli(self, monkeypatch, capsys):
        use_profile = MagicMock()
        monkeypatch.setattr("prefect.context.use_profile", use_profile)
        monkeypatch.setattr("sys.argv", ["/prefect", "--profile", "bar"])
        root_settings_context()
        _, err = capsys.readouterr()
        assert (
            "profile 'bar' set by command line argument not found. The default profile"
            " will be used instead."
            in err
        )

    def test_root_settings_context_missing_environment_variables(
        self, monkeypatch, capsys
    ):
        use_profile = MagicMock()
        monkeypatch.setattr("prefect.context.use_profile", use_profile)
        monkeypatch.setenv("PREFECT_PROFILE", "bar")
        root_settings_context()
        _, err = capsys.readouterr()
        assert (
            "profile 'bar' set by environment variable not found. The default profile"
            " will be used instead."
            in err
        )

    @pytest.mark.usefixtures("remove_existing_settings_context")
    def test_root_settings_context_accessible_in_new_thread(self):
        from concurrent.futures.thread import ThreadPoolExecutor

        with ThreadPoolExecutor() as executor:
            result = executor.submit(get_settings_context).result()

        assert result == GLOBAL_SETTINGS_CONTEXT

    @pytest.mark.usefixtures("remove_existing_settings_context")
    def test_root_settings_context_accessible_in_new_loop(self):
        from anyio import start_blocking_portal

        with start_blocking_portal() as portal:
            result = portal.call(get_settings_context)

        assert result == GLOBAL_SETTINGS_CONTEXT
