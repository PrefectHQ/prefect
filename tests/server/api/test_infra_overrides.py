import uuid
from typing import Optional

import pytest

from prefect.server import models, schemas
from prefect.server.models import deployments
from prefect.settings import (
    PREFECT_EXPERIMENTAL_ENABLE_FLOW_RUN_INFRA_OVERRIDES,
    temporary_settings,
)


@pytest.fixture
def enable_infra_overrides():
    with temporary_settings(
        {PREFECT_EXPERIMENTAL_ENABLE_FLOW_RUN_INFRA_OVERRIDES: True}
    ):
        yield


async def create_work_pool(
    session, job_template: dict, type: str = "None"
) -> schemas.core.WorkPool:
    work_pool = await models.workers.create_work_pool(
        session=session,
        work_pool=schemas.actions.WorkPoolCreate.construct(
            _fields_set=schemas.actions.WorkPoolCreate.__fields_set__,
            name="wp-1",
            type=type,
            description="None",
            base_job_template=job_template,
        ),
    )
    await session.commit()
    return work_pool


async def create_deployment(
    session,
    flow: schemas.core.Flow,
    work_pool: schemas.core.WorkPool,
    job_variables: dict,
) -> schemas.core.Deployment:
    deployment = await deployments.create_deployment(
        session=session,
        deployment=schemas.core.Deployment(
            name="My Deployment X",
            flow_id=flow.id,
            paused=False,
            work_queue_id=work_pool.default_queue_id,
            infra_overrides=job_variables,
        ),
    )
    await session.commit()
    return deployment


async def create_flow(session) -> schemas.core.Flow:
    flow = await models.flows.create_flow(
        session=session, flow=schemas.core.Flow(name="my-flow")
    )
    await session.commit()
    assert flow
    return flow


async def create_objects_for_pool(
    session,
    *,
    pool_job_config: Optional[dict] = None,
    deployment_vars: Optional[dict] = None,
    pool_type: str = "None",
):
    pool_job_config = pool_job_config or {}
    deployment_vars = deployment_vars or {}
    flow = await create_flow(session)
    wp = await create_work_pool(session, pool_job_config, type=pool_type)
    deployment = await create_deployment(session, flow, wp, deployment_vars)
    return flow, wp, deployment


