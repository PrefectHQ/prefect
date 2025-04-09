from uuid import uuid4

import pydantic
import pytest
from httpx import AsyncClient
from starlette import status

from prefect.server import models, schemas
from prefect.server.database.orm_models import Deployment, Flow
from prefect.server.schemas import actions
from prefect.types._datetime import now
from prefect.utilities.pydantic import parse_obj_as


@pytest.fixture
async def artifact(flow_run, task_run, client):
    artifact_schema = actions.ArtifactCreate(
        key="voltaic",
        data=1,
        description="# This is a markdown description title",
        metadata_={"data": "opens many doors"},
        flow_run_id=flow_run.id,
        task_run_id=task_run.id,
    )
    response = await client.post(
        "/artifacts/", json=artifact_schema.model_dump(mode="json")
    )
    assert response.status_code == status.HTTP_201_CREATED

    yield response.json()


@pytest.fixture
async def artifacts(flow_run, task_run, client):
    artifact1_schema = actions.ArtifactCreate(
        key="artifact-1",
        data=1,
        description="# This is a markdown description title",
        flow_run_id=flow_run.id,
        task_run_id=task_run.id,
        type="table",
    ).model_dump(mode="json")
    artifact1 = await client.post("/artifacts/", json=artifact1_schema)

    artifact2_schema = actions.ArtifactCreate(
        key="artifact-2",
        description="# This is a markdown description title",
        data=2,
        flow_run_id=flow_run.id,
        task_run_id=uuid4(),
        type="markdown",
    ).model_dump(mode="json")
    artifact2 = await client.post("/artifacts/", json=artifact2_schema)

    artifact3_schema = actions.ArtifactCreate(
        key="artifact-3",
        description="# This is a markdown description title",
        flow_run_id=uuid4(),
        task_run_id=uuid4(),
        type="result",
    ).model_dump(mode="json")
    artifact3 = await client.post("/artifacts/", json=artifact3_schema)

    artifact4_schema = actions.ArtifactCreate(
        key="artifact-4",
        description="# This is a markdown description title",
    ).model_dump(mode="json")
    artifact4 = await client.post("/artifacts/", json=artifact4_schema)

    artifact5_schema = actions.ArtifactCreate(
        data=1,
        description="# This is a markdown description title",
    ).model_dump(mode="json")
    artifact5 = await client.post("/artifacts/", json=artifact5_schema)

    yield [
        artifact1.json(),
        artifact2.json(),
        artifact3.json(),
        artifact4.json(),
        artifact5.json(),
    ]


@pytest.fixture
async def flow_artifacts(client: AsyncClient, flow: Flow, deployment: Deployment):
    flow_data = {"name": flow.name}
    response = await client.post("/flows/", json=flow_data)

    flow = response.json()

    response = await client.post(
        f"deployments/{deployment.id}/create_flow_run", json={}
    )

    flow_run = response.json()

    artifact1_schema = actions.ArtifactCreate(
        key="artifact-1",
        data=1,
        description="# This is a markdown description title",
        flow_run_id=flow_run["id"],
        type="table",
    ).model_dump(mode="json")
    artifact1 = await client.post("/artifacts/", json=artifact1_schema)

    artifact2_schema = actions.ArtifactCreate(
        key="artifact-1",
        data=1,
        description="# This is a markdown description title",
        flow_run_id=flow_run["id"],
        type="table",
    ).model_dump(mode="json")
    artifact2 = await client.post("/artifacts/", json=artifact2_schema)

    return [flow, artifact1.json(), artifact2.json(), deployment.id]


