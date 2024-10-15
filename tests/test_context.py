import textwrap
from contextvars import ContextVar
from unittest.mock import MagicMock

import pytest
from pendulum.datetime import DateTime

import prefect.settings
from prefect import flow, task
from prefect.client.orchestration import PrefectClient
from prefect.context import (
    GLOBAL_SETTINGS_CONTEXT,
    ContextModel,
    FlowRunContext,
    SettingsContext,
    TagsContext,
    TaskRunContext,
    get_run_context,
    get_settings_context,
    hydrated_context,
    root_settings_context,
    serialize_context,
    tags,
    use_profile,
)
from prefect.exceptions import MissingContextError
from prefect.results import ResultStore, get_result_store
from prefect.settings import (
    PREFECT_API_KEY,
    PREFECT_API_URL,
    PREFECT_HOME,
    PREFECT_PROFILES_PATH,
    Profile,
    ProfilesCollection,
    save_profiles,
    temporary_settings,
)
from prefect.states import Running
from prefect.task_runners import ThreadPoolTaskRunner


class ExampleContext(ContextModel):
    __var__: ContextVar = ContextVar("test")

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
        with context.model_copy():
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


async def test_flow_run_context(prefect_client):
    @flow
    def foo():
        pass

    test_task_runner = ThreadPoolTaskRunner()
    flow_run = await prefect_client.create_flow_run(foo)
    result_store = await ResultStore().update_for_flow(foo)

    with FlowRunContext(
        flow=foo,
        flow_run=flow_run,
        client=prefect_client,
        task_runner=test_task_runner,
        result_store=result_store,
        parameters={"x": "y"},
    ):
        ctx = FlowRunContext.get()
        assert ctx.flow is foo
        assert ctx.flow_run == flow_run
        assert ctx.client is prefect_client
        assert ctx.task_runner is test_task_runner
        assert ctx.result_store == result_store
        assert isinstance(ctx.start_time, DateTime)
        assert ctx.parameters == {"x": "y"}


async def test_task_run_context(prefect_client, flow_run):
    @task
    def foo():
        pass

    task_run = await prefect_client.create_task_run(foo, flow_run.id, dynamic_key="")
    result_store = ResultStore()

    with TaskRunContext(
        task=foo,
        task_run=task_run,
        client=prefect_client,
        result_store=result_store,
        parameters={"foo": "bar"},
    ):
        ctx = TaskRunContext.get()
        assert ctx.task is foo
        assert ctx.task_run == task_run
        assert ctx.result_store == result_store
        assert isinstance(ctx.start_time, DateTime)
        assert ctx.parameters == {"foo": "bar"}


@pytest.fixture
def remove_existing_settings_context():
    token = SettingsContext.__var__.set(None)
    try:
        yield
    finally:
        SettingsContext.__var__.reset(token)


