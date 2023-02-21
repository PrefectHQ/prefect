from datetime import timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from textwrap import dedent
from unittest.mock import Mock

import pendulum
import pytest

import prefect.server.models as models
import prefect.server.schemas as schemas
from prefect import flow
from prefect.deployments import Deployment
from prefect.filesystems import LocalFileSystem
from prefect.infrastructure import Process
from prefect.testing.cli import invoke_and_assert
from prefect.testing.utilities import AsyncMock
from prefect.utilities.asyncutils import run_sync_in_worker_thread


@pytest.fixture
def patch_import(monkeypatch):
    @flow(description="Need a non-trivial description here.", version="A")
    def fn():
        pass

    monkeypatch.setattr(
        "prefect.cli.deployment.load_flow_from_entrypoint", lambda path: fn
    )
    return fn


@pytest.fixture
def dep_path():
    return "./dog.py"


@pytest.fixture
def built_deployment_with_queue_and_limit_overrides(patch_import, tmp_path):
    d = Deployment(
        name="TEST",
        flow_name="fn",
    )
    deployment_id = d.apply()

    invoke_and_assert(
        [
            "deployment",
            "build",
            "fake-path.py:fn",
            "-n",
            "TEST",
            "-o",
            str(tmp_path / "test.yaml"),
            "-q",
            "the-queue-to-end-all-queues",
            "--limit",
            "424242",
        ],
        expected_code=0,
        temp_dir=tmp_path,
    )


@pytest.fixture
def applied_deployment_with_queue_and_limit_overrides(patch_import, tmp_path):
    d = Deployment(
        name="TEST",
        flow_name="fn",
    )
    deployment_id = d.apply()

    invoke_and_assert(
        [
            "deployment",
            "build",
            "fake-path.py:fn",
            "-n",
            "TEST",
            "-o",
            str(tmp_path / "test.yaml"),
            "-q",
            "the-mother-of-all-queues",
        ],
        expected_code=0,
        temp_dir=tmp_path,
    )
    invoke_and_assert(
        [
            "deployment",
            "apply",
            str(tmp_path / "test.yaml"),
            "-l",
            "4242",
        ],
        expected_code=0,
        temp_dir=tmp_path,
    )


@pytest.fixture
def storage_block(tmp_path):
    storage = LocalFileSystem(basepath=tmp_path / "storage")
    storage.save(name="test-storage-block")
    return storage


@pytest.fixture
def infra_block(tmp_path):
    infra = Process()
    infra.save(name="test-infra-block")
    return infra


@pytest.fixture
def mock_build_from_flow(monkeypatch):
    mock_build_from_flow = AsyncMock()

    # needed to handle `if deployment.storage` check
    ret = Mock()
    ret.storage = None
    mock_build_from_flow.return_value = ret

    monkeypatch.setattr(
        "prefect.cli.deployment.Deployment.build_from_flow", mock_build_from_flow
    )

    # not needed for test
    monkeypatch.setattr(
        "prefect.cli.deployment.create_work_queue_and_set_concurrency_limit",
        AsyncMock(),
    )

    return mock_build_from_flow


@pytest.fixture(autouse=True)
async def ensure_default_agent_pool_exists(session):
    # The default agent work pool is created by a migration, but is cleared on
    # consecutive test runs. This fixture ensures that the default agent work
    # pool exists before each test.
    default_work_pool = await models.workers.read_work_pool_by_name(
        session=session, work_pool_name=models.workers.DEFAULT_AGENT_WORK_POOL_NAME
    )
    if default_work_pool is None:
        default_work_pool = await models.workers.create_work_pool(
            session=session,
            work_pool=schemas.actions.WorkPoolCreate(
                name=models.workers.DEFAULT_AGENT_WORK_POOL_NAME, type="prefect-agent"
            ),
        )
        await session.commit()
    assert default_work_pool is not None