class TestCreateArtifact:
    async def test_create_artifact(self, flow_run, task_run, client):
        artifact = actions.ArtifactCreate(
            key="voltaic",
            data=1,
            description="# This is a markdown description title",
            metadata_={"data": "opens many doors"},
            flow_run_id=flow_run.id,
            task_run_id=task_run.id,
        ).model_dump(mode="json")

        response = await client.post(
            "/artifacts/",
            json=artifact,
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert response.json()["key"] == artifact["key"]
        assert response.json()["data"] == artifact["data"]
        assert response.json()["description"] == artifact["description"]
        assert response.json()["metadata_"] == artifact["metadata_"]
        assert response.json()["flow_run_id"] == str(flow_run.id)
        assert response.json()["task_run_id"] == str(task_run.id)

    async def test_create_artifact_with_existing_key_succeeds(
        self,
        artifact,
        client,
    ):
        data = actions.ArtifactCreate(
            key=artifact["key"],
            data=artifact["data"],
        ).model_dump(mode="json")

        response = await client.post(
            "/artifacts/",
            json=data,
        )

        assert response.status_code == 201

    async def test_create_camel_case_artifact_key_raises(
        self,
    ):
        with pytest.raises(
            pydantic.ValidationError,
            match="key must only contain lowercase letters, numbers, and dashes",
        ):
            schemas.actions.ArtifactCreate(
                key="camelCase_Key",
                data=1,
            ).model_dump(mode="json")


class TestReadArtifact:
    async def test_read_artifact(self, artifact, client):
        artifact_id = artifact["id"]

        response = await client.get(f"/artifacts/{artifact_id}")
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["key"] == artifact["key"]
        assert response.json()["data"] == artifact["data"]
        assert response.json()["description"] == artifact["description"]
        assert response.json()["metadata_"] == artifact["metadata_"]
        assert response.json()["flow_run_id"] == artifact["flow_run_id"]

    async def test_read_artifact_not_found(self, client):
        response = await client.get(f"/artifacts/{uuid4()}")
        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestReadLatestArtifact:
    async def test_read_latest_artifact(self, artifact, client):
        response = await client.get(f"/artifacts/{artifact['key']}/latest")
        artifact_result = response.json()
        assert response.status_code == status.HTTP_200_OK
        assert artifact_result["key"] == artifact["key"]
        assert artifact_result["data"] == artifact["data"]
        assert artifact_result["description"] == artifact["description"]
        assert artifact_result["metadata_"] == artifact["metadata_"]
        assert artifact_result["flow_run_id"] == artifact["flow_run_id"]


class TestReadArtifacts:
    async def test_read_artifacts(self, artifacts, client):
        response = await client.post("/artifacts/filter")
        assert response.status_code == status.HTTP_200_OK
        assert len(response.json()) == len(artifacts)

        assert {r["key"] for r in response.json()} == {a["key"] for a in artifacts}
        assert {r["data"] for r in response.json()} == {a["data"] for a in artifacts}
        assert {r["description"] for r in response.json()} == {
            a["description"] for a in artifacts
        }
        assert {r["flow_run_id"] for r in response.json()} == {
            a["flow_run_id"] for a in artifacts
        }

    async def test_read_artifacts_with_artifact_key_filter_any(self, artifacts, client):
        artifact_filter = dict(
            artifacts=schemas.filters.ArtifactFilter(
                key=schemas.filters.ArtifactFilterKey(
                    any_=[artifacts[0]["key"], artifacts[1]["key"]]
                )
            ).model_dump(mode="json")
        )
        response = await client.post("/artifacts/filter", json=artifact_filter)
        assert response.status_code == status.HTTP_200_OK
        assert len(response.json()) == 2
        assert {r["key"] for r in response.json()} == {
            artifacts[0]["key"],
            artifacts[1]["key"],
        }

    async def test_read_artifact_with_artifact_key_filter_exists(
        self, artifacts, client
    ):
        artifact_filter = dict(
            artifacts=schemas.filters.ArtifactFilter(
                key=schemas.filters.ArtifactFilterKey(exists_=True)
            ).model_dump(mode="json")
        )
        response = await client.post("/artifacts/filter", json=artifact_filter)
        assert response.status_code == status.HTTP_200_OK
        assert len(response.json()) == len(artifacts) - 1
        assert all(r["key"] for r in response.json())

    async def test_read_artifact_with_artifact_key_filter_not_exists(
        self, artifacts, client
    ):
        artifact_filter = dict(
            artifacts=schemas.filters.ArtifactFilter(
                key=schemas.filters.ArtifactFilterKey(exists_=False)
            ).model_dump(mode="json")
        )
        response = await client.post("/artifacts/filter", json=artifact_filter)
        assert response.status_code == status.HTTP_200_OK
        assert len(response.json()) == 1
        assert response.json()[0]["key"] is None

    async def test_read_artifacts_with_artifact_id_filter(self, artifacts, client):
        artifact_id = artifacts[0]["id"]

        artifact_filter = dict(
            artifacts=schemas.filters.ArtifactFilter(
                id=schemas.filters.ArtifactFilterId(any_=[artifact_id])
            ).model_dump(mode="json")
        )
        response = await client.post("/artifacts/filter", json=artifact_filter)
        assert response.status_code == status.HTTP_200_OK
        assert len(response.json()) == 1

    async def test_read_artifacts_with_artifact_flow_run_id_filter(
        self, artifacts, client
    ):
        flow_run_id = artifacts[0]["flow_run_id"]
        flow_run_filter = dict(
            artifacts=schemas.filters.ArtifactFilter(
                flow_run_id=schemas.filters.ArtifactFilterFlowRunId(any_=[flow_run_id])
            ).model_dump(mode="json")
        )
        response = await client.post("/artifacts/filter", json=flow_run_filter)
        assert response.status_code == status.HTTP_200_OK
        assert len(response.json()) == 2
        assert all(
            [item["flow_run_id"] == str(flow_run_id) for item in response.json()]
        )

    async def test_read_artifacts_with_artifact_task_run_id_filter(
        self, artifacts, client
    ):
        task_run_id = artifacts[0]["task_run_id"]
        task_run_filter = dict(
            artifacts=schemas.filters.ArtifactFilter(
                task_run_id=schemas.filters.ArtifactFilterTaskRunId(any_=[task_run_id])
            ).model_dump(mode="json")
        )
        response = await client.post("/artifacts/filter", json=task_run_filter)
        assert response.status_code == status.HTTP_200_OK
        assert len(response.json()) == 1
        assert all(
            [item["task_run_id"] == str(task_run_id) for item in response.json()]
        )

    async def test_read_artifacts_with_artifact_type_filter_any(
        self, artifacts, client
    ):
        artifact_type = artifacts[1]["type"]
        artifact_type_filter = dict(
            artifacts=schemas.filters.ArtifactFilter(
                type=schemas.filters.ArtifactFilterType(any_=[artifact_type])
            ).model_dump(mode="json")
        )
        response = await client.post("/artifacts/filter", json=artifact_type_filter)
        assert response.status_code == status.HTTP_200_OK
        assert len(response.json()) == 1
        assert response.json()[0]["type"] == artifact_type

    async def test_read_artifacts_with_artifact_type_filter_not_any(
        self, artifacts, client
    ):
        artifact_type = artifacts[2]["type"]
        artifact_type_filter = dict(
            artifacts=schemas.filters.ArtifactFilter(
                type=schemas.filters.ArtifactFilterType(not_any_=[artifact_type])
            ).model_dump(mode="json")
        )
        response = await client.post("/artifacts/filter", json=artifact_type_filter)
        assert response.status_code == status.HTTP_200_OK
        assert len(response.json()) == 2
        assert all([item["type"] != artifact_type for item in response.json()])

    async def test_read_artifacts_with_multiple_filters(
        self, artifacts, flow_run, task_run, client
    ):
        multiple_filters = dict(
            artifacts=schemas.filters.ArtifactFilter(
                flow_run_id=schemas.filters.ArtifactFilterFlowRunId(any_=[flow_run.id]),
                task_run_id=schemas.filters.ArtifactFilterTaskRunId(any_=[task_run.id]),
            ).model_dump(mode="json"),
        )
        response = await client.post("/artifacts/filter", json=multiple_filters)
        assert response.status_code == status.HTTP_200_OK
        assert len(response.json()) == 1
        assert all(
            [item["flow_run_id"] == str(flow_run.id) for item in response.json()]
        )
        assert all(
            [item["task_run_id"] == str(task_run.id) for item in response.json()]
        )

    async def test_read_artifacts_with_flow_run_filter(self, artifacts, client):
        flow_run_id = artifacts[0]["flow_run_id"]
        flow_run_filter = dict(
            flow_runs=schemas.filters.FlowRunFilter(
                id=schemas.filters.FlowRunFilterId(any_=[flow_run_id])
            ).model_dump(mode="json")
        )
        response = await client.post("/artifacts/filter", json=flow_run_filter)
        assert response.status_code == status.HTTP_200_OK
        assert len(response.json()) == 2
        assert all(
            [item["flow_run_id"] == str(flow_run_id) for item in response.json()]
        )

    async def test_read_artifacts_with_task_run_filter(self, artifacts, client):
        task_run_id = artifacts[0]["task_run_id"]
        task_run_filter = dict(
            task_runs=schemas.filters.TaskRunFilter(
                id=schemas.filters.TaskRunFilterId(any_=[task_run_id])
            ).model_dump(mode="json")
        )
        response = await client.post("/artifacts/filter", json=task_run_filter)
        assert response.status_code == status.HTTP_200_OK
        assert len(response.json()) == 1
        assert all(
            [item["task_run_id"] == str(task_run_id) for item in response.json()]
        )

    async def test_read_artifacts_with_limit(self, artifacts, client):
        response = await client.post("/artifacts/filter", json={"limit": 1})
        assert response.status_code == status.HTTP_200_OK
        assert len(response.json()) == 1

    async def test_read_artifacts_with_offset(self, artifacts, client):
        response = await client.post(
            "/artifacts/filter",
            json={
                "offset": 1,
                "sort": schemas.sorting.ArtifactSort.CREATED_DESC,
            },
        )
        assert response.status_code == status.HTTP_200_OK
        assert len(response.json()) == len(artifacts) - 1
        actual_keys = [item["key"] for item in response.json()]
        expected_keys = [item["key"] for item in artifacts[:-1]]
        assert set(actual_keys) == set(expected_keys)

    async def test_read_artifacts_with_sort(self, artifacts, client):
        response = await client.post(
            "/artifacts/filter",
            json=dict(sort=schemas.sorting.ArtifactSort.UPDATED_DESC),
        )
        assert response.status_code == status.HTTP_200_OK
        assert len(response.json()) == len(artifacts)
        # assert they are sorted correctly
        assert all(
            [
                response.json()[i]["updated"] >= response.json()[i + 1]["updated"]
                for i in range(len(response.json()) - 1)
            ]
        )

    async def test_read_artifacts_returns_empty_list(self, client):
        response = await client.post("/artifacts/filter")
        assert response.status_code == status.HTTP_200_OK
        assert len(response.json()) == 0

    async def test_read_artifacts_with_applies_key_like_filter(self, artifacts, client):
        like_first_key = artifacts[0]["key"][-1]

        artifact_filter = dict(
            artifacts=schemas.filters.ArtifactFilter(
                key=schemas.filters.ArtifactFilterKey(like_=like_first_key)
            ).model_dump(mode="json")
        )
        response = await client.post("/artifacts/filter", json=artifact_filter)
        assert response.status_code == status.HTTP_200_OK
        assert len(response.json()) == 1
        assert response.json()[0]["key"] == artifacts[0]["key"]

    async def test_reading_artifacts_by_flow_name(self, flow_artifacts, client):
        flow_name = flow_artifacts[0]["name"]
        flow_filter = dict(
            flows=schemas.filters.FlowFilter(
                name=schemas.filters.FlowFilterName(any_=[flow_name])
            ).model_dump(mode="json")
        )
        response = await client.post("/artifacts/filter", json=flow_filter)
        assert response.status_code == status.HTTP_200_OK
        json = response.json()
        assert len(json) == 2
        assert sorted([json[0]["id"], json[1]["id"]]) == sorted(
            [flow_artifacts[1]["id"], flow_artifacts[2]["id"]]
        )

    async def test_reading_artifacts_by_deployment(self, flow_artifacts, client):
        deployment_id = flow_artifacts[3]
        deployment_filter = dict(
            deployments=schemas.filters.DeploymentFilter(
                id=schemas.filters.DeploymentFilterId(any_=[deployment_id])
            ).model_dump(mode="json")
        )
        response = await client.post("/artifacts/filter", json=deployment_filter)
        assert response.status_code == status.HTTP_200_OK
        json = response.json()
        assert len(json) == 2
        assert sorted([json[0]["id"], json[1]["id"]]) == sorted(
            [flow_artifacts[1]["id"], flow_artifacts[2]["id"]]
        )


class TestReadLatestArtifacts:
    @pytest.fixture
    async def artifacts(self, client, flow_run, task_run):
        artifact1_schema = actions.ArtifactCreate(
            key="artifact-1",
            data=1,
            flow_run_id=flow_run.id,
            description="# This is a markdown description title",
            type="table",
        ).model_dump(mode="json")
        artifact1 = await client.post("/artifacts/", json=artifact1_schema)

        artifact2_schema = actions.ArtifactCreate(
            key="artifact-1",
            description="# This is a markdown description title",
            flow_run_id=flow_run.id,
            data=2,
            type="table",
        ).model_dump(mode="json")
        artifact2 = await client.post("/artifacts/", json=artifact2_schema)

        artifact3_schema = actions.ArtifactCreate(
            key="artifact-3",
            description="# This is a markdown description title",
            flow_run_id=flow_run.id,
            task_run_id=task_run.id,
            data=3,
            type="result",
        ).model_dump(mode="json")
        artifact3 = await client.post("/artifacts/", json=artifact3_schema)

        artifact4_schema = actions.ArtifactCreate(
            data=1,
            type="markdown",
            description="# This is a markdown description title",
        ).model_dump(mode="json")
        artifact4 = await client.post("/artifacts/", json=artifact4_schema)

        yield [
            artifact1.json(),
            artifact2.json(),
            artifact3.json(),
            artifact4.json(),
        ]

    async def test_read_latest_artifacts(self, artifacts, client):
        latest_filter = dict(
            artifacts=schemas.filters.ArtifactCollectionFilter().model_dump(
                mode="json"
            ),
        )

        response = await client.post("/artifacts/latest/filter", json=latest_filter)
        assert response.status_code == 200
        assert len(response.json()) == 2
        keyed_data = {(r["key"], r["data"]) for r in response.json()}
        assert keyed_data == {
            ("artifact-1", 2),
            ("artifact-3", 3),
        }

    async def test_read_latest_artifacts_with_artifact_type_filter(
        self, artifacts, client
    ):
        latest_filter_table_type = dict(
            artifacts=schemas.filters.ArtifactCollectionFilter(
                type=schemas.filters.ArtifactCollectionFilterType(any_=["table"]),
            ).model_dump(mode="json"),
        )
        response = await client.post(
            "/artifacts/latest/filter", json=latest_filter_table_type
        )

        assert response.status_code == 200
        assert len(response.json()) == 1

    async def test_read_latest_artifacts_with_artifact_key_filter(
        self, artifacts, client
    ):
        latest_filter_key = dict(
            artifacts=schemas.filters.ArtifactCollectionFilter(
                key=schemas.filters.ArtifactCollectionFilterKey(any_=["artifact-1"]),
            ).model_dump(mode="json"),
        )

        response = await client.post("/artifacts/latest/filter", json=latest_filter_key)
        assert response.status_code == 200
        assert len(response.json()) == 1
        assert response.json()[0]["key"] == "artifact-1"
        assert response.json()[0]["data"] == 2

    async def test_read_latest_artifact_with_limit(self, artifacts, client):
        latest_filter_limit = {"limit": 2}

        response = await client.post(
            "/artifacts/latest/filter", json=latest_filter_limit
        )

        assert response.status_code == 200
        assert len(response.json()) == 2

    async def test_read_artifacts_with_flow_run_filter(self, artifacts, client):
        flow_run_id = artifacts[0]["flow_run_id"]
        flow_run_filter = dict(
            flow_runs=schemas.filters.FlowRunFilter(
                id=schemas.filters.FlowRunFilterId(any_=[flow_run_id])
            ).model_dump(mode="json")
        )
        response = await client.post("/artifacts/latest/filter", json=flow_run_filter)
        assert response.status_code == status.HTTP_200_OK
        assert len(response.json()) == 2
        assert all(
            [item["flow_run_id"] == str(flow_run_id) for item in response.json()]
        )

    async def test_read_artifacts_with_task_run_filter(self, artifacts, client):
        task_run_id = artifacts[2]["task_run_id"]
        task_run_filter = dict(
            task_runs=schemas.filters.TaskRunFilter(
                id=schemas.filters.TaskRunFilterId(any_=[task_run_id])
            ).model_dump(mode="json")
        )
        response = await client.post("/artifacts/latest/filter", json=task_run_filter)
        assert response.status_code == status.HTTP_200_OK
        assert len(response.json()) == 1
        assert all(
            [item["task_run_id"] == str(task_run_id) for item in response.json()]
        )

    async def test_read_artifacts_returns_empty_list(self, client):
        response = await client.post("/artifacts/latest/filter")
        assert response.status_code == status.HTTP_200_OK
        assert len(response.json()) == 0

    async def test_read_artifacts_with_artifact_flow_run_id_filter(
        self, artifacts, client
    ):
        flow_run_id = artifacts[0]["flow_run_id"]
        flow_run_filter = dict(
            artifacts=schemas.filters.ArtifactCollectionFilter(
                flow_run_id=schemas.filters.ArtifactCollectionFilterFlowRunId(
                    any_=[flow_run_id]
                )
            ).model_dump(mode="json")
        )
        response = await client.post("/artifacts/latest/filter", json=flow_run_filter)
        assert response.status_code == status.HTTP_200_OK
        assert len(response.json()) == 2
        assert all(
            [item["flow_run_id"] == str(flow_run_id) for item in response.json()]
        )

    async def test_read_artifacts_with_artifact_task_run_id_filter(
        self, artifacts, client
    ):
        task_run_id = artifacts[2]["task_run_id"]
        task_run_filter = dict(
            artifacts=schemas.filters.ArtifactCollectionFilter(
                task_run_id=schemas.filters.ArtifactCollectionFilterTaskRunId(
                    any_=[task_run_id]
                )
            ).model_dump(mode="json")
        )
        response = await client.post("/artifacts/latest/filter", json=task_run_filter)
        assert response.status_code == status.HTTP_200_OK
        assert len(response.json()) == 1
        assert all(
            [item["task_run_id"] == str(task_run_id) for item in response.json()]
        )

    async def test_reading_latest_artifacts_by_flow_name(self, flow_artifacts, client):
        flow_name = flow_artifacts[0]["name"]
        flow_filter = dict(
            flows=schemas.filters.FlowFilter(
                name=schemas.filters.FlowFilterName(any_=[flow_name])
            ).model_dump(mode="json")
        )
        response = await client.post("/artifacts/latest/filter", json=flow_filter)
        assert response.status_code == status.HTTP_200_OK
        json = response.json()
        assert len(json) == 1
        assert json[0]["latest_id"] == flow_artifacts[2]["id"]

    async def test_reading_latest_artifacts_by_deployment(self, flow_artifacts, client):
        deployment_id = flow_artifacts[3]
        deployment_filter = dict(
            deployments=schemas.filters.DeploymentFilter(
                id=schemas.filters.DeploymentFilterId(any_=[deployment_id])
            ).model_dump(mode="json")
        )
        response = await client.post("/artifacts/latest/filter", json=deployment_filter)
        assert response.status_code == status.HTTP_200_OK
        json = response.json()
        assert len(json) == 1
        assert json[0]["latest_id"] == flow_artifacts[2]["id"]


class TestCountArtifacts:
    async def test_counting_artifacts(self, artifacts, session):
        count = await models.artifacts.count_artifacts(session=session)

        assert count == 5

    async def test_counting_single_artifact(self, artifact, session):
        count = await models.artifacts.count_artifacts(session=session)

        assert count == 1

    async def test_count_artifacts_with_artifact_filter(self, artifacts, client):
        key_filter = dict(
            artifacts=schemas.filters.ArtifactFilter(
                key=schemas.filters.ArtifactFilterKey(
                    any_=[artifacts[0]["key"], artifacts[1]["key"]]
                )
            ).model_dump(mode="json"),
        )

        response = await client.post("/artifacts/count", json=key_filter)
        assert response.status_code == 200
        assert response.json() == 2

    async def test_count_artifacts_with_flow_run_filter(self, artifacts, client):
        flow_run_filter = dict(
            flow_runs=schemas.filters.FlowRunFilter(
                id=schemas.filters.FlowRunFilterId(any_=[artifacts[0]["flow_run_id"]])
            ).model_dump(mode="json"),
        )

        response = await client.post("/artifacts/count", json=flow_run_filter)
        assert response.status_code == 200
        assert response.json() == 2

    async def test_count_artifacts_with_task_run_filter(
        self,
        artifacts,
        client,
    ):
        task_run_filter = dict(
            task_runs=schemas.filters.TaskRunFilter(
                id=schemas.filters.TaskRunFilterId(any_=[artifacts[0]["task_run_id"]])
            ).model_dump(mode="json"),
        )

        response = await client.post("/artifacts/count", json=task_run_filter)

        assert response.status_code == 200
        assert response.json() == 1

    async def test_count_artifacts_by_flow_name(self, flow_artifacts, client):
        flow_name = flow_artifacts[0]["name"]
        flow_filter = dict(
            flows=schemas.filters.FlowFilter(
                name=schemas.filters.FlowFilterName(any_=[flow_name])
            ).model_dump(mode="json")
        )
        response = await client.post("/artifacts/count", json=flow_filter)
        assert response.status_code == status.HTTP_200_OK
        json = response.json()
        assert json == 2

    async def test_count_artifacts_by_deployment(self, flow_artifacts, client):
        deployment_id = flow_artifacts[3]
        deployment_filter = dict(
            deployments=schemas.filters.DeploymentFilter(
                id=schemas.filters.DeploymentFilterId(any_=[deployment_id])
            ).model_dump(mode="json")
        )
        response = await client.post("/artifacts/count", json=deployment_filter)
        assert response.status_code == status.HTTP_200_OK
        json = response.json()
        assert json == 2

    async def test_counting_latest_artifacts_by_flow_name(self, flow_artifacts, client):
        flow_name = flow_artifacts[0]["name"]
        flow_filter = dict(
            flows=schemas.filters.FlowFilter(
                name=schemas.filters.FlowFilterName(any_=[flow_name])
            ).model_dump(mode="json")
        )
        response = await client.post("/artifacts/latest/count", json=flow_filter)
        assert response.status_code == status.HTTP_200_OK
        json = response.json()
        assert json == 1

    async def test_counting_latest_artifacts_by_deployment(
        self, flow_artifacts, client
    ):
        deployment_id = flow_artifacts[3]
        deployment_filter = dict(
            deployments=schemas.filters.DeploymentFilter(
                id=schemas.filters.DeploymentFilterId(any_=[deployment_id])
            ).model_dump(mode="json")
        )
        response = await client.post("/artifacts/latest/count", json=deployment_filter)
        assert response.status_code == status.HTTP_200_OK
        json = response.json()
        assert json == 1


class TestUpdateArtifact:
    async def test_update_artifact_succeeds(self, artifact, client):
        response = await client.post("/artifacts/filter")
        current_time = now("UTC")
        assert response.status_code == status.HTTP_200_OK
        artifact_id = response.json()[0]["id"]
        artifact_key = response.json()[0]["key"]
        artifact_flow_run_id = response.json()[0]["flow_run_id"]

        response = await client.patch(
            f"/artifacts/{artifact_id}",
            json={"data": {"new": "data"}},
        )

        assert response.status_code == 204

        response = await client.get(f"/artifacts/{artifact_id}")
        updated_artifact = parse_obj_as(schemas.core.Artifact, response.json())
        assert updated_artifact.data == {"new": "data"}
        assert updated_artifact.key == artifact_key
        assert str(updated_artifact.flow_run_id) == artifact_flow_run_id
        assert updated_artifact.created < current_time
        assert updated_artifact.updated > current_time

    async def test_update_artifact_does_not_update_if_fields_are_not_set(
        self, artifact, client
    ):
        current_time = now("UTC")
        artifact_id = artifact["id"]

        response = await client.patch(
            f"/artifacts/{artifact_id}",
            json={},
        )
        assert response.status_code == 204

        response = await client.get(f"/artifacts/{artifact_id}")
        updated_artifact = parse_obj_as(schemas.core.Artifact, response.json())
        assert updated_artifact.data == artifact["data"]
        assert updated_artifact.key == artifact["key"]
        assert str(updated_artifact.flow_run_id) == artifact["flow_run_id"]
        assert updated_artifact.created < current_time
        assert updated_artifact.updated > current_time

    async def test_update_artifact_raises_error_if_artifact_not_found(
        self, artifacts, client
    ):
        response = await client.patch(
            f"/artifacts/{str(uuid4())}",
            json={"data": {"new": "data"}},
        )

        assert response.status_code == 404


class TestDeleteArtifact:
    async def test_delete_artifact_succeeds(self, artifact, session, client):
        artifact_id = artifact["id"]
        artifact_key = artifact["key"]
        response = await client.delete(f"/artifacts/{artifact_id}")
        assert response.status_code == 204

        artifact = await models.artifacts.read_artifact(
            session=session, artifact_id=artifact_id
        )
        assert artifact is None

        assert not await models.artifacts.read_latest_artifact(
            session=session,
            key=artifact_key,
        )

        response = await client.get(f"/artifacts/{artifact_id}")
        assert response.status_code == 404

    async def test_delete_artifact_returns_404_if_does_not_exist(self, client):
        response = await client.delete(f"/artifacts/{str(uuid4())}")
        assert response.status_code == 404