async def test_get_run_context(prefect_client, local_filesystem):
    @flow
    def foo():
        pass

    @task
    def bar():
        pass

    test_task_runner = ThreadPoolTaskRunner()
    flow_run = await prefect_client.create_flow_run(foo)
    task_run = await prefect_client.create_task_run(bar, flow_run.id, dynamic_key="")

    with pytest.raises(RuntimeError):
        get_run_context()

    with pytest.raises(MissingContextError):
        get_run_context()

    with FlowRunContext(
        flow=foo,
        flow_run=flow_run,
        client=prefect_client,
        task_runner=test_task_runner,
        result_store=await ResultStore().update_for_flow(foo),
        parameters={"x": "y"},
    ) as flow_ctx:
        assert get_run_context() is flow_ctx

        with TaskRunContext(
            task=bar,
            task_run=task_run,
            client=prefect_client,
            result_store=await get_result_store().update_for_task(bar, _sync=False),
            parameters={"foo": "bar"},
        ) as task_ctx:
            assert get_run_context() is task_ctx, "Task context takes precedence"

        assert get_run_context() is flow_ctx, "Flow context is restored and retrieved"


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
            settings=prefect.settings.get_current_settings(),
        ) as context:
            assert get_settings_context() is context
            assert context.profile == Profile(name="test", settings={})
            assert context.settings == prefect.settings.get_current_settings()

    def test_get_settings_context_missing(self, monkeypatch):
        # It's kind of hard to actually exit the default profile, so we patch `get`
        monkeypatch.setattr(
            "prefect.context.SettingsContext.get", MagicMock(return_value=None)
        )
        with pytest.raises(MissingContextError, match="No settings context found"):
            get_settings_context()

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

    def test_root_settings_context_creates_home(self, tmpdir, monkeypatch):
        monkeypatch.setenv("PREFECT_HOME", str(tmpdir / "testing"))
        with root_settings_context() as ctx:
            assert ctx.settings.home == tmpdir / "testing"
            assert ctx.settings.home.exists()

    def test_settings_context_does_not_setup_logging(self, monkeypatch):
        setup_logging = MagicMock()
        monkeypatch.setattr(
            "prefect.logging.configuration.setup_logging", setup_logging
        )
        with use_profile("ephemeral"):
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

    def test_root_settings_context_default(self):
        result = root_settings_context()
        assert result is not None
        assert isinstance(result, SettingsContext)

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
        monkeypatch.setattr("sys.argv", cli_command)
        result = root_settings_context()
        assert result is not None

    def test_root_settings_context_respects_cli(self, monkeypatch, foo_profile):
        use_profile = MagicMock()
        monkeypatch.setattr("prefect.context.use_profile", use_profile)
        monkeypatch.setattr("sys.argv", ["/prefect", "--profile", "foo"])
        result = root_settings_context()
        assert result is not None

    def test_root_settings_context_respects_environment_variable(
        self, temporary_profiles_path, monkeypatch
    ):
        temporary_profiles_path.write_text(
            textwrap.dedent(
                """
                [profiles.foo]
                PREFECT_API_URL="foo"
                """
            )
        )
        monkeypatch.setenv("PREFECT_PROFILE", "foo")
        settings_context = root_settings_context()
        assert settings_context.profile.name == "foo"

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
            " will be used instead." in err
        )

    @pytest.mark.usefixtures("remove_existing_settings_context")
    def test_root_settings_context_accessible_in_new_thread(self):
        from concurrent.futures.thread import ThreadPoolExecutor

        with ThreadPoolExecutor() as executor:
            result = executor.submit(get_settings_context).result()

        assert result == GLOBAL_SETTINGS_CONTEXT

    @pytest.mark.usefixtures("remove_existing_settings_context")
    def test_root_settings_context_accessible_in_new_loop(self):
        from anyio.from_thread import start_blocking_portal

        with start_blocking_portal() as portal:
            result = portal.call(get_settings_context)

        assert result == GLOBAL_SETTINGS_CONTEXT


class TestSerializeContext:
    def test_empty(self):
        serialized = serialize_context()
        assert serialized == {
            "flow_run_context": {},
            "task_run_context": {},
            "tags_context": {},
            "settings_context": SettingsContext.get().serialize(),
        }

    async def test_with_flow_run_context(self, prefect_client):
        @flow
        def foo():
            pass

        test_task_runner = ThreadPoolTaskRunner()
        flow_run = await prefect_client.create_flow_run(foo)
        result_store = await ResultStore().update_for_flow(foo)

        with FlowRunContext(
            flow=foo,
            flow_run=flow_run,
            client=prefect_client,
            task_runner=test_task_runner,
            result_store=result_store,
            parameters={"x": "y"},
        ) as flow_run_context:
            serialized = serialize_context()
            assert serialized == {
                "flow_run_context": flow_run_context.serialize(),
                "task_run_context": {},
                "tags_context": {},
                "settings_context": SettingsContext.get().serialize(),
            }

    async def test_with_task_run_context(self, prefect_client, flow_run):
        @task
        def bar():
            pass

        task_run = await prefect_client.create_task_run(
            bar, flow_run.id, dynamic_key=""
        )

        with TaskRunContext(
            task=bar,
            task_run=task_run,
            client=prefect_client,
            result_store=await get_result_store().update_for_task(bar),
            parameters={"foo": "bar"},
        ) as task_ctx:
            serialized = serialize_context()
            assert serialized == {
                "flow_run_context": {},
                "task_run_context": task_ctx.serialize(),
                "tags_context": {},
                "settings_context": SettingsContext.get().serialize(),
            }

    def test_with_tags_context(self):
        with tags("a", "b") as current_tags:
            serialized = serialize_context()
            assert serialized == {
                "flow_run_context": {},
                "task_run_context": {},
                "tags_context": {"current_tags": current_tags},
                "settings_context": SettingsContext.get().serialize(),
            }

    def test_with_multiple_contexts(self):
        with tags("a", "b") as current_tags:
            with temporary_settings(
                updates={PREFECT_API_KEY: "test", PREFECT_API_URL: "test"}
            ):
                serialized = serialize_context()
                assert serialized == {
                    "flow_run_context": {},
                    "task_run_context": {},
                    "tags_context": {"current_tags": current_tags},
                    "settings_context": SettingsContext.get().serialize(),
                }
                assert (
                    serialized["settings_context"]["settings"]["api"]["key"] == "test"
                )
                assert (
                    serialized["settings_context"]["settings"]["api"]["url"] == "test"
                )