class TestSchedules:
    def test_passing_cron_schedules_to_build(self, patch_import, tmp_path):
        invoke_and_assert(
            [
                "deployment",
                "build",
                "fake-path.py:fn",
                "-n",
                "TEST",
                "-o",
                str(tmp_path / "test.yaml"),
                "--cron",
                "0 4 * * *",
                "--timezone",
                "Europe/Berlin",
            ],
            expected_code=0,
            temp_dir=tmp_path,
        )

        deployment = Deployment.load_from_yaml(tmp_path / "test.yaml")
        assert deployment.schedule.cron == "0 4 * * *"
        assert deployment.schedule.timezone == "Europe/Berlin"

    def test_passing_interval_schedules_to_build(self, patch_import, tmp_path):
        invoke_and_assert(
            [
                "deployment",
                "build",
                "fake-path.py:fn",
                "-n",
                "TEST",
                "-o",
                str(tmp_path / "test.yaml"),
                "--interval",
                "42",
                "--anchor-date",
                "2040-02-02",
                "--timezone",
                "America/New_York",
            ],
            expected_code=0,
            temp_dir=tmp_path,
        )

        deployment = Deployment.load_from_yaml(tmp_path / "test.yaml")
        assert deployment.schedule.interval == timedelta(seconds=42)
        assert deployment.schedule.anchor_date == pendulum.parse("2040-02-02")
        assert deployment.schedule.timezone == "America/New_York"

    def test_passing_anchor_without_interval_exits(self, patch_import, tmp_path):
        invoke_and_assert(
            [
                "deployment",
                "build",
                "fake-path.py:fn",
                "-n",
                "TEST",
                "-o",
                str(tmp_path / "test.yaml"),
                "--anchor-date",
                "2018-02-02",
            ],
            expected_code=1,
            temp_dir=tmp_path,
            expected_output_contains=(
                "An anchor date can only be provided with an interval schedule"
            ),
        )

    def test_parsing_rrule_schedule_string_literal(self, patch_import, tmp_path):
        invoke_and_assert(
            [
                "deployment",
                "build",
                "fake-path.py:fn",
                "-n",
                "TEST",
                "-o",
                str(tmp_path / "test.yaml"),
                "--rrule",
                "DTSTART:20220910T110000\nRRULE:FREQ=HOURLY;BYDAY=MO,TU,WE,TH,FR,SA;BYHOUR=9,10,11,12,13,14,15,16,17",
            ],
            expected_code=0,
            temp_dir=tmp_path,
        )

        deployment = Deployment.load_from_yaml(tmp_path / "test.yaml")
        assert (
            deployment.schedule.rrule
            == "DTSTART:20220910T110000\nRRULE:FREQ=HOURLY;BYDAY=MO,TU,WE,TH,FR,SA;BYHOUR=9,10,11,12,13,14,15,16,17"
        )

    def test_parsing_rrule_schedule_json(self, patch_import, tmp_path):
        invoke_and_assert(
            [
                "deployment",
                "build",
                "fake-path.py:fn",
                "-n",
                "TEST",
                "-o",
                str(tmp_path / "test.yaml"),
                "--rrule",
                (
                    '{"rrule":'
                    ' "DTSTART:20220910T110000\\nRRULE:FREQ=HOURLY;BYDAY=MO,TU,WE,TH,FR,SA;BYHOUR=9,10,11,12,13,14,15,16,17",'
                    ' "timezone": "America/New_York"}'
                ),
            ],
            expected_code=0,
            temp_dir=tmp_path,
        )

        deployment = Deployment.load_from_yaml(tmp_path / "test.yaml")
        assert (
            deployment.schedule.rrule
            == "DTSTART:20220910T110000\nRRULE:FREQ=HOURLY;BYDAY=MO,TU,WE,TH,FR,SA;BYHOUR=9,10,11,12,13,14,15,16,17"
        )
        assert deployment.schedule.timezone == "America/New_York"

    def test_parsing_rrule_timezone_overrides_if_passed_explicitly(
        self, patch_import, tmp_path
    ):
        invoke_and_assert(
            [
                "deployment",
                "build",
                "fake-path.py:fn",
                "-n",
                "TEST",
                "-o",
                str(tmp_path / "test.yaml"),
                "--rrule",
                (
                    '{"rrule":'
                    ' "DTSTART:20220910T110000\\nRRULE:FREQ=HOURLY;BYDAY=MO,TU,WE,TH,FR,SA;BYHOUR=9,10,11,12,13,14,15,16,17",'
                    ' "timezone": "America/New_York"}'
                ),
                "--timezone",
                "Europe/Berlin",
            ],
            expected_code=0,
            temp_dir=tmp_path,
        )

        deployment = Deployment.load_from_yaml(tmp_path / "test.yaml")
        assert (
            deployment.schedule.rrule
            == "DTSTART:20220910T110000\nRRULE:FREQ=HOURLY;BYDAY=MO,TU,WE,TH,FR,SA;BYHOUR=9,10,11,12,13,14,15,16,17"
        )
        assert deployment.schedule.timezone == "Europe/Berlin"

    @pytest.mark.parametrize(
        "schedules",
        [
            ["--cron", "cron-str", "--interval", 42],
            ["--rrule", "rrule-str", "--interval", 42],
            ["--rrule", "rrule-str", "--cron", "cron-str"],
            ["--rrule", "rrule-str", "--cron", "cron-str", "--interval", 42],
        ],
    )
    def test_providing_multiple_schedules_exits_with_error(
        self, patch_import, tmp_path, schedules
    ):
        name = "TEST"
        output_path = str(tmp_path / "test.yaml")
        entrypoint = "fake-path.py:fn"
        cmd = [
            "deployment",
            "build",
            entrypoint,
            "-n",
            name,
            "-o",
            output_path,
        ]
        cmd += schedules

        res = invoke_and_assert(
            cmd,
            expected_code=1,
            expected_output="Only one schedule type can be provided.",
        )


