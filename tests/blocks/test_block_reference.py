import asyncio
import warnings
from typing import Any, Type
from uuid import UUID, uuid4

import pydantic
import pytest

from prefect.blocks.core import Block
from prefect.exceptions import ParameterTypeError
from prefect.flows import flow


class TestBlockReference:
    class ReferencedBlock(Block):
        a: int
        b: str

    class SimilarReferencedBlock(Block):
        a: int
        b: str

    class OtherReferencedBlock(Block):
        c: int
        d: str

    @pytest.fixture
    def block_document_id(self, prefect_client) -> UUID:
        block = self.ReferencedBlock(a=1, b="foo")
        block_name = f"block-reference-{uuid4()}"
        block.save(block_name, client=prefect_client)
        return block._block_document_id

    def test_block_load_from_reference(
        self,
        block_document_id: UUID,
    ):
        block = self.ReferencedBlock.load_from_ref(block_document_id)
        assert block.a == 1
        assert block.b == "foo"

    def test_base_block_load_from_reference(
        self,
        block_document_id: UUID,
    ):
        block = Block.load_from_ref(block_document_id)
        assert isinstance(block, self.ReferencedBlock)
        assert block.a == 1
        assert block.b == "foo"

    def test_block_load_from_reference_string(
        self,
        block_document_id: UUID,
    ):
        block = self.ReferencedBlock.load_from_ref(str(block_document_id))
        assert block.a == 1
        assert block.b == "foo"

    def test_block_load_from_bad_reference(self):
        with pytest.raises(ValueError, match="is not a valid UUID"):
            self.ReferencedBlock.load_from_ref("non-valid-uuid")

        with pytest.raises(ValueError, match="Unable to find block document with ID"):
            self.ReferencedBlock.load_from_ref(uuid4())

    def test_block_load_from_similar_block_reference_type(self):
        block = self.SimilarReferencedBlock(a=1, b="foo")
        block_name = f"other-block-{uuid4()}"
        block.save(block_name)

        block = self.ReferencedBlock.load_from_ref(block._block_document_id)
        assert block.a == 1
        assert block.b == "foo"

    def test_block_load_from_invalid_block_reference_type(self):
        block = self.OtherReferencedBlock(c=1, d="foo")
        block_name = f"other-block-{uuid4()}"
        block.save(block_name)

        with pytest.raises(RuntimeError):
            self.ReferencedBlock.load_from_ref(block._block_document_id)

    def test_block_load_from_nested_block_reference(self):
        ReferencedBlock = self.ReferencedBlock

        class NestedReferencedBlock(Block):
            inner_block: ReferencedBlock

        nested_block = NestedReferencedBlock(inner_block=ReferencedBlock(a=1, b="foo"))
        block_name = f"nested-block-{uuid4()}"
        nested_block.save(block_name)

        loaded_block = NestedReferencedBlock.load_from_ref(
            nested_block._block_document_id
        )
        assert getattr(loaded_block, "inner_block", None) is not None
        assert loaded_block.inner_block.a == 1
        assert loaded_block.inner_block.b == "foo"


