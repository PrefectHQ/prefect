from uuid import uuid4

import pydantic
import pytest

from prefect.orion import schemas


@pytest.mark.parametrize(
    "name",
    [
        "my-object",
        "my object",
        "my:object",
        "my;object",
        r"my\object",
        "my|object",
        "my⁉️object",
    ],
)
async def test_valid_names(name):
    assert schemas.core.Flow(name=name)
    assert schemas.core.Deployment(
        name=name,
        flow_id=uuid4(),
        flow_data=schemas.data.DataDocument(encoding="x", blob=b"y"),
    )
    assert schemas.core.BlockDocument(
        name=name, block_schema_id=uuid4(), block_type_id=uuid4()
    )


@pytest.mark.parametrize(
    "name",
    [
        "my/object",
        r"my%object",
    ],
)
async def test_invalid_names(name):
    with pytest.raises(pydantic.ValidationError, match="contains an invalid character"):
        assert schemas.core.Flow(name=name)
    with pytest.raises(pydantic.ValidationError, match="contains an invalid character"):
        assert schemas.core.Deployment(
            name=name,
            flow_id=uuid4(),
            flow_data=schemas.data.DataDocument(encoding="x", blob=b"y"),
        )
    with pytest.raises(pydantic.ValidationError, match="contains an invalid character"):
        assert schemas.core.BlockDocument(
            name=name, block_schema_id=uuid4(), block_type_id=uuid4()
        )


class TestBlockDocument:
    async def test_block_document_requires_name(self):
        with pytest.raises(
            ValueError, match="(Names must be provided for block documents.)"
        ):
            schemas.core.BlockDocument(block_schema_id=uuid4(), block_type_id=uuid4())

    async def test_anonymous_block_document_does_not_require_name(self):
        assert schemas.core.BlockDocument(
            block_schema_id=uuid4(), block_type_id=uuid4(), is_anonymous=True
        )


class TestFlowRunNotificationPolicy:
    async def test_message_template_variables_are_validated(self):
        with pytest.raises(
            pydantic.ValidationError,
            match="(Invalid template variable provided: 'bad_variable')",
        ):
            schemas.core.FlowRunNotificationPolicy(
                name="test",
                state_names=[],
                tags=[],
                block_document_id=uuid4(),
                message_template="This uses a {bad_variable}",
            )

    async def test_multiple_message_template_variables_are_validated(self):
        with pytest.raises(
            pydantic.ValidationError,
            match="(Invalid template variable provided: 'bad_variable')",
        ):
            schemas.core.FlowRunNotificationPolicy(
                name="test",
                state_names=[],
                tags=[],
                block_document_id=uuid4(),
                message_template="This contains {flow_run_id} and {bad_variable} and {another_bad_variable}",
            )