class TestParameterOverrides:
    def test_param_overrides(self, patch_import, tmp_path):
        d = Deployment(
            name="TEST",
            flow_name="fn",
        )
        deployment_id = d.apply()

        invoke_and_assert(
            [
                "deployment",
                "build",
                "fake-path.py:fn",
                "-n",
                "TEST",
                "-o",
                str(tmp_path / "test.yaml"),
                "--param",
                "foo=bar",
                "--param",
                'greenman_says={"parsed as json": "I am"}',
            ],
            expected_code=0,
            temp_dir=tmp_path,
        )

        deployment = Deployment.load_from_yaml(tmp_path / "test.yaml")
        assert deployment.parameters["foo"] == "bar"
        assert deployment.parameters["greenman_says"] == {"parsed as json": "I am"}

    def test_parameters_override(self, patch_import, tmp_path):
        d = Deployment(
            name="TEST",
            flow_name="fn",
        )
        deployment_id = d.apply()

        invoke_and_assert(
            [
                "deployment",
                "build",
                "fake-path.py:fn",
                "-n",
                "TEST",
                "-o",
                str(tmp_path / "test.yaml"),
                "--params",
                '{"greenman_says": {"parsed as json": "I am"}}',
            ],
            expected_code=0,
            temp_dir=tmp_path,
        )

        deployment = Deployment.load_from_yaml(tmp_path / "test.yaml")
        assert deployment.parameters["greenman_says"] == {"parsed as json": "I am"}

    def test_mixing_parameter_overrides(self, patch_import, tmp_path):
        d = Deployment(
            name="TEST",
            flow_name="fn",
        )
        deployment_id = d.apply()

        invoke_and_assert(
            [
                "deployment",
                "build",
                "fake-path.py:fn",
                "-n",
                "TEST",
                "-o",
                str(tmp_path / "test.yaml"),
                "--params",
                '{"which": "parameter"}',
                "--param",
                "shouldbe:used",
            ],
            expected_code=1,
            temp_dir=tmp_path,
        )


class TestFlowName:
    @pytest.mark.filterwarnings("ignore:does not have upload capabilities")
    def test_flow_name_called_correctly(
        self, patch_import, tmp_path, mock_build_from_flow
    ):
        name = "TEST"
        output_path = str(tmp_path / "test.yaml")
        entrypoint = "fake-path.py:fn"
        cmd = [
            "deployment",
            "build",
            entrypoint,
            "-n",
            name,
            "-o",
            output_path,
        ]

        invoke_and_assert(
            cmd,
            expected_code=0,
        )

        build_kwargs = mock_build_from_flow.call_args.kwargs
        assert build_kwargs["name"] == name

    def test_not_providing_name_exits_with_error(self, patch_import, tmp_path):
        output_path = str(tmp_path / "test.yaml")
        entrypoint = "fake-path.py:fn"
        cmd = [
            "deployment",
            "build",
            entrypoint,
            "-o",
            output_path,
        ]

        res = invoke_and_assert(
            cmd,
            expected_code=1,
            expected_output=(
                "A name for this deployment must be provided with the '--name' flag.\n"
            ),
        )

    def test_name_must_be_provided_by_default(self, dep_path):
        invoke_and_assert(
            ["deployment", "build", dep_path],
            expected_output_contains=["A name for this deployment must be provided"],
            expected_code=1,
        )