class TestFlowWithBlockParam:
    @pytest.fixture
    def ParamBlock(self) -> Type[Block]:
        # Ignore warning caused by matching key in registry due to block fixture
        warnings.filterwarnings("ignore", category=UserWarning)

        class ParamBlock(Block):
            a: int
            b: str

        return ParamBlock

    @pytest.fixture
    def OtherParamBlock(self) -> Type[Block]:
        # Ignore warning caused by matching key in registry due to block fixture
        warnings.filterwarnings("ignore", category=UserWarning)

        class OtherParamBlock(Block):
            a: int
            b: str

        return OtherParamBlock

    @pytest.mark.parametrize(
        "reference_type", ["uuid", "uuid_string", "id", "id_string", "id_urn", "slug"]
    )
    def test_flow_with_block_params(self, ParamBlock: type[Block], reference_type: str):
        ref_block = ParamBlock(a=10, b="foo")
        block_name = f"param-block-{uuid4()}"
        ref_block.save(block_name)
        references = {
            "uuid": ref_block._block_document_id,
            "uuid_string": str(ref_block._block_document_id),
            "id": {"block_document_id": ref_block._block_document_id},
            "id_string": {"block_document_id": str(ref_block._block_document_id)},
            "id_urn": {"block_document_id": ref_block._block_document_id.urn},
            "slug": {
                "block_document_slug": f"{ParamBlock.get_block_type_slug()}/{block_name}"
            },
        }

        @flow
        def flow_with_block_param(block: ParamBlock) -> int:
            return block.a

        assert (
            flow_with_block_param({"$ref": references[reference_type]}) == ref_block.a
        )

    def test_flow_with_invalid_block_reference(self, ParamBlock: type[Block]):
        @flow
        def flow_with_block_param(block: ParamBlock) -> int:
            return block.a

        with pytest.raises(
            ParameterTypeError, match="Failed to resolve block references in parameters"
        ):
            flow_with_block_param.validate_parameters(
                {"block": {"$ref": {"block_document_id": "not-a-uuid"}}}
            )

    def test_flow_with_invalid_block_param_type(self, ParamBlock, OtherParamBlock):
        ref_block = OtherParamBlock(a=10, b="foo")
        block_name = f"other-param-block-{uuid4()}"
        ref_block.save(block_name)

        @flow
        def flow_with_block_param(block: ParamBlock) -> int:
            return block.a

        with pytest.raises(
            ParameterTypeError, match="Flow run received invalid parameters"
        ):
            flow_with_block_param({"$ref": str(ref_block._block_document_id)})

    def test_flow_with_nested_block_params(self, ParamBlock):
        class NestedParamBlock(Block):
            inner_block: ParamBlock

        nested_block = NestedParamBlock(inner_block=ParamBlock(a=12, b="foo"))
        block_name = f"nested-block-{uuid4()}"
        nested_block.save(block_name)

        @flow
        def flow_with_nested_block_param(block: NestedParamBlock):
            return block.inner_block.a

        assert (
            flow_with_nested_block_param(
                {"$ref": {"block_document_id": str(nested_block._block_document_id)}}
            )
            == nested_block.inner_block.a
        )

    def test_flow_with_block_param_in_basemodel(self, ParamBlock):
        class ParamModel(pydantic.BaseModel):
            block: ParamBlock

        param_block = ParamBlock(a=12, b="foo")
        block_name = f"param-block-{uuid4()}"
        param_block.save(block_name)

        @flow
        def flow_with_block_param_in_basemodel(param: ParamModel):
            return param.block.a

        assert (
            flow_with_block_param_in_basemodel(
                {
                    "block": {
                        "$ref": {
                            "block_document_id": str(param_block._block_document_id)
                        }
                    }
                }
            )
            == param_block.a
        )

    def test_async_flow_with_block_params(self, ParamBlock):
        ref_block = ParamBlock(a=10, b="foo")
        block_name = f"param-block-{uuid4()}"
        ref_block.save(block_name)

        @flow
        async def flow_with_block_param(block: ParamBlock) -> int:
            return block.a

        assert (
            asyncio.run(
                flow_with_block_param({"$ref": str(ref_block._block_document_id)})
            )
            == ref_block.a
        )
        assert (
            asyncio.run(
                flow_with_block_param(
                    {"$ref": {"block_document_id": str(ref_block._block_document_id)}}
                )
            )
            == ref_block.a
        )


class TestFlowWithSchemaParam:
    @pytest.mark.parametrize(
        "reference",
        [
            "#/$defs/Item",
            "https://example.com/schema.json",
            "schema.json#/$defs/Item",
            "urn:uuid:12345678-1234-1234-1234-123456789abc",
            "uuid:12345678-1234-1234-1234-123456789abc",
        ],
    )
    def test_flow_preserves_schema_references(self, reference: str):
        @flow
        def schema_flow(schema_data: dict[str, Any]) -> dict[str, Any]:
            return schema_data

        schema = {"properties": {"item": {"$ref": reference, "title": "Item"}}}
        assert schema_flow(schema) == schema

    @pytest.mark.parametrize("is_async", [False, True])
    def test_flow_preserves_schema_in_model_parameter(self, is_async: bool):
        class Item(pydantic.BaseModel):
            value: int

        class Payload(pydantic.BaseModel):
            item: Item

        class SchemaParameter(pydantic.BaseModel):
            schema_data: dict[str, Any]

        @flow
        def schema_flow(parameter: SchemaParameter) -> SchemaParameter:
            return parameter

        @flow
        async def async_schema_flow(parameter: SchemaParameter) -> SchemaParameter:
            return parameter

        parameter = SchemaParameter(schema_data=Payload.model_json_schema())
        if is_async:
            result = asyncio.run(async_schema_flow(parameter))
        else:
            result = schema_flow(parameter)

        assert isinstance(result, SchemaParameter)
        assert result == parameter