class TestInfraOverrides:
    async def test_creating_flow_run_with_unexpected_vars(
        self,
        session,
        client,
        enable_infra_overrides,
    ):
        *_, deployment = await create_objects_for_pool(
            session,
            pool_job_config={
                "job_configuration": {
                    "thing_one": "{{ expected_variable_1 }}",
                    "thing_two": "{{ expected_variable_2 }}",
                },
                "variables": {
                    "properties": {
                        "expected_variable_1": {},
                        "expected_variable_2": {},
                    },
                    "required": ["expected_variable_1", "expected_variable_2"],
                },
            },
        )

        response = await client.post(
            f"/deployments/{deployment.id}/create_flow_run",
            json={"job_variables": {"x": 1}},
        )
        assert response.status_code == 409
        assert (
            response.json()["detail"]
            == "Error creating flow run: Validation failed. Failure reason: 'expected_variable_1' is a required property"
        )

    async def test_creating_flow_run_with_mismatched_var_types(
        self,
        session,
        client,
        enable_infra_overrides,
    ):
        *_, deployment = await create_objects_for_pool(
            session,
            pool_job_config={
                "job_configuration": {
                    "thing_one": "{{ expected_variable_1 }}",
                    "thing_two": "{{ expected_variable_2 }}",
                },
                "variables": {
                    "properties": {
                        "expected_variable_1": {
                            "title": "expected_variable_1",
                            "default": 0,
                            "type": "integer",
                        },
                        "expected_variable_2": {
                            "title": "expected_variable_2",
                            "default": "0",
                            "type": "string",
                        },
                    },
                    "required": ["expected_variable_1", "expected_variable_2"],
                },
            },
        )

        response = await client.post(
            f"/deployments/{deployment.id}/create_flow_run",
            json={
                "job_variables": {"expected_variable_1": 1, "expected_variable_2": 2}
            },
        )
        assert response.status_code == 409
        assert (
            response.json()["detail"]
            == "Error creating flow run: Validation failed for field 'expected_variable_2'. Failure reason: 2 is not of type 'string'"
        )

    @pytest.mark.parametrize(
        "template",
        (
            {},
            None,
            {
                "job_configuration": {
                    "thing_one": "{{ expected_variable_1 }}",
                    "thing_two": "{{ expected_variable_2 }}",
                },
                "variables": {
                    "properties": {
                        "expected_variable_1": {},
                        "expected_variable_2": {},
                    },
                },
            },
        ),
    )
    async def test_creating_flow_run_with_vars_on_non_strict_pool(
        self,
        session,
        client,
        enable_infra_overrides,
        template,
    ):
        # create a pool with a lax schema
        *_, deployment = await create_objects_for_pool(
            session, pool_job_config=template
        )

        # create a flow run with job vars
        job_variables = {"x": 1}
        response = await client.post(
            f"/deployments/{deployment.id}/create_flow_run",
            json={"job_variables": job_variables},
        )
        assert response.status_code == 201

        # verify the flow run was created with the supplied job vars
        flow_run = await models.flow_runs.read_flow_run(
            session=session,
            flow_run_id=response.json()["id"],
        )
        assert flow_run.job_variables == job_variables

    async def test_flow_run_vars_overwrite_deployment_vars(
        self,
        session,
        client,
        enable_infra_overrides,
    ):
        # create a pool with a pool schema and a deployment with variables
        *_, deployment = await create_objects_for_pool(
            session,
            pool_job_config={
                "job_configuration": {
                    "thing_one": "{{ expected_variable_1 }}",
                    "thing_two": "{{ expected_variable_2 }}",
                },
                "variables": {
                    "properties": {
                        "expected_variable_1": {
                            "title": "expected_variable_1",
                            "default": 0,
                            "type": "integer",
                        },
                        "expected_variable_2": {
                            "title": "expected_variable_2",
                            "default": 0,
                            "type": "integer",
                        },
                    },
                    "required": ["expected_variable_1", "expected_variable_2"],
                },
            },
            deployment_vars={"expected_variable_1": 1, "expected_variable_2": 2},
        )

        # create a flow run its own job vars
        job_variables = {"expected_variable_1": -1, "expected_variable_2": -2}
        response = await client.post(
            f"/deployments/{deployment.id}/create_flow_run",
            json={"job_variables": job_variables},
        )
        assert response.status_code == 201

        # verify the flow run vars took precedence over deployment vars
        flow_run = await models.flow_runs.read_flow_run(
            session=session,
            flow_run_id=response.json()["id"],
        )
        assert flow_run.job_variables == job_variables

    async def test_merged_deployment_vars_and_flow_run_vars_are_not_stored(
        self,
        session,
        client,
        enable_infra_overrides,
    ):
        # create a pool with a pool schema and a deployment with overrides
        deployment_vars = {"expected_variable_2": 2}
        *_, deployment = await create_objects_for_pool(
            session,
            pool_job_config={
                "job_configuration": {
                    "thing_one": "{{ expected_variable_1 }}",
                    "thing_two": "{{ expected_variable_2 }}",
                },
                "variables": {
                    "properties": {
                        "expected_variable_1": {
                            "title": "expected_variable_1",
                            "default": 0,
                            "type": "integer",
                        },
                        "expected_variable_2": {
                            "title": "expected_variable_2",
                            "default": 0,
                            "type": "integer",
                        },
                    },
                    "required": ["expected_variable_1", "expected_variable_2"],
                },
            },
            deployment_vars=deployment_vars,
        )

        # create a flow run its own overrides
        job_variables = {"expected_variable_1": -1}
        response = await client.post(
            f"/deployments/{deployment.id}/create_flow_run",
            json={"job_variables": job_variables},
        )
        assert response.status_code == 201

        # verify the flow run overrides are stored unmerged
        flow_run = await models.flow_runs.read_flow_run(
            session=session,
            flow_run_id=response.json()["id"],
        )
        assert flow_run.job_variables == job_variables

    async def test_flow_run_fails_if_missing_default_are_not_provided(
        self,
        session,
        client,
        enable_infra_overrides,
    ):
        # create a pool with a pool schema and a deployment with variables
        *_, deployment = await create_objects_for_pool(
            session,
            pool_job_config={
                "job_configuration": {
                    "thing_one": "{{ expected_variable_1 }}",
                    "thing_two": "{{ expected_variable_2 }}",
                },
                "variables": {
                    "properties": {
                        "expected_variable_1": {
                            "title": "expected_variable_1",
                            "type": "integer",
                        },
                    },
                    "required": ["expected_variable_1"],
                },
            },
        )

        # create a flow run that should fail bc no override is provided
        response = await client.post(
            f"/deployments/{deployment.id}/create_flow_run",
            json={},
        )

        # verify the flow run failed due to a missing required variable
        assert response.status_code == 409
        assert response.json()["detail"] == (
            "Error creating flow run: Validation failed. Failure reason: 'expected_variable_1' is a required property"
        )

    async def test_flow_run_with_base_job_template_defaults(
        self,
        session,
        client,
        enable_infra_overrides,
    ):
        # create a pool with a pool schema that has a default value
        *_, deployment = await create_objects_for_pool(
            session,
            pool_job_config={
                "job_configuration": {
                    "thing_one": "{{ expected_variable_1 }}",
                    "thing_two": "{{ expected_variable_2 }}",
                },
                "variables": {
                    "properties": {
                        "expected_variable_1": {
                            "title": "expected_variable_1",
                            "default": 0,
                            "type": "integer",
                        },
                    },
                    "required": ["expected_variable_1"],
                },
            },
        )

        # create a flow run has no overrides
        response = await client.post(
            f"/deployments/{deployment.id}/create_flow_run", json={}
        )

        # verify validation passed since the job templates's default was used
        assert response.status_code == 201


