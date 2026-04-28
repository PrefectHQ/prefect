import pytest
from urllib.parse import quote
from prefect.server import models, schemas
from prefect._internal.compatibility.starlette import status


@pytest.mark.parametrize("flow_run_name", ["🚀-production-logs", "simple-logs"])
async def test_download_flow_run_logs_encoding_and_bom(
    client, session, flow, flow_run_name
):
    # Create a flow run with potential special characters
    flow_run = await models.flow_runs.create_flow_run(
        session=session,
        flow_run=schemas.core.FlowRun(flow_id=flow.id, name=flow_run_name),
    )
    await session.commit()

    # Call the download endpoint
    response = await client.get(f"/flow_runs/{flow_run.id}/logs/download")

    assert response.status_code == status.HTTP_200_OK

    # Check Content-Disposition header (RFC 5987)
    encoded_name = quote(f"{flow_run_name}-logs.csv", safe="")
    expected_content_disposition = (
        f"attachment; filename=\"flow-run-logs.csv\"; filename*=UTF-8''{encoded_name}"
    )
    assert response.headers["Content-Disposition"] == expected_content_disposition
    assert response.headers["Content-Type"] == "text/csv; charset=utf-8"

    # Check for UTF-8 BOM (b'\xef\xbb\xbf')
    assert response.content.startswith(b"\xef\xbb\xbf")

    # Check CSV headers after BOM
    decoded_content = response.content.decode("utf-8-sig")
    assert decoded_content.startswith("timestamp,level,flow_run_id,task_run_id,message")
