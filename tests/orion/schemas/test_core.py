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
    assert schemas.core.BlockSchema(name=name, version="1.0")
    assert schemas.core.BlockDocument(name=name, block_schema_id=uuid4())


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
        assert schemas.core.BlockSchema(name=name, version="1.0")
    with pytest.raises(pydantic.ValidationError, match="contains an invalid character"):
        assert schemas.core.BlockDocument(name=name, block_Schema_id=uuid4())


@pytest.mark.parametrize(
    "version",
    [
        "my/object",
        r"my%object",
    ],
)
async def test_invalid_block_Schema_version(version):
    with pytest.raises(
        pydantic.ValidationError, match="(Version contains an invalid character)"
    ):
        assert schemas.core.BlockSchema(name="valid name", version=version)
