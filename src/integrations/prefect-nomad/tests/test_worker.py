"""Tests for the Nomad worker, job configuration, and result."""

import time
from unittest.mock import MagicMock, patch

import anyio.abc
import pytest
from prefect_nomad.credentials import NomadCredentials
from prefect_nomad.exceptions import (
    NomadEvaluationError,
    NomadJobSchedulingError,
    NomadJobTimeoutError,
)
from prefect_nomad.worker import (
    NomadTaskResources,
    NomadWorker,
    NomadWorkerJobConfiguration,
    NomadWorkerResult,
)

import prefect
from prefect.exceptions import InfrastructureNotFound
from prefect.utilities.dockerutils import get_prefect_image_name


class TestNomadTaskResources:
    def test_defaults(self):
        r = NomadTaskResources()
        assert r.cpu == 500
        assert r.memory_mb == 256

    def test_custom_values(self):
        r = NomadTaskResources(cpu=1000, memory_mb=512)
        assert r.cpu == 1000
        assert r.memory_mb == 512

    def test_cpu_minimum(self):
        with pytest.raises(Exception):
            NomadTaskResources(cpu=0)

    def test_memory_minimum(self):
        with pytest.raises(Exception):
            NomadTaskResources(memory_mb=0)


class TestJobConfigurationDefaults:
    def test_default_image_is_prefect_image(self):
        cfg = NomadWorkerJobConfiguration()
        assert cfg.image == get_prefect_image_name()

    def test_default_datacenters(self):
        cfg = NomadWorkerJobConfiguration()
        assert cfg.datacenters == ["dc1"]

    def test_default_stream_output(self):
        cfg = NomadWorkerJobConfiguration()
        assert cfg.stream_output is True

    def test_default_force_pull(self):
        cfg = NomadWorkerJobConfiguration()
        assert cfg.force_pull is False

    def test_default_privileged(self):
        cfg = NomadWorkerJobConfiguration()
        assert cfg.privileged is False

    def test_default_poll_interval(self):
        cfg = NomadWorkerJobConfiguration()
        assert cfg.poll_interval == 1

    def test_default_credentials_is_none(self):
        cfg = NomadWorkerJobConfiguration()
        assert cfg.nomad_credentials is None

    def test_default_job_timeout_is_none(self):
        cfg = NomadWorkerJobConfiguration()
        assert cfg.job_timeout is None

    def test_custom_job_timeout(self):
        cfg = NomadWorkerJobConfiguration(job_timeout=300)
        assert cfg.job_timeout == 300


class TestSlugify:
    @pytest.mark.parametrize(
        "input_name, expected",
        [
            ("simple-name", "simple-name"),
            ("My Flow Run", "my-flow-run"),
            ("flow_run_123", "flow-run-123"),
            ("---leading-hyphens", "leading-hyphens"),
            ("trailing-hyphens---", "trailing-hyphens"),
            ("multiple---hyphens", "multiple-hyphens"),
            ("special!@#chars", "special-chars"),
            ("UPPERCASE", "uppercase"),
            ("a" * 100, "a" * 63),
            ("", None),
            ("---", None),
            ("!@#$%", None),
            (None, None),
        ],
    )
    def test_slugify(self, input_name, expected):
        result = NomadWorkerJobConfiguration._slugify(input_name)
        assert result == expected


