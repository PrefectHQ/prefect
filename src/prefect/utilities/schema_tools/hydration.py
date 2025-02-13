import json
from abc import ABC, abstractmethod
from collections.abc import Callable, Sequence
from typing import Any, Optional, cast

import jinja2
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from typing_extensions import Self, TypeAlias, TypeIs

from prefect.types import StrictVariableValue


class HydrationContext(BaseModel):
    workspace_variables: dict[
        str,
        StrictVariableValue,
    ] = Field(default_factory=dict)
    render_workspace_variables: bool = Field(default=False)
    raise_on_error: bool = Field(default=False)
    render_jinja: bool = Field(default=False)
    jinja_context: dict[str, Any] = Field(default_factory=dict)

    @classmethod
    async def build(
        cls,
        session: AsyncSession,
        raise_on_error: bool = False,
        render_jinja: bool = False,
        render_workspace_variables: bool = False,
    ) -> Self:
        from prefect.server.database.orm_models import Variable
        from prefect.server.models.variables import read_variables

        variables: Sequence[Variable]
        if render_workspace_variables:
            variables = await read_variables(
                session=session,
            )
        else:
            variables = []

        return cls(
            workspace_variables={
                variable.name: variable.value for variable in variables
            },
            raise_on_error=raise_on_error,
            render_jinja=render_jinja,
            render_workspace_variables=render_workspace_variables,
        )


Handler: TypeAlias = Callable[[dict[str, Any], HydrationContext], Any]
PrefectKind: TypeAlias = Optional[str]

_handlers: dict[PrefectKind, Handler] = {}


class Placeholder:
    def __eq__(self, other: Any) -> bool:
        return isinstance(other, type(self))

    @property
    def is_error(self) -> bool:
        return False


class RemoveValue(Placeholder):
    pass


def _remove_value(value: Any) -> TypeIs[RemoveValue]:
    return isinstance(value, RemoveValue)


class HydrationError(Placeholder, Exception, ABC):
    def __init__(self, detail: Optional[str] = None):
        self.detail = detail

    @property
    def is_error(self) -> bool:
        return True

    @property
    @abstractmethod
    def message(self) -> str:
        raise NotImplementedError("Must be implemented by subclass")

    def __eq__(self, other: Any) -> bool:
        return isinstance(other, type(self)) and self.message == other.message

    def __str__(self) -> str:
        return self.message


class KeyNotFound(HydrationError):
    @property
    def message(self) -> str:
        return f"Missing '{self.key}' key in __prefect object"

    @property
    @abstractmethod
    def key(self) -> str:
        raise NotImplementedError("Must be implemented by subclass")


class ValueNotFound(KeyNotFound):
    @property
    def key(self) -> str:
        return "value"


class TemplateNotFound(KeyNotFound):
    @property
    def key(self) -> str:
        return "template"


class VariableNameNotFound(KeyNotFound):
    @property
    def key(self) -> str:
        return "variable_name"


class InvalidJSON(HydrationError):
    @property
    def message(self) -> str:
        message = "Invalid JSON"
        if self.detail:
            message += f": {self.detail}"
        return message


class InvalidJinja(HydrationError):
    @property
    def message(self) -> str:
        message = "Invalid jinja"
        if self.detail:
            message += f": {self.detail}"
        return message


class WorkspaceVariableNotFound(HydrationError):
    @property
    def variable_name(self) -> str:
        assert self.detail is not None
        return self.detail

    @property
    def message(self) -> str:
        return f"Variable '{self.detail}' not found in workspace."


class WorkspaceVariable(Placeholder):
    def __init__(self, variable_name: str) -> None:
        self.variable_name = variable_name

    def __eq__(self, other: Any) -> bool:
        return (
            isinstance(other, type(self)) and self.variable_name == other.variable_name
        )


class ValidJinja(Placeholder):
    def __init__(self, template: str) -> None:
        self.template = template

    def __eq__(self, other: Any) -> bool:
        return isinstance(other, type(self)) and self.template == other.template


