from typing import Any, Type, Union
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from prefect.server import models, schemas
from prefect.server.api.validation import (
    validate_job_variable_defaults_for_work_pool,
    validate_job_variables_for_deployment,
    validate_job_variables_for_deployment_flow_run,
)
from prefect.server.database.orm_models import ORMDeployment, ORMFlow, ORMWorkPool
from prefect.server.schemas.actions import (
    DeploymentCreate,
    DeploymentFlowRunCreate,
    DeploymentUpdate,
)


@pytest.fixture
async def deployment_with_work_queue(
    work_pool,
    flow,
    session,
) -> ORMDeployment:
    deployment = await models.deployments.create_deployment(
        session=session,
        deployment=schemas.core.Deployment(
            flow_id=flow.id,
            name="test-deployment",
            work_queue_id=work_pool.default_queue_id,
        ),
    )
    await session.commit()
    return deployment


@pytest.fixture
async def missing_block_doc_ref_template():
    return {
        "job_configuration": {
            "block": "{{ block_string }}",
        },
        "variables": {
            "properties": {
                "block_string": {
                    "type": "string",
                    "title": "Block String",
                    "default": {"$ref": {"block_document_id": str(uuid4())}},
                },
            },
            "required": ["block_string"],
        },
    }


@pytest.fixture
async def empty_block_doc_ref_template():
    return {
        "job_configuration": {
            "block": "{{ block_string }}",
        },
        "variables": {
            "properties": {
                "block_string": {
                    "type": "string",
                    "title": "Block String",
                    "default": {"$ref": {"block_document_id": ""}},
                },
            },
            "required": ["block_string"],
        },
    }


@pytest.fixture
async def malicious_block_doc_ref_template():
    return {
        "job_configuration": {
            "block": "{{ block_string }}",
        },
        "variables": {
            "properties": {
                "block_string": {
                    "type": "string",
                    "title": "Block String",
                    "default": {"$ref": {"block_document_id": "i'm hacking ya"}},
                },
            },
            "required": ["block_string"],
        },
    }


@pytest.fixture
def incorrect_type_block_ref_template(
    block_document,
):
    return {
        "job_configuration": {
            "block": "{{ block_string }}",
        },
        "variables": {
            "properties": {
                "block_string": {
                    "type": "string",
                    "title": "Block String",
                    "default": {"$ref": {"block_document_id": str(block_document.id)}},
                },
            },
            "required": ["block_string"],
        },
    }


@pytest.fixture
def block_ref_template(
    block_document,
):
    return {
        "job_configuration": {
            "block": "{{ block_object }}",
        },
        "variables": {
            "properties": {
                "block_object": {
                    "type": "object",
                    "title": "Block Object",
                    "default": {"$ref": {"block_document_id": str(block_document.id)}},
                },
            },
            "required": ["block_object"],
        },
    }


@pytest.fixture
def template_required_field_no_default():
    return {
        "job_configuration": {
            "name": "{{ name }}",
        },
        "variables": {
            "properties": {
                "name": {
                    "type": "string",
                    "title": "Username",
                },
            },
            "required": ["name"],
        },
    }


@pytest.fixture
def template_required_field_with_default():
    return {
        "job_configuration": {
            "laptop_choice": "{{ laptop_choice }}",
        },
        "variables": {
            "properties": {
                "laptop_choice": {
                    "type": "string",
                    "title": "Laptop Choice",
                    "default": "macbook pro",
                },
            },
            "required": ["laptop_choice"],
        },
    }


@pytest.fixture
def template_optional_field_with_default():
    """
    This is the "broken" JSON schema that Pydantic v1 generates for both
    of these field types:

        laptop_choice: str | None = "macbook pro"
        laptop_choice: str = "macbook pro"

    The first field can accept None, but the second field cannot, yet the
    JSON schema doesn't let us differentiate between the two.
    """
    return {
        "job_configuration": {
            "laptop_choice": "{{ laptop_choice }}",
        },
        "variables": {
            "properties": {
                "laptop_choice": {
                    "type": "string",
                    "title": "Laptop Choice",
                    "default": "macbook pro",
                },
            },
            "required": [],
        },
    }