class TestPrepareForFlowRun:
    def test_with_deployment_sets_job_name(self, flow_run):
        """Job ID = full flow run ID."""
        cfg = NomadWorkerJobConfiguration(image="prefect:latest")
        cfg.env = {}
        cfg.labels = {}

        deployment = MagicMock()
        deployment.name = "My ETL Pipeline"

        cfg.prepare_for_flow_run(flow_run, deployment=deployment)

        assert cfg.name == str(flow_run.id)

    def test_without_deployment_uses_flow_run_id(self, flow_run):
        """Job ID = full flow run ID when no deployment exists."""
        cfg = NomadWorkerJobConfiguration(image="prefect:latest")
        cfg.env = {}
        cfg.labels = {}

        cfg.prepare_for_flow_run(flow_run)

        assert cfg.name == str(flow_run.id)

    def test_stores_flow_run_name(self, flow_run):
        """_flow_run_name is set to the slugified flow run name."""
        cfg = NomadWorkerJobConfiguration(image="prefect:latest")
        cfg.env = {}
        cfg.labels = {}

        cfg.prepare_for_flow_run(flow_run)

        expected = NomadWorkerJobConfiguration._slugify(flow_run.name)
        assert cfg._flow_run_name == expected

    def test_stores_deployment_name(self, flow_run):
        """_deployment_name is set to the slugified deployment name."""
        cfg = NomadWorkerJobConfiguration(image="prefect:latest")
        cfg.env = {}
        cfg.labels = {}

        deployment = MagicMock()
        deployment.name = "Nightly Sync"

        cfg.prepare_for_flow_run(flow_run, deployment=deployment)

        assert cfg._deployment_name == "nightly-sync"

    def test_deployment_name_not_set_without_deployment(self, flow_run):
        """_deployment_name stays None when no deployment is provided."""
        cfg = NomadWorkerJobConfiguration(image="prefect:latest")
        cfg.env = {}
        cfg.labels = {}

        cfg.prepare_for_flow_run(flow_run)

        assert cfg._deployment_name is None

    def test_spec_uses_flow_run_name_for_task_group_and_task(self, flow_run):
        """After prepare_for_flow_run, spec uses flow run name for TG/Task."""
        cfg = NomadWorkerJobConfiguration(image="prefect:latest")
        cfg.env = {}
        cfg.labels = {}

        cfg.prepare_for_flow_run(flow_run)

        spec = cfg.build_nomad_job_spec()
        tg = spec["Job"]["TaskGroups"][0]
        task = tg["Tasks"][0]

        expected = NomadWorkerJobConfiguration._slugify(flow_run.name)
        assert tg["Name"] == expected
        assert task["Name"] == expected

    def test_image_defaults_when_not_set(self, flow_run):
        """Image defaults to Prefect image name if not explicitly set."""
        cfg = NomadWorkerJobConfiguration()
        cfg.env = {}
        cfg.labels = {}

        cfg.prepare_for_flow_run(flow_run)

        assert cfg.image == get_prefect_image_name()