def handler(kind: PrefectKind) -> Callable[[Handler], Handler]:
    def decorator(func: Handler) -> Handler:
        _handlers[kind] = func
        return func

    return decorator


def call_handler(kind: PrefectKind, obj: dict[str, Any], ctx: HydrationContext) -> Any:
    if kind not in _handlers:
        return obj.get("value", None)

    res = _handlers[kind](obj, ctx)
    if ctx.raise_on_error and isinstance(res, HydrationError):
        raise res
    return res


@handler("none")
def null_handler(obj: dict[str, Any], ctx: HydrationContext):
    if "value" in obj:
        # null handler is a pass through, so we want to continue to hydrate
        return _hydrate(obj["value"], ctx)
    else:
        return ValueNotFound()


@handler("json")
def json_handler(obj: dict[str, Any], ctx: HydrationContext):
    if "value" in obj:
        if isinstance(obj["value"], dict):
            dehydrated_json = _hydrate(obj["value"], ctx)
        else:
            dehydrated_json = obj["value"]

        # If the result is a Placeholder, we should return it as is
        if isinstance(dehydrated_json, Placeholder):
            return dehydrated_json

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


@handler("jinja")
def jinja_handler(obj: dict[str, Any], ctx: HydrationContext) -> Any:
    from prefect.server.utilities.user_templates import (
        TemplateSecurityError,
        render_user_template_sync,
        validate_user_template,
    )

    if "template" in obj:
        if isinstance(obj["template"], dict):
            dehydrated_jinja = _hydrate(obj["template"], ctx)
        else:
            dehydrated_jinja = obj["template"]

        # If the result is a Placeholder, we should return it as is
        if isinstance(dehydrated_jinja, Placeholder):
            return dehydrated_jinja

        try:
            validate_user_template(dehydrated_jinja)
        except (jinja2.exceptions.TemplateSyntaxError, TemplateSecurityError) as exc:
            return InvalidJinja(detail=str(exc))

        if ctx.render_jinja:
            return render_user_template_sync(dehydrated_jinja, ctx.jinja_context)
        else:
            return ValidJinja(template=dehydrated_jinja)
    else:
        return TemplateNotFound()


@handler("workspace_variable")
def workspace_variable_handler(obj: dict[str, Any], ctx: HydrationContext) -> Any:
    if "variable_name" in obj:
        if isinstance(obj["variable_name"], dict):
            dehydrated_variable = _hydrate(obj["variable_name"], ctx)
        else:
            dehydrated_variable = obj["variable_name"]

        # If the result is a Placeholder, we should return it as is
        if isinstance(dehydrated_variable, Placeholder):
            return dehydrated_variable

        if not ctx.render_workspace_variables:
            return WorkspaceVariable(variable_name=dehydrated_variable)

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


def hydrate(
    obj: dict[str, Any], ctx: Optional[HydrationContext] = None
) -> dict[str, Any]:
    res: dict[str, Any] = _hydrate(obj, ctx)

    if _remove_value(res):
        res = {}

    return res


def _hydrate(obj: Any, ctx: Optional[HydrationContext] = None) -> Any:
    if ctx is None:
        ctx = HydrationContext()

    if isinstance(obj, dict) and "__prefect_kind" in obj:
        obj_dict: dict[str, Any] = obj
        prefect_kind = obj_dict["__prefect_kind"]
        return call_handler(prefect_kind, obj_dict, ctx)
    else:
        if isinstance(obj, dict):
            return {
                key: hydrated_value
                for key, value in cast(dict[str, Any], obj).items()
                if not _remove_value(hydrated_value := _hydrate(value, ctx))
            }
        elif isinstance(obj, list):
            return [
                hydrated_element
                for element in cast(list[Any], obj)
                if not _remove_value(hydrated_element := _hydrate(element, ctx))
            ]
        else:
            return obj
