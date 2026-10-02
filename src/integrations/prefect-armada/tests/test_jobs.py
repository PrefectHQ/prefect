import grpc
import pytest
from armada_client.armada import job_pb2, submit_pb2
from armada_client.typings import JobState
from conftest import FakeRpcError, make_job_status_response, make_job_submit_response
from prefect_armada.exceptions import (
    ArmadaJobDefinitionError,
    ArmadaJobFailedError,
    ArmadaJobTimeoutError,
)
from prefect_armada.jobs import (
    ArmadaJob,
    cancel_job,
    get_job_details,
    get_job_errors,
    get_job_run_details,
    get_job_status,
    preempt_job,
    reprioritize_job,
    submit_job,
)


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch: pytest.MonkeyPatch):
    """Keeps status polling from actually sleeping between checks."""

    async def fake_sleep(_seconds):
        return None

    monkeypatch.setattr("prefect_armada.jobs.sleep", fake_sleep)


class TestTasks:
    async def test_submit_job(self, armada_credentials, mock_armada_client):
        mock_armada_client.submit_jobs.return_value = make_job_submit_response()

        response = await submit_job.fn(
            armada_credentials=armada_credentials,
            job_request={"namespace": "test-namespace"},
            queue="test-queue",
            job_set_id="test-job-set",
        )

        assert response.job_response_items[0].job_id == "test-job-id"
        call = mock_armada_client.submit_jobs.call_args[1]
        assert call["queue"] == "test-queue"
        assert call["job_set_id"] == "test-job-set"
        assert call["job_request_items"][0].namespace == "test-namespace"

    async def test_submit_job_accepts_multiple_job_requests(
        self, armada_credentials, mock_armada_client
    ):
        await submit_job.fn(
            armada_credentials=armada_credentials,
            job_request=[{"namespace": "a"}, {"namespace": "b"}],
            queue="test-queue",
            job_set_id="test-job-set",
        )

        items = mock_armada_client.submit_jobs.call_args[1]["job_request_items"]
        assert [item.namespace for item in items] == ["a", "b"]

    async def test_submit_job_raises_on_invalid_job_request(
        self, armada_credentials, mock_armada_client
    ):
        with pytest.raises(ArmadaJobDefinitionError):
            await submit_job.fn(
                armada_credentials=armada_credentials,
                job_request={"notAField": 1},
                queue="test-queue",
                job_set_id="test-job-set",
            )
        mock_armada_client.submit_jobs.assert_not_called()

    async def test_cancel_job(self, armada_credentials, mock_armada_client):
        await cancel_job.fn(
            armada_credentials=armada_credentials,
            queue="test-queue",
            job_set_id="test-job-set",
            job_id="test-job-id",
        )

        assert mock_armada_client.cancel_jobs.call_args[1] == {
            "queue": "test-queue",
            "job_set_id": "test-job-set",
            "job_id": "test-job-id",
        }

    async def test_preempt_job(self, armada_credentials, mock_armada_client):
        await preempt_job.fn(
            armada_credentials=armada_credentials,
            queue="test-queue",
            job_set_id="test-job-set",
            job_id="test-job-id",
        )

        assert mock_armada_client.preempt_jobs.call_args[1]["job_id"] == "test-job-id"

    async def test_reprioritize_job(self, armada_credentials, mock_armada_client):
        await reprioritize_job.fn(
            armada_credentials=armada_credentials,
            queue="test-queue",
            job_set_id="test-job-set",
            new_priority=2,
            job_ids=["test-job-id"],
        )

        call = mock_armada_client.reprioritize_jobs.call_args[1]
        assert call["new_priority"] == 2
        assert call["job_ids"] == ["test-job-id"]
        assert call["queue"] == "test-queue"

    async def test_get_job_status(self, armada_credentials, mock_armada_client):
        mock_armada_client.get_job_status.return_value = make_job_status_response(
            **{"test-job-id": JobState.RUNNING.value}
        )

        response = await get_job_status.fn(
            armada_credentials=armada_credentials, job_ids=["test-job-id"]
        )

        assert response.job_states["test-job-id"] == JobState.RUNNING.value
        assert mock_armada_client.get_job_status.call_args[1] == {
            "job_ids": ["test-job-id"]
        }

    async def test_get_job_details(self, armada_credentials, mock_armada_client):
        await get_job_details.fn(
            armada_credentials=armada_credentials, job_ids=["test-job-id"]
        )
        assert mock_armada_client.get_job_details.call_args[1] == {
            "job_ids": ["test-job-id"]
        }

    async def test_get_job_errors(self, armada_credentials, mock_armada_client):
        await get_job_errors.fn(
            armada_credentials=armada_credentials, job_ids=["test-job-id"]
        )
        assert mock_armada_client.get_job_errors.call_args[1] == {
            "job_ids": ["test-job-id"]
        }

    async def test_get_job_run_details(self, armada_credentials, mock_armada_client):
        await get_job_run_details.fn(
            armada_credentials=armada_credentials, run_ids=["test-run-id"]
        )
        assert mock_armada_client.get_job_run_details.call_args[1] == {
            "run_ids": ["test-run-id"]
        }


