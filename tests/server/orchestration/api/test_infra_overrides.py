import uuid
from typing import Any, Dict, Optional

import pytest

from prefect.blocks.core import Block
from prefect.server import models, schemas
from prefect.server.models import deployments


class MockKubernetesClusterConfig(Block):
    context_name: str
    config: Dict[str, Any]


@pytest.fixture
async def k8s_credentials():
    block = MockKubernetesClusterConfig(context_name="default", config={})
    await block.save("k8s-credentials")
    return block


async def create_work_pool(
    session, job_template: dict, type: str = "None"
) -> schemas.core.WorkPool:
    work_pool = await models.workers.create_work_pool(
        session=session,
        work_pool=schemas.actions.WorkPoolCreate.model_construct(
            _fields_set=schemas.actions.WorkPoolCreate.model_fields_set,
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
    job_variables: Dict[str, Any],
) -> schemas.core.Deployment:
    deployment = await deployments.create_deployment(
        session=session,
        deployment=schemas.core.Deployment(
            name="My Deployment X",
            flow_id=flow.id,
            paused=False,
            work_queue_id=work_pool.default_queue_id,
            job_variables=job_variables,
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
                    "additionalProperties": False,
                },
            },
        )

        response = await client.post(
            f"/deployments/{deployment.id}/create_flow_run",
            json={"job_variables": {"x": 1}},
        )
        assert response.status_code == 422
        assert (
            response.json()["detail"]
            == "Error creating flow run: Validation failed. Failure reason: 'expected_variable_1' is a required property"
        )

    async def test_creating_flow_run_with_mismatched_var_types(
        self,
        session,
        client,
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
        assert response.status_code == 422
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
        assert response.status_code == 422
        assert response.json()["detail"] == (
            "Error creating flow run: Validation failed. Failure reason: 'expected_variable_1' is a required property"
        )

    async def test_flow_run_with_base_job_template_defaults(
        self,
        session,
        client,
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

    @pytest.mark.parametrize("job_variables", [{}, None, {"x": "y"}])
    async def test_creating_flow_run_with_missing_work_queue(
        self,
        session,
        client,
        job_variables,
    ):
        """
        This test simulates a scenario where the deployment being run is a Runner's deployment
        """

        # create a pool with a pool schema that has a default value
        _, pool, deployment = await create_objects_for_pool(session)

        # delete the deployment's work queue + work pool
        deleted = await models.workers.delete_work_pool(session, pool.id)
        assert deleted

        await session.commit()

        # create a flow run
        response = await client.post(
            f"/deployments/{deployment.id}/create_flow_run",
            json={"job_variables": job_variables},
        )

        # verify we were able to successfully create the run
        assert response.status_code == 201

    async def test_base_job_template_default_references_to_blocks(
        self,
        session,
        hosted_api_client,
        k8s_credentials,
    ):
        # create a pool with a pool schema that has a default value referencing a block
        *_, deployment = await create_objects_for_pool(
            session,
            pool_job_config={
                "variables": {
                    "type": "object",
                    "required": ["k8s_credentials"],
                    "properties": {
                        "k8s_credentials": {
                            "allOf": [{"$ref": "#/definitions/k8s_credentials"}],
                            "title": "K8s Credentials",
                            "default": {
                                "$ref": {
                                    "block_document_id": f"{k8s_credentials._block_document_id}"
                                }
                            },
                            "description": "The credentials to use to authenticate with K8s.",
                        },
                    },
                    "definitions": {
                        "k8s_credentials": {
                            "type": "object",
                            "title": "k8s_credentials",
                            "required": ["context_name", "config"],
                            "properties": {
                                "context_name": {
                                    "type": "string",
                                    "title": "Context name",
                                },
                                "config": {
                                    "type": "object",
                                    "title": "Config",
                                },
                            },
                            "description": "Block used to manage K8s Credentials.",
                            "block_type_slug": "k8s-credentials",
                            "block_schema_references": {},
                        }
                    },
                    "description": "Variables for a Modal flow run.",
                },
                "job_configuration": {
                    "k8s_credentials": "{{ k8s_credentials }}",
                },
            },
        )

        # create a flow run with no overrides
        response = await hosted_api_client.post(
            f"/deployments/{deployment.id}/create_flow_run", json={}
        )

        # a successful response means the block was resolved
        assert response.status_code == 201, response.text

        # because we the default came from the default base job template,
        # the job_variables should not pull that value in
        assert response.json()["job_variables"] == {}


class TestInfraOverridesUpdates:
    async def test_updating_flow_run_with_valid_updates(
        self,
        session,
        client,
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
        assert response.status_code == 422
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
    ):
        # update a non-existent flow run
        response = await client.patch(
            f"/flow_runs/{uuid.uuid4()}", json={"job_variables": {"foo": "bar"}}
        )

        # verify the update failed
        assert response.status_code == 404
        assert response.json()["detail"] == "Flow run not found"

    @pytest.mark.parametrize("job_variables", [{}, None, {"x": "y"}])
    async def test_updating_flow_run_with_missing_work_queue(
        self,
        session,
        client,
        job_variables,
    ):
        # create a pool with a pool schema that has a default value
        _, pool, deployment = await create_objects_for_pool(session)

        # create a flow run
        response = await client.post(
            f"/deployments/{deployment.id}/create_flow_run", json={}
        )

        # delete the deployment's work queue + work pool
        deleted = await models.workers.delete_work_pool(session, pool.id)
        assert deleted

        await session.commit()

        # attempt to update the flow run
        flow_run_id = response.json()["id"]
        response = await client.patch(
            f"/flow_runs/{flow_run_id}", json={"job_variables": job_variables}
        )

        # verify we were able to successfully create the run
        assert response.status_code == 204

    async def test_base_job_template_default_references_to_blocks(
        self,
        session,
        hosted_api_client,
        k8s_credentials,
    ):
        # create a pool with a pool schema that has a default value referencing a block
        *_, deployment = await create_objects_for_pool(
            session,
            pool_job_config={
                "variables": {
                    "type": "object",
                    "required": ["k8s_credentials"],
                    "properties": {
                        "k8s_credentials": {
                            "allOf": [{"$ref": "#/definitions/k8s_credentials"}],
                            "title": "K8s Credentials",
                            "default": {
                                "$ref": {
                                    "block_document_id": f"{k8s_credentials._block_document_id}"
                                }
                            },
                            "description": "The credentials to use to authenticate with K8s.",
                        },
                    },
                    "definitions": {
                        "k8s_credentials": {
                            "type": "object",
                            "title": "k8s_credentials",
                            "required": ["context_name", "config"],
                            "properties": {
                                "context_name": {
                                    "type": "string",
                                    "title": "Context name",
                                },
                                "config": {
                                    "type": "object",
                                    "title": "Config",
                                },
                            },
                            "description": "Block used to manage K8s Credentials.",
                            "block_type_slug": "k8s-credentials",
                            "block_schema_references": {},
                        }
                    },
                    "description": "Variables for a Modal flow run.",
                },
                "job_configuration": {
                    "k8s_credentials": "{{ k8s_credentials }}",
                },
            },
        )

        # create a flow run with custom overrides
        updates = {"k8s_credentials": {"context_name": "foo", "config": {}}}
        response = await hosted_api_client.post(
            f"/deployments/{deployment.id}/create_flow_run",
            json={"job_variables": updates},
        )
        assert response.status_code == 201, response.text
        assert response.json()["job_variables"] == updates

        # update the flow run to force it to refer to the default block's value
        flow_run_id = response.json()["id"]
        response = await hosted_api_client.patch(
            f"/flow_runs/{flow_run_id}", json={"job_variables": {}}
        )
        assert response.status_code == 204, response.text

        # verify that the flow run's job variables are removed
        flow_run = await models.flow_runs.read_flow_run(
            session=session, flow_run_id=flow_run_id
        )
        assert flow_run.job_variables == {}
