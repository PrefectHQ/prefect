from __future__ import annotations

import pytest

from prefect.client.schemas import actions as client_actions
from prefect.server import models
from prefect.server.schemas import core
from prefect.states import Failed, Scheduled, to_state_create


@pytest.mark.usefixtures("client", "session", "flow")
class TestRetryCountersPersistence:
    async def test_reschedule_retries_persisted_via_api(self, client, session, flow):
        deployment = await models.deployments.create_deployment(
            session=session,
            deployment=core.Deployment(name="", flow_id=flow.id),
        )
        await session.commit()

        fr_create = client_actions.FlowRunCreate(
            flow_id=flow.id,
            deployment_id=deployment.id,
            state=to_state_create(Failed()),
        )

        resp = await client.post("/flow_runs/", json=fr_create.model_dump(mode="json"))
        assert resp.status_code == 201
        flow_run_id = resp.json()["id"]

        sched_state = to_state_create(Scheduled())
        set_resp = await client.post(
            f"/flow_runs/{flow_run_id}/set_state",
            json=sched_state.model_dump(mode="json"),
        )
        assert set_resp.status_code in (200, 201)

        read_resp = await client.get(f"/flow_runs/{flow_run_id}")
        assert read_resp.status_code == 200
        fr = read_resp.json()
        assert "empirical_policy" in fr
        assert fr["empirical_policy"]["reschedule_retries"] == 1
