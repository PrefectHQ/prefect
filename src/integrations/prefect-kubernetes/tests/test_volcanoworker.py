"""
Comprehensive unit-tests for the custom `VolcanoWorker`.

These tests use pytest+monkeypatch+AsyncMock exclusively,
without touching any real Kubernetes / Volcano clusters.
"""

from __future__ import annotations

import uuid
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from kubernetes_asyncio.client import V1Pod


pytest.importorskip("prefect_kubernetes.volcanoworker")
from prefect_kubernetes.volcanoworker import (  # noqa: E402
    VolcanoWorker,
    VolcanoWorkerJobConfiguration,
)

def minimal_volcano_manifest(image: str = "busybox") -> dict:
    """Return a minimal valid Volcano Job manifest."""
    return {
        "apiVersion": "batch.volcano.sh/v1alpha1",
        "kind": "Job",
        "metadata": {},
        "spec": {
            "queue": "default",
            "maxRetry": 1,
            "minAvailable": 1,
            "schedulerName": "volcano",
            "tasks": [
                {
                    "name": "task",
                    "replicas": 1,
                    "policies": [{"event": "TaskCompleted", "action": "CompleteJob"}],
                    "template": {
                        "spec": {
                            "containers": [
                                {
                                    "name": "c1",
                                    "image": image,
                                    "args": ["echo", "hello"],
                                }
                            ],
                            "restartPolicy": "Never",
                        }
                    },
                }
            ],
        },
    }


@pytest.fixture
def dummy_flow_run():
    fr = MagicMock()
    fr.id = uuid.uuid4()
    fr.name = "unit-flow"
    fr.flow_id = uuid.uuid4()
    return fr


@pytest.fixture
async def job_cfg():
    template = VolcanoWorker.get_default_base_job_template()
    template["job_configuration"]["job_manifest"] = minimal_volcano_manifest()
    cfg = await VolcanoWorkerJobConfiguration.from_template_and_values(
        template, values={}
    )
    return cfg

@pytest.mark.asyncio
async def test_job_configuration_prepare(job_cfg, dummy_flow_run):
    """
    Verify:
    1. Volcano manifest passes validation
    2. prepare_for_flow_run adds image / args / env
    """
    # 1) _validate is already triggered in from_template_and_values; reaching here means it passed

    # 2) prepare
    job_cfg.prepare_for_flow_run(flow_run=dummy_flow_run)

    mc = job_cfg._main_container()
    # Image / args should not be None
    assert "image" in mc and mc["image"]
    assert mc["args"] == ["prefect", "flow-run", "execute"]

    # ENV should contain PREFECT__FLOW_RUN_ID
    env_names = {e["name"] for e in mc["env"]}
    assert "PREFECT__FLOW_RUN_ID" in env_names

@pytest.mark.asyncio
async def test_get_job_pod_selector_order(monkeypatch, job_cfg):
    """
    _get_job_pod should try in order:
      volcano.sh/job-name → job-name → ownerReferences
    """
    # --- Create fake CoreV1Api.list_namespaced_pod ---
    async def fake_list_ns_pod(namespace, label_selector=None):
        fake_resp = MagicMock(items=[])
        # First selector hits
        if label_selector == "volcano.sh/job-name=my-job":
            pod = MagicMock(spec=V1Pod)
            fake_resp.items = [pod]
        return fake_resp

    list_pod_mock = AsyncMock(side_effect=fake_list_ns_pod)
    monkeypatch.setattr(
        "prefect_kubernetes.volcanoworker.CoreV1Api",
        MagicMock(return_value=MagicMock(list_namespaced_pod=list_pod_mock)),
    )

    worker = VolcanoWorker(work_pool_name="dummy")
    pod = await worker._get_job_pod(
        logger=worker.logger,
        job_name="my-job",
        configuration=job_cfg,
        client=MagicMock(),
    )

    # Confirm pod was returned
    assert pod is not None
    # Should use volcano.sh/job-name first
    assert list_pod_mock.await_args_list[0].kwargs["label_selector"].startswith(
        "volcano.sh/job-name"
    )

@pytest.mark.asyncio
async def test_run_full_flow(monkeypatch, job_cfg, dummy_flow_run):
    """
    Mock all external dependencies, run through run(), and ensure:
      • _create_job uses CustomObjectsApi
      • status_code from _watch_job is passed through
      • PID format is clusterUID:ns:name
    """
    fake_job = {
        "metadata": {
            "name": "vc-job-999",
            "namespace": job_cfg.namespace,
        }
    }
    create_job_mock = AsyncMock(return_value=fake_job)
    monkeypatch.setattr(
        "prefect_kubernetes.volcanoworker.CustomObjectsApi",
        MagicMock(return_value=MagicMock(create_namespaced_custom_object=create_job_mock)),
    )

    monkeypatch.setattr(
        VolcanoWorker,
        "_watch_job",
        AsyncMock(return_value=0),
    )

    # _replace_api_key_with_secret does nothing
    monkeypatch.setattr(
        VolcanoWorker,
        "_replace_api_key_with_secret",
        AsyncMock(),
    )

    # get cluster UID ⇒ fixed value
    monkeypatch.setattr(
        VolcanoWorker,
        "_get_cluster_uid",
        AsyncMock(return_value="CLUSTER-UID"),
    )

    async with VolcanoWorker(work_pool_name="dummy-pool") as worker:
        # Need to prepare first or env will be missing
        job_cfg.prepare_for_flow_run(dummy_flow_run)
        res = await worker.run(flow_run=dummy_flow_run, configuration=job_cfg)

    assert res.status_code == 0

    create_job_mock.assert_awaited_once()
    args, kwargs = create_job_mock.await_args
    assert kwargs["group"] == "batch.volcano.sh"
    assert kwargs["version"] == "v1alpha1"

    assert res.identifier == "CLUSTER-UID:default:vc-job-999"
