from armada_client.typings import JobState
from conftest import make_job_status_response, make_job_submit_response
from prefect_armada.flows import run_armada_job, run_armada_job_async


def test_run_armada_job(
    valid_armada_job_block, mock_armada_client, mock_binoculars_client
):
    mock_armada_client.submit_jobs.return_value = make_job_submit_response()
    mock_armada_client.get_job_status.return_value = make_job_status_response(
        **{"test-job-id": JobState.SUCCEEDED.value}
    )

    result = run_armada_job(armada_job=valid_armada_job_block)

    assert result == {"test-job-id": "line one\nline two"}


async def test_run_armada_job_async(
    valid_armada_job_block, mock_armada_client, mock_binoculars_client
):
    mock_armada_client.submit_jobs.return_value = make_job_submit_response()
    mock_armada_client.get_job_status.return_value = make_job_status_response(
        **{"test-job-id": JobState.SUCCEEDED.value}
    )

    result = await run_armada_job_async(armada_job=valid_armada_job_block)

    assert result == {"test-job-id": "line one\nline two"}


def test_run_armada_job_streams_logs_with_print_func(
    valid_armada_job_block, mock_armada_client, mock_binoculars_client
):
    mock_armada_client.submit_jobs.return_value = make_job_submit_response()
    mock_armada_client.get_job_status.return_value = make_job_status_response(
        **{"test-job-id": JobState.SUCCEEDED.value}
    )
    printed = []

    run_armada_job(armada_job=valid_armada_job_block, print_func=printed.append)

    assert printed == ["line one", "line two"]
