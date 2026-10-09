import pytest
from prefect_armada.logs import read_job_log, read_job_log_lines


async def test_read_job_log_lines(armada_credentials, mock_binoculars_client):
    log_lines = await read_job_log_lines.fn(
        armada_credentials=armada_credentials,
        job_id="test-job-id",
        namespace="test-namespace",
        pod_number=1,
        since_time="2026-07-29T00:00:00Z",
    )

    assert [line.line for line in log_lines] == ["line one", "line two"]
    assert mock_binoculars_client.logs.call_args[1] == {
        "job_id": "test-job-id",
        "since_time": "2026-07-29T00:00:00Z",
        "pod_namespace": "test-namespace",
        "pod_number": 1,
    }


async def test_read_job_log_lines_defaults_to_the_default_namespace(
    armada_credentials, mock_binoculars_client
):
    await read_job_log_lines.fn(
        armada_credentials=armada_credentials,
        job_id="test-job-id",
        namespace=None,
    )

    assert mock_binoculars_client.logs.call_args[1]["pod_namespace"] == "default"


async def test_read_job_log(armada_credentials, mock_binoculars_client):
    logs = await read_job_log.fn(
        armada_credentials=armada_credentials, job_id="test-job-id"
    )

    assert logs == "line one\nline two"


async def test_read_job_log_with_print_func(armada_credentials, mock_binoculars_client):
    printed = []

    logs = await read_job_log.fn(
        armada_credentials=armada_credentials,
        job_id="test-job-id",
        print_func=printed.append,
    )

    assert printed == ["line one", "line two"]
    assert logs == "line one\nline two"


async def test_read_job_log_propagates_errors(
    armada_credentials, mock_binoculars_client
):
    mock_binoculars_client.logs.side_effect = RuntimeError("pod is gone")

    with pytest.raises(RuntimeError, match="pod is gone"):
        await read_job_log.fn(
            armada_credentials=armada_credentials, job_id="test-job-id"
        )
