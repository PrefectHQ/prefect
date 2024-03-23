import json
from typing import Any, Callable, Dict, Optional

from prefect._internal.pydantic import HAS_PYDANTIC_V2

if HAS_PYDANTIC_V2:
    from pydantic.v1 import BaseModel, Field
else:
    from pydantic import BaseModel, Field

from sqlalchemy.ext.asyncio import AsyncSession
from typing_extensions import TypeAlias

from prefect.server.models.variables import read_variables


class HydrationContext(BaseModel):
    workspace_variables: Dict[str, str] = Field(default_factory=dict)
    raise_on_error: bool = Field(default=False)

    @classmethod
    async def build(
        cls,
        session: AsyncSession,
        raise_on_error: bool = False,
    ) -> "HydrationContext":
        variables = await read_variables(
            session=session,
        )
        return cls(
            workspace_variables={
                variable.name: variable.value for variable in variables
            },
            raise_on_error=raise_on_error,
        )


Handler: TypeAlias = Callable[[Dict, HydrationContext], Any]
PrefectKind: TypeAlias = Optional[str]

_handlers: Dict[PrefectKind, Handler] = {}


class Placeholder:
    def __eq__(self, other):
        return isinstance(other, type(self))

    @property
    def is_error(self) -> bool:
        return False


class RemoveValue(Placeholder):
    pass


def _remove_value(value) -> bool:
    return isinstance(value, RemoveValue)


class HydrationError(Placeholder, Exception):
    def __init__(self, detail: Optional[str] = None):
        self.detail = detail

    @property
    def is_error(self) -> bool:
        return True

    @property
    def message(self):
        raise NotImplementedError("Must be implemented by subclass")

    def __eq__(self, other):
        return isinstance(other, type(self)) and self.message == other.message

    def __str__(self):
        return self.message


class KeyNotFound(HydrationError):
    @property
    def message(self):
        return f"Missing '{self.key}' key in __prefect object"

    @property
    def key(self) -> str:
        raise NotImplementedError("Must be implemented by subclass")


class ValueNotFound(KeyNotFound):
    @property
    def key(self):
        return "value"


class VariableNameNotFound(KeyNotFound):
    @property
    def key(self):
        return "variable_name"


class InvalidJSON(HydrationError):
    @property
    def message(self):
        message = "Invalid JSON"
        if self.detail:
            message += f": {self.detail}"
        return message


class WorkspaceVariableNotFound(HydrationError):
    @property
    def variable_name(self) -> str:
        assert self.detail is not None
        return self.detail

    @property
    def message(self):
        return f"Variable '{self.detail}' not found."


def handler(kind: PrefectKind) -> Callable:
    def decorator(func: Handler) -> Handler:
        _handlers[kind] = func
        return func

    return decorator


def call_handler(kind: PrefectKind, obj: Dict, ctx: HydrationContext) -> Any:
    if kind not in _handlers:
        return (obj or {}).get("value", None)

    res = _handlers[kind](obj, ctx)
    if ctx.raise_on_error and isinstance(res, HydrationError):
        raise res
    return res


@handler("none")
def null_handler(obj: Dict, ctx: HydrationContext):
    if "value" in obj:
        # null handler is a pass through, so we want to continue to hydrate
        return _hydrate(obj["value"], ctx)
    else:
        return ValueNotFound()


@handler("json")
def json_handler(obj: Dict, ctx: HydrationContext):
    if "value" in obj:
        if isinstance(obj["value"], dict):
            dehydrated_json = _hydrate(obj["value"], ctx)
        else:
            dehydrated_json = obj["value"]
        try:
            return json.loads(dehydrated_json)
        except (json.decoder.JSONDecodeError, TypeError) as e:
            return InvalidJSON(detail=str(e))
    else:
        # If `value` is not in the object, we need special handling to help
        # the UI. For now if an object looks like {"__prefect_kind": "json"}
        # We will remove it from the parent object. e.x.
        # {"a": {"__prefect_kind": "json"}} -> {}
        # or
        # [{"__prefect_kind": "json"}] -> []
        return RemoveValue()


@handler("workspace_variable")
def workspace_variable_handler(obj: Dict, ctx: HydrationContext):
    if "variable_name" in obj:
        if isinstance(obj["variable_name"], dict):
            dehydrated_variable = _hydrate(obj["variable_name"], ctx)
        else:
            dehydrated_variable = obj["variable_name"]

        if dehydrated_variable in ctx.workspace_variables:
            return ctx.workspace_variables[dehydrated_variable]
        else:
            return WorkspaceVariableNotFound(detail=dehydrated_variable)
    else:
        # Special handling if `variable_name` is not in the object.
        # If an object looks like {"__prefect_kind": "workspace_variable"}
        # we will remove it from the parent object. e.x.
        # {"a": {"__prefect_kind": "workspace_variable"}} -> {}
        # or
        # [{"__prefect_kind": "workspace_variable"}] -> []
        # or
        # {"__prefect_kind": "workspace_variable"} -> {}
        return RemoveValue()


def hydrate(obj: Dict, ctx: Optional[HydrationContext] = None):
    res = _hydrate(obj, ctx)

    if _remove_value(res):
        return {}

    return res


def _hydrate(obj, ctx: Optional[HydrationContext] = None):
    if ctx is None:
        ctx = HydrationContext()

    prefect_object = isinstance(obj, dict) and "__prefect_kind" in obj

    if prefect_object:
        prefect_kind = obj.get("__prefect_kind")
        return call_handler(prefect_kind, obj, ctx)
    else:
        if isinstance(obj, dict):
            return {
                key: hydrated_value
                for key, value in obj.items()
                if not _remove_value(hydrated_value := _hydrate(value, ctx))
            }
        elif isinstance(obj, list):
            return [
                hydrated_element
                for element in obj
                if not _remove_value(hydrated_element := _hydrate(element, ctx))
            ]
        else:
            return obj