class TestInfraOverridesUpdates:
    async def test_updating_flow_run_with_valid_updates(
        self,
        session,
        client,
        enable_infra_overrides,
    ):
        # create a pool with a pool schema that has a default value
        *_, deployment = await create_objects_for_pool(
            session,
            pool_job_config={
                "job_configuration": {
                    "thing_one": "{{ expected_variable_1 }}",
                },
                "variables": {
                    "properties": {
                        "expected_variable_1": {
                            "title": "expected_variable_1",
                            "default": 0,
                            "type": "integer",
                        },
                    },
                    "required": ["expected_variable_1"],
                },
            },
        )

        # create a flow run with no overrides
        response = await client.post(
            f"/deployments/{deployment.id}/create_flow_run", json={}
        )
        assert response.status_code == 201
        flow_run_id = response.json()["id"]

        # update the flow run with new job vars
        job_variables = {"expected_variable_1": 100}
        response = await client.patch(
            f"/flow_runs/{flow_run_id}", json={"job_variables": job_variables}
        )
        assert response.status_code == 204

        # verify that updates were applied
        flow_run = await models.flow_runs.read_flow_run(
            session=session, flow_run_id=flow_run_id
        )
        assert flow_run.job_variables == job_variables

    async def test_updating_flow_run_with_invalid_update_type(
        self,
        session,
        client,
        enable_infra_overrides,
    ):
        # create a pool with a pool schema that has a default value
        *_, deployment = await create_objects_for_pool(
            session,
            pool_job_config={
                "job_configuration": {
                    "thing_one": "{{ expected_variable_1 }}",
                },
                "variables": {
                    "properties": {
                        "expected_variable_1": {
                            "title": "expected_variable_1",
                            "default": 0,
                            "type": "integer",
                        },
                    },
                    "required": ["expected_variable_1"],
                },
            },
        )

        # create a flow run with no overrides
        response = await client.post(
            f"/deployments/{deployment.id}/create_flow_run", json={}
        )
        assert response.status_code == 201
        flow_run_id = response.json()["id"]

        # update the flow run with a job var that doesn't conform to the schema
        job_variables = {"expected_variable_1": "this_should_be_an_int"}
        response = await client.patch(
            f"/flow_runs/{flow_run_id}", json={"job_variables": job_variables}
        )

        # verify that the update failed
        assert response.status_code == 409
        assert (
            response.json()["detail"]
            == "Error updating flow run: Validation failed for field 'expected_variable_1'. Failure reason: 'this_should_be_an_int' is not of type 'integer'"
        )

        flow_run = await models.flow_runs.read_flow_run(
            session=session, flow_run_id=flow_run_id
        )
        assert flow_run.job_variables == {}

    async def test_updating_flow_run_in_non_scheduled_state(
        self,
        session,
        client,
        db,
        enable_infra_overrides,
    ):
        # create a pool with a pool schema that has a default value
        *_, deployment = await create_objects_for_pool(
            session,
            pool_job_config={
                "job_configuration": {
                    "thing_one": "{{ expected_variable_1 }}",
                },
                "variables": {
                    "properties": {
                        "expected_variable_1": {
                            "title": "expected_variable_1",
                            "default": 0,
                            "type": "integer",
                        },
                    },
                    "required": ["expected_variable_1"],
                },
            },
        )

        # create a flow run
        original_job_variables = {"expected_variable_1": 1}
        response = await client.post(
            f"/deployments/{deployment.id}/create_flow_run",
            json={"job_variables": original_job_variables},
        )
        assert response.status_code == 201
        flow_run_id = response.json()["id"]

        # set the flow run state to be non-scheduled
        flow_run = await models.flow_runs.read_flow_run(
            session=session,
            flow_run_id=flow_run_id,
        )
        flow_run.set_state(db.FlowRunState(**schemas.states.Pending().orm_dict()))
        await session.commit()

        # attempt to update the flow run
        job_variables = {"expected_variable_1": 100}
        response = await client.patch(
            f"/flow_runs/{flow_run_id}", json={"job_variables": job_variables}
        )

        # verify that the update failed
        assert response.status_code == 400
        assert (
            response.json()["detail"]
            == "Job variables for a flow run in state PENDING cannot be updated"
        )

        flow_run = await models.flow_runs.read_flow_run(
            session=session, flow_run_id=flow_run_id
        )
        assert flow_run.job_variables == original_job_variables

    async def test_updating_non_existant_flow_run(
        self,
        client,
        enable_infra_overrides,
    ):
        # update a non-existent flow run
        response = await client.patch(
            f"/flow_runs/{uuid.uuid4()}", json={"job_variables": {"foo": "bar"}}
        )

        # verify the update failed
        assert response.status_code == 404
        assert response.json()["detail"] == "Flow run not found"