class TestEntrypoint:
    def test_entrypoint_is_saved_as_relative_path(self, patch_import, tmp_path):
        invoke_and_assert(
            [
                "deployment",
                "build",
                "fake-path.py:fn",
                "-n",
                "TEST",
                "-o",
                str(tmp_path / "test.yaml"),
            ],
            expected_code=0,
            temp_dir=tmp_path,
        )

        deployment = Deployment.load_from_yaml(tmp_path / "test.yaml")
        assert deployment.entrypoint == "fake-path.py:fn"

    def test_poorly_formed_entrypoint_raises_correct_error(
        self, patch_import, tmp_path
    ):
        name = "TEST"
        file_name = "test_no_suffix"
        output_path = str(tmp_path / file_name)
        entrypoint = "fake-path.py"
        cmd = ["deployment", "build", "-n", name]
        cmd += [entrypoint]

        invoke_and_assert(
            cmd,
            expected_code=1,
            expected_output_contains=(
                "Your flow entrypoint must include the name of the function that is"
                f" the entrypoint to your flow.\nTry {entrypoint}:<flow_name>"
            ),
        )

    def test_entrypoint_that_does_not_point_to_flow_raises_error(self, tmp_path):
        code = """
        def fn():
            pass
        """
        fpath = tmp_path / "dog.py"
        fpath.write_text(dedent(code))

        name = "TEST"
        entrypoint = f"{fpath}:fn"
        cmd = ["deployment", "build", "-n", name]
        cmd += [entrypoint]

        res = invoke_and_assert(
            cmd,
            expected_code=1,
            expected_output_contains=(
                f"Function with name 'fn' is not a flow. Make sure that it is decorated"
                f" with '@flow'"
            ),
        )

    def test_entrypoint_that_points_to_wrong_flow_raises_error(self, tmp_path):
        code = """
        from prefect import flow

        @flow
        def cat():
            pass
        """
        fpath = tmp_path / "dog.py"
        fpath.write_text(dedent(code))

        name = "TEST"
        entrypoint = f"{fpath}:fn"
        cmd = ["deployment", "build", "-n", name]
        cmd += [entrypoint]

        res = invoke_and_assert(
            cmd,
            expected_code=1,
            expected_output_contains=(
                f"Flow function with name 'fn' not found in {str(fpath)!r}"
            ),
        )

    def test_entrypoint_that_does_not_point_to_python_file_raises_error(self, tmp_path):
        code = """
        def fn():
            pass
        """
        fpath = tmp_path / "dog.cake"
        fpath.write_text(dedent(code))

        name = "TEST"
        entrypoint = f"{fpath}:fn"
        cmd = ["deployment", "build", "-n", name]
        cmd += [entrypoint]

        res = invoke_and_assert(
            cmd,
            expected_code=1,
            expected_output_contains=f"No module named ",
        )

    def test_entrypoint_works_with_flow_with_custom_name(self):
        flow_code = """
        from prefect import flow

        @flow(name="SoMe CrAz_y N@me")
        def dog():
            pass
        """
        file_name = "f.py"
        with TemporaryDirectory() as tmp_dir:
            Path(file_name).write_text(dedent(flow_code))

            dep_name = "TEST"
            entrypoint = f"{file_name}:dog"
            cmd = ["deployment", "build", "-n", dep_name]
            cmd += [entrypoint]

            res = invoke_and_assert(
                cmd,
                expected_code=0,
            )

    def test_entrypoint_works_with_flow_func_with_underscores(self):
        flow_code = """
        from prefect import flow
        
        @flow
        def dog_flow_func():
            pass
        """
        file_name = "f.py"
        with TemporaryDirectory() as tmp_dir:
            Path(file_name).write_text(dedent(flow_code))

            dep_name = "TEST"
            entrypoint = f"{file_name}:dog_flow_func"
            cmd = ["deployment", "build", "-n", dep_name]
            cmd += [entrypoint]

            res = invoke_and_assert(
                cmd,
                expected_code=0,
            )


