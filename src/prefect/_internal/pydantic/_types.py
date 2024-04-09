from typing import Any, Dict, Literal, Set, Union

from annotated_types import Ge
from typing_extensions import Annotated, TypeAlias

IncEx: TypeAlias = "Union[Set[int], Set[str], Dict[int, Any], Dict[str, Any], None]"

DEFAULT_REF_TEMPLATE = "#/$defs/{model}"
JsonSchemaMode = Literal["validation", "serialization"]

NonNegativeInteger = Annotated[int, Ge(0)]
PositiveInteger = Annotated[int, Ge(1)]