@pytest.fixture
def template_optional_field():
    return {
        "job_configuration": {
            "age": "{{ age }}",
        },
        "variables": {
            "properties": {
                "age": {
                    "type": "integer",
                    "title": "Age",
                },
            },
            "required": [],
        },
    }


@pytest.fixture
async def empty_block_document(session, block_schema, block_type_x):
    block_document = await models.block_documents.create_block_document(
        session=session,
        block_document=schemas.actions.BlockDocumentCreate(
            block_schema_id=block_schema.id,
            name="block-1",
            block_type_id=block_type_x.id,
            data={},
        ),
    )
    await session.commit()
    return block_document


@pytest.fixture
async def empty_block_ref_template(empty_block_document):
    return {
        "job_configuration": {
            "block": "{{ block_string }}",
        },
        "variables": {
            "properties": {
                "block_string": {
                    "type": "string",
                    "title": "Block String",
                    "default": {
                        "$ref": {"block_document_id": str(empty_block_document.id)}
                    },
                },
            },
            "required": ["block_string"],
        },
    }


async def create_work_pool(
    session: AsyncSession, base_job_template: dict, **kwargs
) -> ORMWorkPool:
    work_pool = await models.workers.create_work_pool(
        session=session,
        work_pool=schemas.actions.WorkPoolCreate(
            name="test-pool", base_job_template=base_job_template, **kwargs
        ),
    )
    await session.flush()
    return work_pool


async def create_deployment_with_work_pool(
    session: AsyncSession,
    flow: ORMFlow,
    work_pool: ORMWorkPool,
    **kwargs: Any,
) -> ORMDeployment:
    deployment = await models.deployments.create_deployment(
        session=session,
        deployment=schemas.core.Deployment(
            flow_id=flow.id,
            name="test-deployment",
            work_queue_id=work_pool.default_queue_id,
            **kwargs,
        ),
    )
    await session.flush()
    return deployment


class TestWorkPoolValidation:
    async def test_work_pool_template_validation_empty_block_document(
        self,
        session,
        work_pool,
        empty_block_doc_ref_template,
    ):
        with pytest.raises(HTTPException, match="404: Block not found."):
            await validate_job_variable_defaults_for_work_pool(
                session,
                work_pool.name,
                empty_block_doc_ref_template,
            )

    async def test_work_pool_template_validation_missing_block_document(
        self,
        session,
        work_pool,
        missing_block_doc_ref_template,
    ):
        with pytest.raises(HTTPException, match="404: Block not found."):
            await validate_job_variable_defaults_for_work_pool(
                session,
                work_pool.name,
                missing_block_doc_ref_template,
            )

    async def test_work_pool_template_validation_malicious_block_document(
        self,
        session,
        work_pool,
        malicious_block_doc_ref_template,
    ):
        with pytest.raises(HTTPException, match="404: Block not found."):
            await validate_job_variable_defaults_for_work_pool(
                session,
                work_pool.name,
                malicious_block_doc_ref_template,
            )

    async def test_work_pool_template_validation_block_document_reference_incorrect_type(
        self,
        session,
        work_pool,
        incorrect_type_block_ref_template,
    ):
        with pytest.raises(
            HTTPException, match="{'foo': 'bar'} is not of type 'string'"
        ):
            await validate_job_variable_defaults_for_work_pool(
                session,
                work_pool.name,
                incorrect_type_block_ref_template,
            )

    async def test_work_pool_template_validation_block_document_reference_incorrect_type_empty_dict(
        self,
        session,
        work_pool,
        empty_block_ref_template,
    ):
        with pytest.raises(HTTPException, match="{} is not of type 'string'"):
            await validate_job_variable_defaults_for_work_pool(
                session,
                work_pool.name,
                empty_block_ref_template,
            )

    async def test_work_pool_template_validation_valid_block_document_reference(
        self,
        session,
        work_pool,
        block_ref_template,
    ):
        await validate_job_variable_defaults_for_work_pool(
            session,
            work_pool.name,
            block_ref_template,
        )