class TestWorkQueue:
    def test_work_queue_name_is_populated_as_default(self, patch_import, tmp_path):
        invoke_and_assert(
            [
                "deployment",
                "build",
                "fake-path.py:fn",
                "-n",
                "TEST",
                "-o",
                str(tmp_path / "test.yaml"),
            ],
            expected_code=0,
            temp_dir=tmp_path,
        )

        deployment = Deployment.load_from_yaml(tmp_path / "test.yaml")
        assert deployment.work_queue_name == "default"

    def test_success_message_with_work_queue_name(self, patch_import, tmp_path):
        invoke_and_assert(
            [
                "deployment",
                "build",
                "fake-path.py:fn",
                "-n",
                "TEST",
                "-o",
                str(tmp_path / "test.yaml"),
            ],
            expected_code=0,
            temp_dir=tmp_path,
        )
        invoke_and_assert(
            [
                "deployment",
                "apply",
                str(tmp_path / "test.yaml"),
            ],
            expected_output_contains=[
                (
                    "To execute flow runs from this deployment, start an agent "
                    "that pulls work from the 'default' work queue:"
                ),
                "$ prefect agent start -q 'default'",
            ],
        )


class TestWorkPool:
    async def test_creates_work_queue_in_work_pool(
        self,
        patch_import,
        tmp_path,
        work_pool,
        session,
    ):
        await run_sync_in_worker_thread(
            invoke_and_assert,
            [
                "deployment",
                "build",
                "fake-path.py:fn",
                "-n",
                "TEST",
                "-p",
                work_pool.name,
                "-q",
                "new-queue",
                "-o",
                str(tmp_path / "test.yaml"),
                "--apply",
            ],
            expected_code=0,
            temp_dir=tmp_path,
        )

        deployment = await Deployment.load_from_yaml(tmp_path / "test.yaml")
        assert deployment.work_pool_name == work_pool.name
        assert deployment.work_queue_name == "new-queue"

        work_queue = await models.workers.read_work_queue_by_name(
            session=session, work_pool_name=work_pool.name, work_queue_name="new-queue"
        )
        assert work_queue is not None


class TestAutoApply:
    def test_auto_apply_flag(self, patch_import, tmp_path):
        d = Deployment(
            name="TEST",
            flow_name="fn",
        )
        deployment_id = d.apply()

        invoke_and_assert(
            [
                "deployment",
                "build",
                "fake-path.py:fn",
                "-n",
                "TEST",
                "-o",
                str(tmp_path / "test.yaml"),
                "--apply",
            ],
            expected_code=0,
            expected_output_contains=[
                f"Deployment '{d.flow_name}/{d.name}' successfully created with id"
                f" '{deployment_id}'."
            ],
            temp_dir=tmp_path,
        )

    def test_auto_apply_work_pool_does_not_exist(
        self,
        patch_import,
        tmp_path,
    ):
        invoke_and_assert(
            [
                "deployment",
                "build",
                "fake-path.py:fn",
                "-n",
                "TEST",
                "-o",
                str(tmp_path / "test.yaml"),
                "-p",
                "gibberish",
                "--apply",
            ],
            expected_code=1,
            expected_output_contains=(
                [
                    (
                        "This deployment specifies a work pool name of 'gibberish', but"
                        " no such work pool exists."
                    ),
                    "To create a work pool via the CLI:",
                    "$ prefect work-pool create 'gibberish'",
                ]
            ),
            temp_dir=tmp_path,
        )


class TestWorkQueueConcurrency:
    async def test_setting_work_queue_concurrency_limits_with_build(
        self, built_deployment_with_queue_and_limit_overrides, orion_client
    ):
        queue = await orion_client.read_work_queue_by_name(
            "the-queue-to-end-all-queues"
        )
        assert queue.concurrency_limit == 424242

    async def test_setting_work_queue_concurrency_limits_with_apply(
        self, applied_deployment_with_queue_and_limit_overrides, orion_client
    ):
        queue = await orion_client.read_work_queue_by_name("the-mother-of-all-queues")
        assert queue.concurrency_limit == 4242


