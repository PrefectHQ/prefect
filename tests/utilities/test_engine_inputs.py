from typing import Any, Literal

import pytest
from pydantic import BaseModel, ConfigDict, PrivateAttr

from prefect.states import Completed
from prefect.utilities.annotations import quote
from prefect.utilities.engine import resolve_inputs, resolve_inputs_sync


@pytest.mark.parametrize("resolver", ["sync", "async"])
@pytest.mark.parametrize("frozen", [False, True])
@pytest.mark.parametrize("input_type", ["quote", "state"])
async def test_resolve_inputs_with_unset_private_attribute(
    resolver: Literal["sync", "async"],
    frozen: bool,
    input_type: Literal["quote", "state"],
):
    class Document(BaseModel):
        model_config = ConfigDict(frozen=frozen)
        text: Any
        _cache: dict[str, Any] = PrivateAttr()

    value = (
        quote("parsed text") if input_type == "quote" else Completed(data="parsed text")
    )
    document = Document(text=value)
    parameters = {"document": document}

    if resolver == "sync":
        resolved = resolve_inputs_sync(parameters)
    else:
        resolved = await resolve_inputs(parameters)

    result = resolved["document"]
    assert isinstance(result, Document)
    assert result.text == "parsed text"
    assert not hasattr(result, "_cache")
    assert document.text is value
    assert not hasattr(document, "_cache")