class TestBuildNomadJobSpec:
    def test_basic_job_structure(self):
        cfg = NomadWorkerJobConfiguration(image="prefect:latest")
        cfg.name = "test-job"
        cfg.env = {"PREFECT_API_URL": "http://localhost:4200/api"}

        spec = cfg.build_nomad_job_spec()

        assert "Job" in spec
        job = spec["Job"]
        assert job["ID"] == "test-job"
        assert job["Name"] == "test-job"
        assert job["Type"] == "batch"
        assert job["Datacenters"] == ["dc1"]

    def test_job_has_single_task_group(self):
        """Without prepare_for_flow_run, TaskGroup/Task use defaults."""
        cfg = NomadWorkerJobConfiguration(image="prefect:latest")
        cfg.name = "test-job"

        spec = cfg.build_nomad_job_spec()
        job = spec["Job"]

        assert len(job["TaskGroups"]) == 1
        tg = job["TaskGroups"][0]
        assert tg["Name"] == "prefect"
        assert tg["Count"] == 1
        # Task also uses default name
        task = tg["Tasks"][0]
        assert task["Name"] == "prefect-job"

    def test_restart_policy_zero_attempts(self):
        cfg = NomadWorkerJobConfiguration(image="prefect:latest")
        cfg.name = "test-job"

        spec = cfg.build_nomad_job_spec()
        tg = spec["Job"]["TaskGroups"][0]

        assert tg["RestartPolicy"]["Attempts"] == 0
        assert tg["RestartPolicy"]["Mode"] == "fail"

    def test_docker_driver_config(self):
        cfg = NomadWorkerJobConfiguration(image="my-image:v1")
        cfg.name = "test-job"

        spec = cfg.build_nomad_job_spec()
        task = spec["Job"]["TaskGroups"][0]["Tasks"][0]

        assert task["Driver"] == "docker"
        assert task["Config"]["image"] == "my-image:v1"

    def test_env_vars_are_stringified(self):
        cfg = NomadWorkerJobConfiguration(image="prefect:latest")
        cfg.name = "test-job"
        cfg.env = {"KEY": "value", "NUM": 42}

        spec = cfg.build_nomad_job_spec()
        task = spec["Job"]["TaskGroups"][0]["Tasks"][0]

        assert task["Env"]["KEY"] == "value"
        assert task["Env"]["NUM"] == "42"

    def test_resources(self):
        cfg = NomadWorkerJobConfiguration(
            image="prefect:latest",
            task_resources=NomadTaskResources(cpu=1000, memory_mb=512),
        )
        cfg.name = "test-job"

        spec = cfg.build_nomad_job_spec()
        task = spec["Job"]["TaskGroups"][0]["Tasks"][0]

        assert task["Resources"]["CPU"] == 1000
        assert task["Resources"]["MemoryMB"] == 512

    def test_command_is_split(self):
        cfg = NomadWorkerJobConfiguration(image="prefect:latest")
        cfg.name = "test-job"
        cfg.command = "python -m prefect.engine"

        spec = cfg.build_nomad_job_spec()
        docker_config = spec["Job"]["TaskGroups"][0]["Tasks"][0]["Config"]

        assert docker_config["command"] == "python"
        assert docker_config["args"] == ["-m", "prefect.engine"]

    def test_single_command_no_args(self):
        cfg = NomadWorkerJobConfiguration(image="prefect:latest")
        cfg.name = "test-job"
        cfg.command = "python"

        spec = cfg.build_nomad_job_spec()
        docker_config = spec["Job"]["TaskGroups"][0]["Tasks"][0]["Config"]

        assert docker_config["command"] == "python"
        assert "args" not in docker_config

    def test_no_command(self):
        cfg = NomadWorkerJobConfiguration(image="prefect:latest")
        cfg.name = "test-job"
        cfg.command = None

        spec = cfg.build_nomad_job_spec()
        docker_config = spec["Job"]["TaskGroups"][0]["Tasks"][0]["Config"]

        assert "command" not in docker_config
        assert "args" not in docker_config

    def test_docker_auth(self):
        cfg = NomadWorkerJobConfiguration(
            image="prefect:latest",
            docker_auth={"username": "user", "password": "pass"},
        )
        cfg.name = "test-job"

        spec = cfg.build_nomad_job_spec()
        docker_config = spec["Job"]["TaskGroups"][0]["Tasks"][0]["Config"]

        assert docker_config["auth"]["username"] == "user"
        assert docker_config["auth"]["password"] == "pass"

    def test_network_mode(self):
        cfg = NomadWorkerJobConfiguration(image="prefect:latest", network_mode="host")
        cfg.name = "test-job"

        spec = cfg.build_nomad_job_spec()
        docker_config = spec["Job"]["TaskGroups"][0]["Tasks"][0]["Config"]

        assert docker_config["network_mode"] == "host"

    def test_privileged(self):
        cfg = NomadWorkerJobConfiguration(image="prefect:latest", privileged=True)
        cfg.name = "test-job"

        spec = cfg.build_nomad_job_spec()
        docker_config = spec["Job"]["TaskGroups"][0]["Tasks"][0]["Config"]

        assert docker_config["privileged"] is True

    def test_force_pull(self):
        cfg = NomadWorkerJobConfiguration(image="prefect:latest", force_pull=True)
        cfg.name = "test-job"

        spec = cfg.build_nomad_job_spec()
        docker_config = spec["Job"]["TaskGroups"][0]["Tasks"][0]["Config"]

        assert docker_config["force_pull"] is True

    def test_extra_docker_config(self):
        cfg = NomadWorkerJobConfiguration(
            image="prefect:latest",
            extra_docker_config={"dns_servers": ["8.8.8.8"]},
        )
        cfg.name = "test-job"

        spec = cfg.build_nomad_job_spec()
        docker_config = spec["Job"]["TaskGroups"][0]["Tasks"][0]["Config"]

        assert docker_config["dns_servers"] == ["8.8.8.8"]

    def test_extra_task_config(self):
        cfg = NomadWorkerJobConfiguration(
            image="prefect:latest",
            extra_task_config={"KillTimeout": 30_000_000_000},
        )
        cfg.name = "test-job"

        spec = cfg.build_nomad_job_spec()
        task = spec["Job"]["TaskGroups"][0]["Tasks"][0]

        assert task["KillTimeout"] == 30_000_000_000

    def test_namespace_in_spec(self):
        cfg = NomadWorkerJobConfiguration(
            image="prefect:latest", namespace="production"
        )
        cfg.name = "test-job"

        spec = cfg.build_nomad_job_spec()
        assert spec["Job"]["Namespace"] == "production"

    def test_region_in_spec(self):
        cfg = NomadWorkerJobConfiguration(image="prefect:latest", region="us-east-1")
        cfg.name = "test-job"

        spec = cfg.build_nomad_job_spec()
        assert spec["Job"]["Region"] == "us-east-1"

    def test_priority_in_spec(self):
        cfg = NomadWorkerJobConfiguration(image="prefect:latest", priority=75)
        cfg.name = "test-job"

        spec = cfg.build_nomad_job_spec()
        assert spec["Job"]["Priority"] == 75

    def test_no_namespace_when_none(self):
        cfg = NomadWorkerJobConfiguration(image="prefect:latest")
        cfg.name = "test-job"

        spec = cfg.build_nomad_job_spec()
        assert "Namespace" not in spec["Job"]

    def test_meta_includes_prefect_version(self):
        cfg = NomadWorkerJobConfiguration(image="prefect:latest")
        cfg.name = "test-job"

        spec = cfg.build_nomad_job_spec()
        assert spec["Job"]["Meta"]["prefect.version"] == prefect.__version__

    def test_custom_meta_merged(self):
        cfg = NomadWorkerJobConfiguration(
            image="prefect:latest",
            meta={"team": "data-eng"},
        )
        cfg.name = "test-job"

        spec = cfg.build_nomad_job_spec()
        meta = spec["Job"]["Meta"]
        assert meta["team"] == "data-eng"
        assert meta["prefect.version"] == prefect.__version__

    def test_labels_converted_to_meta(self):
        cfg = NomadWorkerJobConfiguration(image="prefect:latest")
        cfg.name = "test-job"
        cfg.labels = {"prefect.io/flow-run-id": "abc-123"}

        spec = cfg.build_nomad_job_spec()
        meta = spec["Job"]["Meta"]
        # Dots and slashes are converted to underscores
        assert meta["prefect_io_flow-run-id"] == "abc-123"

    def test_fallback_job_id_when_no_name(self):
        cfg = NomadWorkerJobConfiguration(image="prefect:latest")
        cfg.name = None

        spec = cfg.build_nomad_job_spec()
        assert spec["Job"]["ID"] == "prefect-flow-run"