class TestVersionFlag:
    def test_version_flag_takes_precedence(self, patch_import, tmp_path):
        d = Deployment(
            name="TEST",
            flow_name="fn",
            version="server",
        )
        assert d.apply()

        invoke_and_assert(
            [
                "deployment",
                "build",
                "fake-path.py:fn",
                "-n",
                "TEST",
                "-o",
                str(tmp_path / "test.yaml"),
                "-v",
                "CLI-version",
            ],
            expected_code=0,
            temp_dir=tmp_path,
        )

        deployment = Deployment.load_from_yaml(tmp_path / "test.yaml")
        assert deployment.version == "CLI-version"


class TestLoadingSettings:
    def test_server_side_settings_are_used_if_present(self, patch_import, tmp_path):
        """
        This only applies to tags, work queue name, description, schedules and default parameter values
        """
        d = Deployment(
            name="TEST",
            flow_name="fn",
            description="server-side value",
            version="server",
            parameters={"key": "server"},
            tags=["server-tag"],
            work_queue_name="dev",
        )
        assert d.apply()

        invoke_and_assert(
            [
                "deployment",
                "build",
                "fake-path.py:fn",
                "-n",
                "TEST",
                "-o",
                str(tmp_path / "test.yaml"),
            ],
            expected_code=0,
            temp_dir=tmp_path,
        )

        deployment = Deployment.load_from_yaml(tmp_path / "test.yaml")
        assert deployment.description == "server-side value"
        assert deployment.tags == ["server-tag"]
        assert deployment.parameters == dict(key="server")
        assert deployment.work_queue_name == "dev"


class TestSkipUpload:
    @pytest.mark.filterwarnings("ignore:does not have upload capabilities")
    @pytest.mark.parametrize("skip_upload", ["--skip-upload", None])
    def test_skip_upload_called_correctly(
        self, patch_import, tmp_path, skip_upload, mock_build_from_flow
    ):
        name = "TEST"
        output_path = str(tmp_path / "test.yaml")
        entrypoint = "fake-path.py:fn"
        cmd = [
            "deployment",
            "build",
            entrypoint,
            "-n",
            name,
            "-o",
            output_path,
        ]

        if skip_upload:
            cmd.append(skip_upload)

        invoke_and_assert(
            cmd,
            expected_code=0,
        )

        build_kwargs = mock_build_from_flow.call_args.kwargs

        if skip_upload:
            assert build_kwargs["skip_upload"] == True
        else:
            assert build_kwargs["skip_upload"] == False


class TestInfraAndInfraBlock:
    def test_providing_infra_block_and_infra_type_exits_with_error(
        self, patch_import, tmp_path
    ):
        name = "TEST"
        output_path = str(tmp_path / "test.yaml")
        entrypoint = "fake-path.py:fn"
        cmd = [
            "deployment",
            "build",
            entrypoint,
            "-n",
            name,
            "-o",
            output_path,
        ]
        cmd += ["-i", "process", "-ib", "my-block"]

        res = invoke_and_assert(
            cmd,
            expected_code=1,
            expected_output=(
                "Only one of `infra` or `infra_block` can be provided, please choose"
                " one."
            ),
        )

    @pytest.mark.filterwarnings("ignore:does not have upload capabilities")
    def test_infra_block_called_correctly(
        self, patch_import, tmp_path, infra_block, mock_build_from_flow
    ):
        name = "TEST"
        output_path = str(tmp_path / "test.yaml")
        entrypoint = "fake-path.py:fn"
        cmd = [
            "deployment",
            "build",
            entrypoint,
            "-n",
            name,
            "-o",
            output_path,
        ]
        cmd += ["-ib", "process/test-infra-block"]

        res = invoke_and_assert(
            cmd,
            expected_code=0,
        )

        build_kwargs = mock_build_from_flow.call_args.kwargs
        assert build_kwargs["infrastructure"] == infra_block

    @pytest.mark.filterwarnings("ignore:does not have upload capabilities")
    def test_infra_type_specifies_infra_block_on_deployment(
        self, patch_import, tmp_path, mock_build_from_flow
    ):
        name = "TEST"
        output_path = str(tmp_path / "test.yaml")
        entrypoint = "fake-path.py:fn"
        cmd = [
            "deployment",
            "build",
            entrypoint,
            "-n",
            name,
            "-o",
            output_path,
        ]
        cmd += ["-i", "docker-container"]

        res = invoke_and_assert(
            cmd,
            expected_code=0,
        )

        build_kwargs = mock_build_from_flow.call_args.kwargs
        infra = build_kwargs["infrastructure"]
        assert infra.type == "docker-container"