class TestHydratedContext:
    def test_empty(self):
        initial_settings_context = SettingsContext.get()
        with hydrated_context({}):
            assert FlowRunContext.get() is None
            assert TaskRunContext.get() is None
            assert TagsContext.get().current_tags == set()
            assert SettingsContext.get() == initial_settings_context

    async def test_with_flow_run_context(self, prefect_client):
        @flow
        def foo():
            pass

        test_task_runner = ThreadPoolTaskRunner()
        flow_run = await prefect_client.create_flow_run(foo)
        result_store = await ResultStore().update_for_flow(foo)
        flow_run_context = FlowRunContext(
            flow=foo,
            flow_run=flow_run,
            client=prefect_client,
            task_runner=test_task_runner,
            result_store=result_store,
            parameters={"x": "y"},
        )

        with hydrated_context(
            {
                "flow_run_context": flow_run_context.serialize(),
            }
        ):
            hydrated_flow_run_context = FlowRunContext.get()
            assert hydrated_flow_run_context.flow is foo
            assert hydrated_flow_run_context.flow_run == flow_run
            assert (
                hydrated_flow_run_context.client is not None
            )  # this won't be the same object as the original client
            assert (
                hydrated_flow_run_context.task_runner is not None
            )  # this won't be the same object as the original task runner
            assert (
                hydrated_flow_run_context.result_store is not None
            )  # this won't be the same object as the original result store
            assert isinstance(hydrated_flow_run_context.start_time, DateTime)
            assert hydrated_flow_run_context.parameters == {"x": "y"}

    async def test_task_runner_started_when_hydrating_context(
        self, prefect_client: PrefectClient
    ):
        """
        This test ensures the task runner for a flow run context is started when
        the context is hydrated. This enables calling .submit and .map on tasks
        running in remote environments like Dask and Ray.

        Regression test for https://github.com/PrefectHQ/prefect/issues/14788
        """

        @flow
        def foo():
            pass

        @task
        def bar():
            return 42

        test_task_runner = ThreadPoolTaskRunner()
        flow_run = await prefect_client.create_flow_run(foo, state=Running())
        result_store = await ResultStore().update_for_flow(foo)
        flow_run_context = FlowRunContext(
            flow=foo,
            flow_run=flow_run,
            client=prefect_client,
            task_runner=test_task_runner,
            result_store=result_store,
            parameters={"x": "y"},
        )

        with hydrated_context(
            {
                "flow_run_context": flow_run_context.serialize(),
            }
        ):
            hydrated_flow_run_context = FlowRunContext.get()
            assert hydrated_flow_run_context

            future = hydrated_flow_run_context.task_runner.submit(bar, parameters={})
            assert future.result() == 42

    async def test_with_task_run_context(self, prefect_client, flow_run):
        @task
        def bar():
            pass

        task_run = await prefect_client.create_task_run(
            bar, flow_run.id, dynamic_key=""
        )
        task_ctx = TaskRunContext(
            task=bar,
            task_run=task_run,
            client=prefect_client,
            result_store=await get_result_store().update_for_task(bar),
            parameters={"foo": "bar"},
        )

        with hydrated_context(
            {
                "task_run_context": task_ctx.serialize(),
            }
        ):
            hydrated_task_ctx = TaskRunContext.get()
            assert hydrated_task_ctx.task is bar
            assert hydrated_task_ctx.task_run == task_run
            assert hydrated_task_ctx.result_store is not None
            assert isinstance(hydrated_task_ctx.start_time, DateTime)
            assert hydrated_task_ctx.parameters == {"foo": "bar"}

    def test_with_tags_context(self):
        with hydrated_context(
            {
                "tags_context": {"current_tags": {"a", "b"}},
            }
        ):
            assert TagsContext.get().current_tags == {"a", "b"}

    def test_with_settings_context(self):
        with hydrated_context(
            {
                "settings_context": {
                    "profile": {"name": "test", "settings": {}, "source": None},
                    "settings": {"api": {"key": "test", "url": "test"}},
                },
            }
        ):
            assert SettingsContext.get().profile == Profile(
                name="test",
                settings={},
                source=None,
            )
            settings = SettingsContext.get().settings
            assert (
                settings.api.key is not None
                and settings.api.key.get_secret_value() == "test"
            )
            assert settings.api.url == "test"
