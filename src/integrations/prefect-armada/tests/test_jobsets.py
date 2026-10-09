from armada_client.typings import JobState
from prefect_armada.jobsets import (
    cancel_jobset,
    get_job_status_by_external_job_uri,
    job_states_from_values,
    reprioritize_jobset,
)


async def test_cancel_jobset(armada_credentials, mock_armada_client):
    await cancel_jobset.fn(
        armada_credentials=armada_credentials,
        queue="test-queue",
        job_set_id="test-job-set",
    )

    assert mock_armada_client.cancel_jobset.call_args[1] == {
        "queue": "test-queue",
        "job_set_id": "test-job-set",
        "filter_states": [],
    }


async def test_cancel_jobset_coerces_filter_states(
    armada_credentials, mock_armada_client
):
    await cancel_jobset.fn(
        armada_credentials=armada_credentials,
        queue="test-queue",
        job_set_id="test-job-set",
        filter_states=["queued", JobState.RUNNING, 1],
    )

    assert mock_armada_client.cancel_jobset.call_args[1]["filter_states"] == [
        JobState.QUEUED,
        JobState.RUNNING,
        JobState.PENDING,
    ]


async def test_reprioritize_jobset(armada_credentials, mock_armada_client):
    await reprioritize_jobset.fn(
        armada_credentials=armada_credentials,
        queue="test-queue",
        job_set_id="test-job-set",
        new_priority=3,
    )

    call = mock_armada_client.reprioritize_jobs.call_args[1]
    assert call["new_priority"] == 3
    assert call["job_ids"] is None
    assert call["job_set_id"] == "test-job-set"


async def test_get_job_status_by_external_job_uri(
    armada_credentials, mock_armada_client
):
    await get_job_status_by_external_job_uri.fn(
        armada_credentials=armada_credentials,
        queue="test-queue",
        job_set_id="test-job-set",
        external_job_uri="prefect://flow-run/abc",
    )

    assert mock_armada_client.get_job_status_by_external_job_uri.call_args[1] == {
        "queue": "test-queue",
        "job_set_id": "test-job-set",
        "external_job_uri": "prefect://flow-run/abc",
    }


def test_job_states_from_values():
    assert job_states_from_values(["failed", 3]) == [
        JobState.FAILED,
        JobState.SUCCEEDED,
    ]