class TestInfraOverrides:
    @pytest.mark.filterwarnings("ignore:does not have upload capabilities")
    def test_overrides_called_correctly(
        self, patch_import, tmp_path, mock_build_from_flow
    ):
        name = "TEST"
        output_path = str(tmp_path / "test.yaml")
        entrypoint = "fake-path.py:fn"
        overrides = ["my.dog=1", "your.cat=test"]
        cmd = [
            "deployment",
            "build",
            entrypoint,
            "-n",
            name,
            "-o",
            output_path,
        ]
        for override in overrides:
            cmd += ["--override", override]
        res = invoke_and_assert(
            cmd,
            expected_code=0,
        )

        build_kwargs = mock_build_from_flow.call_args.kwargs
        assert build_kwargs["infra_overrides"] == {"my.dog": "1", "your.cat": "test"}

    @pytest.mark.filterwarnings("ignore:does not have upload capabilities")
    def test_overrides_default_is_empty(
        self, patch_import, tmp_path, mock_build_from_flow
    ):
        name = "TEST"
        output_path = str(tmp_path / "test.yaml")
        entrypoint = "fake-path.py:fn"
        cmd = [
            "deployment",
            "build",
            entrypoint,
            "-n",
            name,
            "-o",
            output_path,
        ]
        res = invoke_and_assert(
            cmd,
            expected_code=0,
        )

        build_kwargs = mock_build_from_flow.call_args.kwargs
        assert build_kwargs["infra_overrides"] == {}


class TestStorageBlock:
    @pytest.mark.filterwarnings("ignore:does not have upload capabilities")
    def test_storage_block_called_correctly(
        self, patch_import, tmp_path, storage_block, mock_build_from_flow
    ):
        name = "TEST"
        output_path = str(tmp_path / "test.yaml")
        entrypoint = "fake-path.py:fn"
        cmd = [
            "deployment",
            "build",
            entrypoint,
            "-n",
            name,
            "-o",
            output_path,
        ]
        cmd += ["-sb", "local-file-system/test-storage-block"]

        res = invoke_and_assert(
            cmd,
            expected_code=0,
        )

        build_kwargs = mock_build_from_flow.call_args.kwargs
        assert build_kwargs["storage"] == storage_block


class TestOutputFlag:
    def test_output_file_with_wrong_suffix_exits_with_error(
        self, patch_import, tmp_path
    ):
        name = "TEST"
        file_name = "test.not_yaml"
        output_path = str(tmp_path / file_name)
        entrypoint = "fake-path.py:fn"
        cmd = [
            "deployment",
            "build",
            entrypoint,
            "-n",
            name,
        ]
        cmd += ["-o", output_path]

        res = invoke_and_assert(
            cmd, expected_code=1, expected_output="Output file must be a '.yaml' file."
        )

    @pytest.mark.filterwarnings("ignore:does not have upload capabilities")
    def test_yaml_appended_to_out_file_without_suffix(
        self, monkeypatch, patch_import, tmp_path, mock_build_from_flow
    ):
        name = "TEST"
        file_name = "test_no_suffix"
        output_path = str(tmp_path / file_name)
        entrypoint = "fake-path.py:fn"
        cmd = [
            "deployment",
            "build",
            entrypoint,
            "-n",
            name,
        ]
        cmd += ["-o", output_path]

        invoke_and_assert(
            cmd,
            expected_code=0,
        )

        build_kwargs = mock_build_from_flow.call_args.kwargs
        assert build_kwargs["output"] == Path(output_path + ".yaml")


class TestOtherStuff:
    @pytest.mark.filterwarnings("ignore:does not have upload capabilities")
    def test_correct_flow_passed_to_deployment_object(
        self, patch_import, tmp_path, mock_build_from_flow
    ):
        name = "TEST"
        file_name = "test_no_suffix"
        output_path = str(tmp_path / file_name)
        entrypoint = "fake-path.py:fn"
        cmd = ["deployment", "build", entrypoint, "-n", name, "-o", output_path]

        invoke_and_assert(
            cmd,
            expected_code=0,
        )

        build_kwargs = mock_build_from_flow.call_args.kwargs
        assert build_kwargs["flow"] == patch_import
