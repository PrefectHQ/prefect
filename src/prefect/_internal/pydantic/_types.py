from typing import Any, Dict, Literal, Set, Union

from typing_extensions import Annotated, TypeAlias

from ._base_model import Field

IncEx: TypeAlias = "Union[Set[int], Set[str], Dict[int, Any], Dict[str, Any], None]"

DEFAULT_REF_TEMPLATE = "#/$defs/{model}"
JsonSchemaMode = Literal["validation", "serialization"]

NonNegativeInteger = Annotated[int, Field(ge=0)]
PositiveInteger = Annotated[int, Field(gt=0)]