class TestInfrastructurePid:
    def test_parse_infrastructure_pid_http(self):
        addr, job_id = NomadWorker._parse_infrastructure_pid(
            "http://127.0.0.1:4646:my-job"
        )
        assert addr == "http://127.0.0.1:4646"
        assert job_id == "my-job"

    def test_parse_infrastructure_pid_https(self):
        addr, job_id = NomadWorker._parse_infrastructure_pid(
            "https://nomad.example.com:4646:my-job"
        )
        assert addr == "https://nomad.example.com:4646"
        assert job_id == "my-job"

    def test_parse_infrastructure_pid_no_port(self):
        addr, job_id = NomadWorker._parse_infrastructure_pid(
            "http://nomad.local:my-job"
        )
        assert addr == "http://nomad.local"
        assert job_id == "my-job"

    def test_parse_infrastructure_pid_invalid(self):
        with pytest.raises(ValueError, match="Invalid infrastructure PID"):
            NomadWorker._parse_infrastructure_pid("no-colons")

    def test_get_infrastructure_pid_with_credentials(self):
        creds = NomadCredentials(address="http://10.0.0.1:4646")
        cfg = NomadWorkerJobConfiguration(
            image="prefect:latest", nomad_credentials=creds
        )

        mock_client = MagicMock()
        worker = NomadWorker.__new__(NomadWorker)
        pid = worker._get_infrastructure_pid(mock_client, "my-job", cfg)

        assert pid == "http://10.0.0.1:4646:my-job"

    def test_get_infrastructure_pid_without_credentials(self):
        cfg = NomadWorkerJobConfiguration(image="prefect:latest")

        mock_client = MagicMock()
        mock_client.secure = False
        mock_client.host = "127.0.0.1"
        mock_client.port = 4646

        worker = NomadWorker.__new__(NomadWorker)
        pid = worker._get_infrastructure_pid(mock_client, "my-job", cfg)

        assert pid == "http://127.0.0.1:4646:my-job"

    def test_get_infrastructure_pid_secure(self):
        cfg = NomadWorkerJobConfiguration(image="prefect:latest")

        mock_client = MagicMock()
        mock_client.secure = True
        mock_client.host = "nomad.example.com"
        mock_client.port = 4646

        worker = NomadWorker.__new__(NomadWorker)
        pid = worker._get_infrastructure_pid(mock_client, "my-job", cfg)

        assert pid == "https://nomad.example.com:4646:my-job"