class TestArmadaJobBlock:
    def test_from_yaml_file(self, armada_credentials):
        from conftest import SAMPLE_JOB_PATH

        job = ArmadaJob.from_yaml_file(
            credentials=armada_credentials,
            manifest_path=SAMPLE_JOB_PATH,
        )

        assert isinstance(job, ArmadaJob)
        assert job.job_request["podSpec"]["containers"][0]["name"] == "prefect-job"

    def test_generates_default_credentials(self):
        job_block = ArmadaJob(job_request={"namespace": "default"})
        assert job_block.credentials is not None
        assert job_block.credentials.cluster_config is None

    async def test_trigger_submits_the_job(
        self, valid_armada_job_block, mock_armada_client
    ):
        mock_armada_client.submit_jobs.return_value = make_job_submit_response()

        job_run = await valid_armada_job_block.trigger()

        assert job_run.job_id == "test-job-id"
        assert job_run.job_set_id == "test-job-set"
        assert mock_armada_client.submit_jobs.call_args[1]["queue"] == "test-queue"

    async def test_trigger_generates_a_job_set_when_not_configured(
        self, armada_credentials, sample_job_dict, mock_armada_client
    ):
        mock_armada_client.submit_jobs.return_value = make_job_submit_response()
        job = ArmadaJob(
            credentials=armada_credentials,
            job_request=sample_job_dict,
            queue="test-queue",
        )

        job_run = await job.trigger()

        assert job_run.job_set_id.startswith("prefect-")

    async def test_trigger_raises_when_armada_reports_an_error(
        self, valid_armada_job_block, mock_armada_client
    ):
        mock_armada_client.submit_jobs.return_value = make_job_submit_response(
            error="queue does not exist"
        )

        with pytest.raises(ArmadaJobFailedError, match="queue does not exist"):
            await valid_armada_job_block.trigger()

    async def test_trigger_raises_when_armada_creates_no_job(
        self, valid_armada_job_block, mock_armada_client
    ):
        mock_armada_client.submit_jobs.return_value = submit_pb2.JobSubmitResponse()

        with pytest.raises(ArmadaJobDefinitionError, match="exactly one job"):
            await valid_armada_job_block.trigger()