class TestDeploymentValidation:
    async def make_deployment_schema(
        self,
        flow_id: UUID,
        schema_cls: Union[Type[DeploymentCreate], Type[DeploymentUpdate]],
    ):
        if schema_cls == DeploymentCreate:
            params = {
                "flow_id": flow_id,
                "name": "test-deployment-2",
            }
        else:
            params = {}

        deployment = schema_cls(**params)
        return deployment

    @pytest.mark.parametrize("schema_cls", [DeploymentCreate, DeploymentUpdate])
    async def test_deployment_template_validation_succeeds_with_missing_default_block_document(
        self,
        session,
        work_pool,
        flow,
        deployment_with_work_queue,
        missing_block_doc_ref_template,
        schema_cls,
    ):
        """
        When we validate a deployment's job variables, we only validate the job variables
        and not default values in the base template.
        """
        work_pool.base_job_template = missing_block_doc_ref_template
        deployment = await self.make_deployment_schema(flow.id, schema_cls)

        await validate_job_variables_for_deployment(
            session,
            work_pool,
            deployment,
        )

    @pytest.mark.parametrize("schema_cls", [DeploymentCreate, DeploymentUpdate])
    async def test_deployment_template_validation_succeeds_with_block_document_reference_incorrect_type(
        self,
        session,
        work_pool,
        flow,
        deployment_with_work_queue,
        incorrect_type_block_ref_template,
        schema_cls,
    ):
        """
        When we validate a deployment's job variables, we only validate the job variables
        and not default values in the base template.
        """
        work_pool.base_job_template = incorrect_type_block_ref_template
        deployment = await self.make_deployment_schema(flow.id, schema_cls)

        await validate_job_variables_for_deployment(
            session,
            work_pool,
            deployment,
        )

    @pytest.mark.parametrize("schema_cls", [DeploymentCreate, DeploymentUpdate])
    async def test_deployment_template_validation_allows_missing_required_fields(
        self,
        session,
        work_pool,
        flow,
        deployment_with_work_queue,
        template_required_field_no_default,
        schema_cls,
    ):
        work_pool.base_job_template = template_required_field_no_default
        deployment = await self.make_deployment_schema(flow.id, schema_cls)

        await validate_job_variables_for_deployment(
            session,
            work_pool,
            deployment,
        )

    @pytest.mark.parametrize("schema_cls", [DeploymentCreate, DeploymentUpdate])
    async def test_deployment_template_validation_invalid_type(
        self,
        session,
        work_pool,
        flow,
        deployment_with_work_queue,
        template_optional_field,
        schema_cls,
    ):
        work_pool.base_job_template = template_optional_field
        deployment = await self.make_deployment_schema(flow.id, schema_cls)
        deployment.job_variables = {"age": "hi"}

        with pytest.raises(HTTPException, match="'hi' is not valid"):
            await validate_job_variables_for_deployment(
                session,
                work_pool,
                deployment,
            )

    @pytest.mark.parametrize("schema_cls", [DeploymentCreate, DeploymentUpdate])
    async def test_deployment_template_validation_valid(
        self,
        session,
        work_pool,
        flow,
        deployment_with_work_queue,
        template_optional_field,
        schema_cls,
    ):
        work_pool.base_job_template = template_optional_field
        deployment = await self.make_deployment_schema(flow.id, schema_cls)
        deployment.job_variables = {"age": 41}

        await validate_job_variables_for_deployment(
            session,
            work_pool,
            deployment,
        )

    @pytest.mark.parametrize("schema_cls", [DeploymentCreate, DeploymentUpdate])
    async def test_deployment_template_validation_ignores_variable_not_in_schema(
        self,
        session,
        work_pool,
        flow,
        deployment_with_work_queue,
        template_optional_field,
        schema_cls,
    ):
        work_pool.base_job_template = template_optional_field
        deployment = await self.make_deployment_schema(flow.id, schema_cls)
        deployment.job_variables = {"favorite_type_of_bike": "touring"}

        await validate_job_variables_for_deployment(
            session,
            work_pool,
            deployment,
        )