class TestGetExitCodeFromAllocation:
    def _worker(self):
        return NomadWorker.__new__(NomadWorker)

    def test_terminated_event_exit_code_zero(self):
        alloc = {
            "ClientStatus": "complete",
            "TaskStates": {
                "prefect-job": {"Events": [{"Type": "Terminated", "ExitCode": 0}]}
            },
        }
        assert self._worker()._get_exit_code_from_allocation(alloc, "prefect-job") == 0

    def test_terminated_event_exit_code_nonzero(self):
        alloc = {
            "ClientStatus": "failed",
            "TaskStates": {
                "prefect-job": {"Events": [{"Type": "Terminated", "ExitCode": 137}]}
            },
        }
        assert (
            self._worker()._get_exit_code_from_allocation(alloc, "prefect-job") == 137
        )

    def test_complete_without_terminated_event(self):
        alloc = {
            "ClientStatus": "complete",
            "TaskStates": {"prefect-job": {"Events": [{"Type": "Started"}]}},
        }
        assert self._worker()._get_exit_code_from_allocation(alloc, "prefect-job") == 0

    def test_failed_without_terminated_event(self):
        alloc = {
            "ClientStatus": "failed",
            "TaskStates": {"prefect-job": {"Events": [{"Type": "Started"}]}},
        }
        assert self._worker()._get_exit_code_from_allocation(alloc, "prefect-job") == 1

    def test_no_task_states(self):
        alloc = {"ClientStatus": "lost"}
        assert self._worker()._get_exit_code_from_allocation(alloc, "prefect-job") == 1

    def test_uses_last_terminated_event(self):
        """When multiple Terminated events exist, use the last one."""
        alloc = {
            "ClientStatus": "failed",
            "TaskStates": {
                "prefect-job": {
                    "Events": [
                        {"Type": "Terminated", "ExitCode": 1},
                        {"Type": "Restarting"},
                        {"Type": "Terminated", "ExitCode": 2},
                    ]
                }
            },
        }
        # reversed() iteration means we find ExitCode=2 first
        assert self._worker()._get_exit_code_from_allocation(alloc, "prefect-job") == 2


class TestWaitForEvaluation:
    def _worker(self):
        return NomadWorker.__new__(NomadWorker)

    def test_eval_completes_successfully(self, mock_nomad_client):
        """Evaluation with status=complete and no FailedTGAllocs returns normally."""
        cfg = NomadWorkerJobConfiguration(image="prefect:latest", poll_interval=1)
        worker = self._worker()
        worker._logger = MagicMock()

        # Should return without raising
        worker._wait_for_evaluation(
            mock_nomad_client, "eval-123", "test-job", cfg, time.monotonic()
        )

        mock_nomad_client.evaluation.get_evaluation.assert_called_once_with("eval-123")

    def test_eval_scheduling_failure_raises(
        self, mock_nomad_client_eval_scheduling_failure
    ):
        """Evaluation with FailedTGAllocs raises NomadJobSchedulingError."""
        cfg = NomadWorkerJobConfiguration(image="prefect:latest", poll_interval=1)
        worker = self._worker()
        worker._logger = MagicMock()

        with pytest.raises(NomadJobSchedulingError, match="failed to schedule"):
            worker._wait_for_evaluation(
                mock_nomad_client_eval_scheduling_failure,
                "eval-123",
                "test-job",
                cfg,
                time.monotonic(),
            )

    def test_eval_failed_raises(self, mock_nomad_client_eval_failed):
        """Evaluation with status=failed raises NomadEvaluationError."""
        cfg = NomadWorkerJobConfiguration(image="prefect:latest", poll_interval=1)
        worker = self._worker()
        worker._logger = MagicMock()

        with pytest.raises(NomadEvaluationError, match="failed"):
            worker._wait_for_evaluation(
                mock_nomad_client_eval_failed,
                "eval-123",
                "test-job",
                cfg,
                time.monotonic(),
            )

    def test_eval_canceled_raises(self, mock_nomad_client_eval_canceled):
        """Evaluation with status=canceled raises NomadEvaluationError."""
        cfg = NomadWorkerJobConfiguration(image="prefect:latest", poll_interval=1)
        worker = self._worker()
        worker._logger = MagicMock()

        with pytest.raises(NomadEvaluationError, match="canceled"):
            worker._wait_for_evaluation(
                mock_nomad_client_eval_canceled,
                "eval-123",
                "test-job",
                cfg,
                time.monotonic(),
            )

    def test_eval_chaining_follows_next_eval(self, mock_nomad_client_eval_chained):
        """Evaluation with NextEval follows the chain iteratively."""
        cfg = NomadWorkerJobConfiguration(image="prefect:latest", poll_interval=1)
        worker = self._worker()
        worker._logger = MagicMock()

        worker._wait_for_evaluation(
            mock_nomad_client_eval_chained,
            "eval-123",
            "test-job",
            cfg,
            time.monotonic(),
        )

        # Should have fetched both evals in the chain
        assert mock_nomad_client_eval_chained.evaluation.get_evaluation.call_count == 2
        mock_nomad_client_eval_chained.evaluation.get_evaluation.assert_any_call(
            "eval-123"
        )
        mock_nomad_client_eval_chained.evaluation.get_evaluation.assert_any_call(
            "eval-456"
        )

    def test_eval_timeout_raises(self, mock_nomad_client):
        """Evaluation that takes too long raises NomadJobTimeoutError."""
        cfg = NomadWorkerJobConfiguration(
            image="prefect:latest", poll_interval=1, job_timeout=1
        )
        worker = self._worker()
        worker._logger = MagicMock()

        # Mock returns pending status forever
        mock_nomad_client.evaluation.get_evaluation.return_value = {
            "ID": "eval-123",
            "Status": "pending",
            "FailedTGAllocs": None,
            "NextEval": "",
            "StatusDescription": "",
        }

        # Start time in the past to trigger immediate timeout
        start_time = time.monotonic() - 2

        # Patch time.sleep to avoid actual delays
        with patch("time.sleep"):
            with pytest.raises(
                NomadJobTimeoutError, match="timed out.*evaluation phase"
            ):
                worker._wait_for_evaluation(
                    mock_nomad_client, "eval-123", "test-job", cfg, start_time
                )

    def test_eval_transient_api_error_retries(self, mock_nomad_client):
        """API error during eval fetch logs warning and retries."""
        import nomad.api.exceptions

        cfg = NomadWorkerJobConfiguration(image="prefect:latest", poll_interval=1)
        worker = self._worker()
        worker._logger = MagicMock()

        # First call raises exception, second call succeeds
        mock_nomad_client.evaluation.get_evaluation.side_effect = [
            nomad.api.exceptions.BaseNomadException(MagicMock()),
            {
                "ID": "eval-123",
                "Status": "complete",
                "FailedTGAllocs": None,
                "NextEval": "",
                "StatusDescription": "",
            },
        ]

        # Patch time.sleep to avoid actual delays
        with patch("time.sleep"):
            worker._wait_for_evaluation(
                mock_nomad_client, "eval-123", "test-job", cfg, time.monotonic()
            )

        # Should have logged a warning
        worker._logger.warning.assert_called_once()
        assert mock_nomad_client.evaluation.get_evaluation.call_count == 2


