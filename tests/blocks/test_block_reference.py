import asyncio
import warnings
from typing import Type
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
        block.save("block-reference", client=prefect_client)
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
        block.save("other-block")

        block = self.ReferencedBlock.load_from_ref(block._block_document_id)
        assert block.a == 1
        assert block.b == "foo"

    def test_block_load_from_invalid_block_reference_type(self):
        block = self.OtherReferencedBlock(c=1, d="foo")
        block.save("other-block")

        with pytest.raises(RuntimeError):
            self.ReferencedBlock.load_from_ref(block._block_document_id)

    def test_block_load_from_nested_block_reference(self):
        ReferencedBlock = self.ReferencedBlock

        class NestedReferencedBlock(Block):
            inner_block: ReferencedBlock

        nested_block = NestedReferencedBlock(inner_block=ReferencedBlock(a=1, b="foo"))
        nested_block.save("nested-block")

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

    def test_flow_with_block_params(self, ParamBlock):
        ref_block = ParamBlock(a=10, b="foo")
        ref_block.save("param-block")

        @flow
        def flow_with_block_param(block: ParamBlock) -> int:
            return block.a

        assert (
            flow_with_block_param({"$ref": str(ref_block._block_document_id)})
            == ref_block.a
        )
        assert (
            flow_with_block_param(
                {"$ref": {"block_document_id": str(ref_block._block_document_id)}}
            )
            == ref_block.a
        )

    def test_flow_with_invalid_block_param_type(self, ParamBlock, OtherParamBlock):
        ref_block = OtherParamBlock(a=10, b="foo")
        ref_block.save("other-param-block")

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
        nested_block.save("nested-block")

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
        param_block.save("param-block")

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
        ref_block.save("param-block")

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