class TestDeploymentFlowRunJobVariablesValidation:
    async def test_missing_block_document_default_value(
        self,
        flow,
        session,
        missing_block_doc_ref_template,
    ):
        work_pool = await create_work_pool(
            session=session,
            base_job_template=missing_block_doc_ref_template,
        )
        deployment = await create_deployment_with_work_pool(
            session=session,
            flow=flow,
            work_pool=work_pool,
        )

        with pytest.raises(HTTPException, match="404: Block not found."):
            await validate_job_variables_for_deployment_flow_run(
                session=session,
                deployment=deployment,
                flow_run=DeploymentFlowRunCreate(
                    state=schemas.states.Scheduled().to_state_create()
                ),
            )

    async def test_ignores_block_document_reference_incorrect_type_in_default_value(
        self,
        flow,
        session,
        incorrect_type_block_ref_template,
    ):
        work_pool = await create_work_pool(
            session=session,
            base_job_template=incorrect_type_block_ref_template,
        )
        deployment = await create_deployment_with_work_pool(
            session=session,
            flow=flow,
            work_pool=work_pool,
        )

        await validate_job_variables_for_deployment_flow_run(
            session=session,
            deployment=deployment,
            flow_run=DeploymentFlowRunCreate(
                state=schemas.states.Scheduled().to_state_create()
            ),
        )

    async def test_valid_block_document_reference(
        self,
        flow,
        block_ref_template,
        session,
    ):
        work_pool = await create_work_pool(
            session=session,
            base_job_template=block_ref_template,
        )
        deployment = await create_deployment_with_work_pool(
            session=session,
            flow=flow,
            work_pool=work_pool,
        )

        await validate_job_variables_for_deployment_flow_run(
            session=session,
            deployment=deployment,
            flow_run=DeploymentFlowRunCreate(
                state=schemas.states.Scheduled().to_state_create()
            ),
        )

    async def test_allows_missing_required_variable_with_default(
        self,
        flow,
        template_required_field_with_default,
        session,
    ):
        work_pool = await create_work_pool(
            session=session,
            base_job_template=template_required_field_with_default,
        )
        deployment = await create_deployment_with_work_pool(
            session=session,
            flow=flow,
            work_pool=work_pool,
        )

        await validate_job_variables_for_deployment_flow_run(
            session=session,
            deployment=deployment,
            flow_run=DeploymentFlowRunCreate(
                state=schemas.states.Scheduled().to_state_create()
            ),
        )

    async def test_allows_missing_optional_variable_with_default(
        self,
        flow,
        template_optional_field_with_default,
        session,
    ):
        work_pool = await create_work_pool(
            session=session,
            base_job_template=template_optional_field_with_default,
        )
        deployment = await create_deployment_with_work_pool(
            session=session,
            flow=flow,
            work_pool=work_pool,
        )

        await validate_job_variables_for_deployment_flow_run(
            session=session,
            deployment=deployment,
            flow_run=DeploymentFlowRunCreate(
                state=schemas.states.Scheduled().to_state_create()
            ),
        )

    async def test_allows_none_for_optional_variable_with_default(
        self,
        flow,
        template_optional_field_with_default,
        session,
    ):
        """
        Multiple Infrastructure block fields default to None, so we should allow None as a
        valid value for optional fields even when those fields have default values (and
        thus we can't know, because of Pydantic v1 limitations, whether the field
        supports None as a value).
        """
        work_pool = await create_work_pool(
            session=session,
            base_job_template=template_optional_field_with_default,
        )
        deployment = await create_deployment_with_work_pool(
            session=session,
            flow=flow,
            work_pool=work_pool,
            job_variables={"laptop_choice": None},
        )

        await validate_job_variables_for_deployment_flow_run(
            session=session,
            deployment=deployment,
            flow_run=DeploymentFlowRunCreate(
                state=schemas.states.Scheduled().to_state_create()
            ),
        )

    async def test_allows_missing_optional_variable_with_no_default(
        self,
        flow,
        template_optional_field,
        session,
    ):
        work_pool = await create_work_pool(
            session=session,
            base_job_template=template_optional_field,
        )
        deployment = await create_deployment_with_work_pool(
            session=session,
            flow=flow,
            work_pool=work_pool,
        )

        await validate_job_variables_for_deployment_flow_run(
            session=session,
            deployment=deployment,
            flow_run=DeploymentFlowRunCreate(
                state=schemas.states.Scheduled().to_state_create()
            ),
        )