class TestWaitForJobCompletionTimeout:
    def _worker(self):
        return NomadWorker.__new__(NomadWorker)

    def test_allocation_timeout_raises(self, mock_nomad_client):
        """Allocation polling that exceeds job_timeout raises NomadJobTimeoutError."""
        cfg = NomadWorkerJobConfiguration(
            image="prefect:latest", poll_interval=1, job_timeout=1
        )
        worker = self._worker()
        worker._logger = MagicMock()

        # Mock returns running status forever
        mock_nomad_client.job.get_allocations.return_value = [
            {
                "ID": "alloc-123",
                "ClientStatus": "running",
                "TaskStates": {
                    "prefect-job": {
                        "State": "running",
                        "Events": [{"Type": "Started"}],
                    }
                },
            }
        ]

        # Start time in the past to trigger immediate timeout
        start_time = time.monotonic() - 2

        # Patch time.sleep to avoid actual delays
        with patch("time.sleep"):
            with pytest.raises(NomadJobTimeoutError, match="timed out"):
                worker._wait_for_job_completion(
                    mock_nomad_client,
                    "test-job",
                    "prefect-job",
                    cfg,
                    created_event=None,
                    start_time=start_time,
                )

    def test_no_timeout_when_none(self, mock_nomad_client):
        """When job_timeout is None, no timeout is enforced."""
        cfg = NomadWorkerJobConfiguration(image="prefect:latest", poll_interval=1)
        worker = self._worker()
        worker._logger = MagicMock()
        worker._emit_job_status_change_event = MagicMock(return_value=None)

        # Returns complete immediately
        mock_nomad_client.job.get_allocations.return_value = [
            {
                "ID": "alloc-123",
                "ClientStatus": "complete",
                "TaskStates": {
                    "prefect-job": {
                        "State": "dead",
                        "Events": [{"Type": "Terminated", "ExitCode": 0}],
                    }
                },
            }
        ]

        # Should succeed even with old start_time
        exit_code = worker._wait_for_job_completion(
            mock_nomad_client,
            "test-job",
            "prefect-job",
            cfg,
            created_event=None,
            start_time=time.monotonic() - 1000,
        )

        assert exit_code == 0

    def test_no_timeout_when_start_time_none(self, mock_nomad_client):
        """When start_time is None, no timeout is enforced."""
        cfg = NomadWorkerJobConfiguration(
            image="prefect:latest", poll_interval=1, job_timeout=1
        )
        worker = self._worker()
        worker._logger = MagicMock()
        worker._emit_job_status_change_event = MagicMock(return_value=None)

        # Returns complete immediately
        mock_nomad_client.job.get_allocations.return_value = [
            {
                "ID": "alloc-123",
                "ClientStatus": "complete",
                "TaskStates": {
                    "prefect-job": {
                        "State": "dead",
                        "Events": [{"Type": "Terminated", "ExitCode": 0}],
                    }
                },
            }
        ]

        # Should succeed even with job_timeout set
        exit_code = worker._wait_for_job_completion(
            mock_nomad_client,
            "test-job",
            "prefect-job",
            cfg,
            created_event=None,
            start_time=None,
        )

        assert exit_code == 0


