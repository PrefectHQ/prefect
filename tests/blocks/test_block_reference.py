import warnings
from typing import Dict, Type
from uuid import uuid4

import pytest
from pydantic import ValidationError

from prefect.blocks.core import Block
from prefect.exceptions import ParameterTypeError
from prefect.flows import flow


class TestBlockReference:
    class ReferencedBlock(Block):
        a: int
        b: str

    class OtherReferencedBlock(Block):
        a: int
        b: str

    @pytest.fixture
    def block_reference(self, prefect_client) -> Dict[str, str]:
        block = self.ReferencedBlock(a=1, b="foo")
        block.save("block-reference", client=prefect_client)
        return {"$ref": str(block._block_document_id)}

    def test_block_initialization_from_reference(
        self,
        block_reference: Dict[str, str],
    ):
        block = self.ReferencedBlock(**block_reference)
        assert block.a == 1
        assert block.b == "foo"

    def test_block_initialization_from_reference_with_kwargs(
        self,
        block_reference: Dict[str, str],
    ):
        block = self.ReferencedBlock(**block_reference, a=2)
        assert block.a == 2
        assert block.b == "foo"

    def test_block_initialization_from_bad_reference(self):
        with pytest.raises(ValueError, match="is not a valid UUID"):
            self.ReferencedBlock(**{"$ref": "non-valid-uuid"})

        with pytest.raises(ValueError, match="Unable to find block document with ID"):
            self.ReferencedBlock(**{"$ref": str(uuid4())})

    def test_block_initialization_from_invalid_block_reference_type(self):
        block = self.OtherReferencedBlock(a=1, b="foo")
        block.save("other-block")

        with pytest.raises(ValueError, match="Invalid Block reference type"):
            self.ReferencedBlock(**{"$ref": str(block._block_document_id)})

    def test_block_validation_from_reference(
        self,
        block_reference: Dict[str, str],
    ):
        block = self.ReferencedBlock.model_validate(block_reference)
        assert block.a == 1
        assert block.b == "foo"

    def test_block_validation_from_bad_reference(
        self,
        block_reference: Dict[str, str],
    ):
        with pytest.raises(ValidationError):
            self.ReferencedBlock.model_validate({"$ref": "non-valid-uuid"})

        with pytest.raises(ValidationError):
            self.ReferencedBlock.model_validate({"$ref": str(uuid4())})

    def test_block_validation_from_invalid_block_reference_type(self):
        block = self.OtherReferencedBlock(a=1, b="foo")
        block.save("other-block")

        with pytest.raises(ValidationError):
            self.ReferencedBlock.model_validate({"$ref": str(block._block_document_id)})


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
