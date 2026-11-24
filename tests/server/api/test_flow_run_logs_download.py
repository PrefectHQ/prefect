import csv
import io
from datetime import timedelta
from urllib.parse import quote
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from prefect._internal.compatibility.starlette import status
from prefect.server import models, schemas
from prefect.server.api import flow_runs
from prefect.server.database import orm_models
from prefect.types._datetime import now

pytestmark = pytest.mark.clear_db


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

    assert next(csv.reader(io.StringIO(response.text))) == [
        "timestamp",
        "level",
        "flow_run_id",
        "task_run_id",
        "message",
        "worker_id",
        "worker_name",
    ]


@pytest.mark.parametrize(
    ("worker_name", "exported_name"),
    [("worker, east", "worker, east"), ("=worker", "'=worker")],
)
async def test_download_flow_run_logs_worker_attribution(
    client: AsyncClient,
    session: AsyncSession,
    flow_run: orm_models.FlowRun,
    work_pool: orm_models.WorkPool,
    monkeypatch: pytest.MonkeyPatch,
    worker_name: str,
    exported_name: str,
):
    monkeypatch.setattr(flow_runs, "FLOW_RUN_LOGS_DOWNLOAD_PAGE_LIMIT", 2)
    worker = await models.workers.record_worker_heartbeat(
        session=session,
        work_pool=work_pool,
        worker_name=worker_name,
        return_worker=True,
    )
    assert worker is not None
    missing_worker_id = uuid4()
    timestamp = now("UTC")
    logs = [
        ("Run started", None),
        ('Submitted, with "quotes"\nand a newline', worker.id),
        ("Aborted submission", missing_worker_id),
    ]
    await models.logs.create_logs(
        session=session,
        logs=[
            schemas.actions.LogCreate(
                name="prefect.flow_runs",
                level=20,
                timestamp=timestamp + timedelta(seconds=index),
                flow_run_id=flow_run.id,
                message=message,
                worker_id=worker_id,
            )
            for index, (message, worker_id) in enumerate(logs)
        ],
    )
    await session.commit()

    response = await client.get(f"/flow_runs/{flow_run.id}/logs/download")

    assert response.status_code == status.HTTP_200_OK
    rows = list(csv.DictReader(io.StringIO(response.text)))
    assert [row["message"] for row in rows] == [message for message, _ in logs]
    assert [(row["worker_id"], row["worker_name"]) for row in rows] == [
        ("", ""),
        (str(worker.id), exported_name),
        (str(missing_worker_id), ""),
    ]