class TestWorkerRun:
    async def test_run_submits_job_and_returns_result(
        self, mock_nomad_client, flow_run
    ):
        cfg = NomadWorkerJobConfiguration(image="prefect:latest")
        cfg.name = "test-job"
        cfg.env = {}
        cfg.labels = {}

        with patch.object(
            NomadWorker, "_get_nomad_client", return_value=mock_nomad_client
        ):
            async with NomadWorker(work_pool_name="test") as worker:
                result = await worker.run(flow_run=flow_run, configuration=cfg)

        assert isinstance(result, NomadWorkerResult)
        assert result.status_code == 0
        mock_nomad_client.job.register_job.assert_called_once()

    async def test_run_returns_nonzero_for_failed_job(
        self, mock_nomad_client_failed, flow_run
    ):
        cfg = NomadWorkerJobConfiguration(image="prefect:latest")
        cfg.name = "test-job"
        cfg.env = {}
        cfg.labels = {}

        with patch.object(
            NomadWorker,
            "_get_nomad_client",
            return_value=mock_nomad_client_failed,
        ):
            async with NomadWorker(work_pool_name="test") as worker:
                result = await worker.run(flow_run=flow_run, configuration=cfg)

        assert result.status_code == 1

    async def test_run_reports_infrastructure_pid(self, mock_nomad_client, flow_run):
        cfg = NomadWorkerJobConfiguration(image="prefect:latest")
        cfg.name = "test-job"
        cfg.env = {}
        cfg.labels = {}

        task_status = MagicMock(spec=anyio.abc.TaskStatus)

        with patch.object(
            NomadWorker, "_get_nomad_client", return_value=mock_nomad_client
        ):
            async with NomadWorker(work_pool_name="test") as worker:
                _ = await worker.run(
                    flow_run=flow_run,
                    configuration=cfg,
                    task_status=task_status,
                )

        task_status.started.assert_called_once()
        pid = task_status.started.call_args[0][0]
        assert "test-job" in pid

    async def test_run_passes_correct_job_spec(self, mock_nomad_client, flow_run):
        cfg = NomadWorkerJobConfiguration(
            image="my-custom-image:v2",
            datacenters=["dc1", "dc2"],
            namespace="production",
        )
        cfg.name = "custom-job"
        cfg.env = {"MY_VAR": "hello"}
        cfg.labels = {}

        with patch.object(
            NomadWorker, "_get_nomad_client", return_value=mock_nomad_client
        ):
            async with NomadWorker(work_pool_name="test") as worker:
                await worker.run(flow_run=flow_run, configuration=cfg)

        call_args = mock_nomad_client.job.register_job.call_args
        job_id = call_args[0][0]
        job_spec = call_args[0][1]

        assert job_id == "custom-job"
        assert job_spec["Job"]["Datacenters"] == ["dc1", "dc2"]
        assert job_spec["Job"]["Namespace"] == "production"
        task = job_spec["Job"]["TaskGroups"][0]["Tasks"][0]
        assert task["Config"]["image"] == "my-custom-image:v2"
        assert task["Env"]["MY_VAR"] == "hello"

    async def test_run_uses_credentials_block(self, flow_run):
        """When nomad_credentials is set, get_client() from credentials is used."""
        mock_client = MagicMock()
        mock_client.host = "nomad.example.com"
        mock_client.port = 4646
        mock_client.secure = True
        mock_client.job.register_job.return_value = {"EvalID": "eval-1"}
        mock_client.job.get_allocations.return_value = [
            {
                "ID": "alloc-1",
                "ClientStatus": "complete",
                "TaskStates": {
                    "prefect-job": {"Events": [{"Type": "Terminated", "ExitCode": 0}]}
                },
            }
        ]
        mock_client.client.stream_logs.stream.return_value = ""

        mock_get_client = MagicMock(return_value=mock_client)
        creds = NomadCredentials(address="https://nomad.example.com:4646")
        creds.get_client = mock_get_client

        cfg = NomadWorkerJobConfiguration(
            image="prefect:latest", nomad_credentials=creds
        )
        cfg.name = "test-job"
        cfg.env = {}
        cfg.labels = {}

        async with NomadWorker(work_pool_name="test") as worker:
            result = await worker.run(flow_run=flow_run, configuration=cfg)

        assert result.status_code == 0
        mock_get_client.assert_called_once()