class TestArmadaJobRun:
    async def test_wait_for_completion_captures_logs(
        self, valid_armada_job_block, mock_armada_client, mock_binoculars_client
    ):
        mock_armada_client.submit_jobs.return_value = make_job_submit_response()
        mock_armada_client.get_job_status.return_value = make_job_status_response(
            **{"test-job-id": JobState.SUCCEEDED.value}
        )

        job_run = await valid_armada_job_block.trigger()
        await job_run.wait_for_completion()

        assert job_run.job_state is JobState.SUCCEEDED
        assert await job_run.fetch_result() == {"test-job-id": "line one\nline two"}

    async def test_wait_for_completion_polls_until_terminal(
        self, valid_armada_job_block, mock_armada_client, mock_binoculars_client
    ):
        mock_armada_client.submit_jobs.return_value = make_job_submit_response()
        mock_armada_client.get_job_status.side_effect = [
            make_job_status_response(**{"test-job-id": JobState.QUEUED.value}),
            make_job_status_response(**{"test-job-id": JobState.RUNNING.value}),
            make_job_status_response(**{"test-job-id": JobState.SUCCEEDED.value}),
        ]

        job_run = await valid_armada_job_block.trigger()
        await job_run.wait_for_completion()

        assert mock_armada_client.get_job_status.await_count == 3

    async def test_wait_for_completion_raises_on_failure(
        self, valid_armada_job_block, mock_armada_client, mock_binoculars_client
    ):
        mock_armada_client.submit_jobs.return_value = make_job_submit_response()
        mock_armada_client.get_job_status.return_value = make_job_status_response(
            **{"test-job-id": JobState.FAILED.value}
        )
        mock_armada_client.get_job_errors.return_value = job_pb2.JobErrorsResponse(
            job_errors={"test-job-id": "container exited with code 1"}
        )

        job_run = await valid_armada_job_block.trigger()

        with pytest.raises(ArmadaJobFailedError, match="container exited with code 1"):
            await job_run.wait_for_completion()

        # Logs are still captured for a failed job so they can be inspected.
        assert job_run.job_logs == {"test-job-id": "line one\nline two"}

    async def test_wait_for_completion_cancels_on_timeout(
        self, armada_credentials, sample_job_dict, mock_armada_client
    ):
        mock_armada_client.submit_jobs.return_value = make_job_submit_response()
        mock_armada_client.get_job_status.return_value = make_job_status_response(
            **{"test-job-id": JobState.QUEUED.value}
        )
        mock_armada_client.cancel_jobs.return_value = submit_pb2.CancellationResult(
            cancelled_ids=["test-job-id"]
        )
        job = ArmadaJob(
            credentials=armada_credentials,
            job_request=sample_job_dict,
            queue="test-queue",
            job_set_id="test-job-set",
            interval_seconds=1,
            timeout_seconds=1,
        )

        job_run = await job.trigger()

        with pytest.raises(ArmadaJobTimeoutError, match="timed out"):
            await job_run.wait_for_completion()

        assert mock_armada_client.cancel_jobs.call_args[1]["job_id"] == "test-job-id"

    async def test_wait_for_completion_does_not_cancel_when_disabled(
        self, armada_credentials, sample_job_dict, mock_armada_client
    ):
        mock_armada_client.submit_jobs.return_value = make_job_submit_response()
        mock_armada_client.get_job_status.return_value = make_job_status_response(
            **{"test-job-id": JobState.QUEUED.value}
        )
        job = ArmadaJob(
            credentials=armada_credentials,
            job_request=sample_job_dict,
            queue="test-queue",
            interval_seconds=1,
            timeout_seconds=1,
            cancel_on_timeout=False,
        )

        job_run = await job.trigger()

        with pytest.raises(ArmadaJobTimeoutError):
            await job_run.wait_for_completion()

        mock_armada_client.cancel_jobs.assert_not_called()

    async def test_unknown_job_state_keeps_waiting(
        self, valid_armada_job_block, mock_armada_client, mock_binoculars_client
    ):
        mock_armada_client.submit_jobs.return_value = make_job_submit_response()
        mock_armada_client.get_job_status.side_effect = [
            # Armada may not know about a job immediately after submission
            make_job_status_response(),
            make_job_status_response(**{"test-job-id": JobState.SUCCEEDED.value}),
        ]

        job_run = await valid_armada_job_block.trigger()
        await job_run.wait_for_completion()

        assert job_run.job_state is JobState.SUCCEEDED

    async def test_log_failures_do_not_fail_the_run(
        self, valid_armada_job_block, mock_armada_client, mock_binoculars_client
    ):
        mock_armada_client.submit_jobs.return_value = make_job_submit_response()
        mock_armada_client.get_job_status.return_value = make_job_status_response(
            **{"test-job-id": JobState.SUCCEEDED.value}
        )
        mock_binoculars_client.logs.side_effect = FakeRpcError(
            grpc.StatusCode.NOT_FOUND, "pod is gone"
        )

        job_run = await valid_armada_job_block.trigger()
        await job_run.wait_for_completion()

        assert await job_run.fetch_result() == {}

    async def test_fetch_result_before_completion_raises(
        self, valid_armada_job_block, mock_armada_client
    ):
        mock_armada_client.submit_jobs.return_value = make_job_submit_response()

        job_run = await valid_armada_job_block.trigger()

        with pytest.raises(
            ValueError, match="The Armada Job run is not in a completed state"
        ):
            await job_run.fetch_result()

    async def test_print_func_receives_log_lines(
        self, valid_armada_job_block, mock_armada_client, mock_binoculars_client
    ):
        mock_armada_client.submit_jobs.return_value = make_job_submit_response()
        mock_armada_client.get_job_status.return_value = make_job_status_response(
            **{"test-job-id": JobState.SUCCEEDED.value}
        )
        printed = []

        job_run = await valid_armada_job_block.trigger()
        await job_run.wait_for_completion(printed.append)

        assert printed == ["line one", "line two"]