class TestKillInfrastructure:
    async def test_kill_deregisters_job(self, mock_nomad_client):
        cfg = NomadWorkerJobConfiguration(image="prefect:latest")

        with patch.object(
            NomadWorker, "_get_nomad_client", return_value=mock_nomad_client
        ):
            async with NomadWorker(work_pool_name="test") as worker:
                await worker.kill_infrastructure(
                    infrastructure_pid="http://127.0.0.1:4646:my-job",
                    configuration=cfg,
                )

        mock_nomad_client.job.deregister_job.assert_called_once_with(
            "my-job", purge=True
        )

    async def test_kill_raises_not_found(self, mock_nomad_client):
        import nomad.api.exceptions

        mock_nomad_client.job.deregister_job.side_effect = (
            nomad.api.exceptions.URLNotFoundNomadException(MagicMock())
        )

        cfg = NomadWorkerJobConfiguration(image="prefect:latest")

        with patch.object(
            NomadWorker, "_get_nomad_client", return_value=mock_nomad_client
        ):
            async with NomadWorker(work_pool_name="test") as worker:
                with pytest.raises(InfrastructureNotFound, match="not found"):
                    await worker.kill_infrastructure(
                        infrastructure_pid="http://127.0.0.1:4646:missing-job",
                        configuration=cfg,
                    )


class TestGetNomadClient:
    def test_uses_credentials_when_provided(self):
        mock_client = MagicMock()
        creds = NomadCredentials()
        with patch.object(creds, "get_client", return_value=mock_client):
            cfg = NomadWorkerJobConfiguration(
                image="prefect:latest", nomad_credentials=creds
            )
            worker = NomadWorker.__new__(NomadWorker)
            result = worker._get_nomad_client(cfg)

        assert result is mock_client

    @patch("prefect_nomad.worker.nomad.Nomad")
    def test_falls_back_to_env_vars(self, mock_nomad_cls):
        mock_instance = MagicMock()
        mock_nomad_cls.return_value = mock_instance

        cfg = NomadWorkerJobConfiguration(image="prefect:latest")
        worker = NomadWorker.__new__(NomadWorker)
        result = worker._get_nomad_client(cfg)

        assert result is mock_instance
        mock_nomad_cls.assert_called_once_with()


class TestStreamAllocationLogs:
    def test_stream_logs_returns_updated_offset(self):
        mock_client = MagicMock()
        mock_client.client.stream_logs.stream.return_value = "line 1\nline 2\n"

        worker = NomadWorker.__new__(NomadWorker)
        worker._logger = MagicMock()
        new_offset = worker._stream_allocation_logs(
            mock_client, "alloc-123", "prefect-job", offset=0
        )

        assert new_offset == len("line 1\nline 2\n".encode("utf-8"))

    def test_stream_logs_handles_empty_output(self):
        mock_client = MagicMock()
        mock_client.client.stream_logs.stream.return_value = ""

        worker = NomadWorker.__new__(NomadWorker)
        worker._logger = MagicMock()
        new_offset = worker._stream_allocation_logs(
            mock_client, "alloc-123", "prefect-job", offset=0
        )

        assert new_offset == 0

    def test_stream_logs_handles_none_output(self):
        mock_client = MagicMock()
        mock_client.client.stream_logs.stream.return_value = None

        worker = NomadWorker.__new__(NomadWorker)
        worker._logger = MagicMock()
        new_offset = worker._stream_allocation_logs(
            mock_client, "alloc-123", "prefect-job", offset=0
        )

        assert new_offset == 0

    def test_stream_logs_exception_is_swallowed(self):
        mock_client = MagicMock()
        mock_client.client.stream_logs.stream.side_effect = Exception("network error")

        worker = NomadWorker.__new__(NomadWorker)
        worker._logger = MagicMock()
        new_offset = worker._stream_allocation_logs(
            mock_client, "alloc-123", "prefect-job", offset=10
        )

        # Offset should remain unchanged
        assert new_offset == 10


class TestWorkerAttributes:
    def test_worker_type(self):
        assert NomadWorker.type == "nomad"

    def test_worker_job_configuration_class(self):
        assert NomadWorker.job_configuration is NomadWorkerJobConfiguration

    def test_worker_description(self):
        assert "Nomad" in NomadWorker._description

    def test_worker_display_name(self):
        assert NomadWorker._display_name == "Nomad"


class TestNomadWorkerResult:
    def test_result_with_zero_exit(self):
        result = NomadWorkerResult(status_code=0, identifier="test-pid")
        assert result.status_code == 0
        assert result.identifier == "test-pid"

    def test_result_with_nonzero_exit(self):
        result = NomadWorkerResult(status_code=1, identifier="test-pid")
        assert result.status_code == 1
