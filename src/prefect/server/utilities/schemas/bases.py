import datetime
import json
import os
from functools import partial
from typing import Any, Dict, Generator, Optional, Set, Type, TypeVar
from uuid import UUID, uuid4

import orjson
import pendulum
from packaging.version import Version

from prefect._internal.pydantic import HAS_PYDANTIC_V2

if HAS_PYDANTIC_V2:
    import pydantic.v1 as pydantic
    from pydantic.v1 import BaseModel, Field, SecretField
    from pydantic.v1.json import custom_pydantic_encoder
else:
    import pydantic
    from pydantic import BaseModel, Field, SecretField
    from pydantic.json import custom_pydantic_encoder

from prefect.server.utilities.schemas.fields import DateTimeTZ
from prefect.server.utilities.schemas.serializers import orjson_dumps_extra_compatible

T = TypeVar("T")
B = TypeVar("B", bound=BaseModel)


def get_class_fields_only(model: Type[pydantic.BaseModel]) -> set:
    """
    Gets all the field names defined on the model class but not any parent classes.
    Any fields that are on the parent but redefined on the subclass are included.
    """
    subclass_class_fields = set(model.__annotations__.keys())
    parent_class_fields = set()

    for base in model.__class__.__bases__:
        if issubclass(base, pydantic.BaseModel):
            parent_class_fields.update(base.__annotations__.keys())

    return (subclass_class_fields - parent_class_fields) | (
        subclass_class_fields & parent_class_fields
    )


class PrefectBaseModel(BaseModel):
    """A base pydantic.BaseModel for all Prefect schemas and pydantic models.

    As the basis for most Prefect schemas, this base model usually ignores extra
    fields that are passed to it at instantiation. Because adding new fields to
    API payloads is not considered a breaking change, this ensures that any
    Prefect client loading data from a server running a possibly-newer version
    of Prefect will be able to process those new fields gracefully. However,
    when PREFECT_TEST_MODE is on, extra fields are forbidden in order to catch
    subtle unintentional testing errors.
    """

    class Config:
        # extra attributes are forbidden in order to raise meaningful errors for
        # bad API payloads
        # We cannot load this setting through the normal pattern due to circular
        # imports; instead just check if its a truthy setting directly
        if os.getenv("PREFECT_TEST_MODE", "0").lower() in ["1", "true"]:
            extra = "forbid"
        else:
            extra = "ignore"

        json_encoders = {
            # Uses secret fields and strange logic to avoid a circular import error
            # for Secret dict in prefect.blocks.fields
            SecretField: lambda v: v.dict() if getattr(v, "dict", None) else str(v)
        }

        pydantic_version = getattr(pydantic, "__version__", None)
        if pydantic_version is not None and Version(pydantic_version) >= Version(
            "1.9.2"
        ):
            copy_on_model_validation = "none"
        else:
            copy_on_model_validation = False

        # Use orjson for serialization
        json_loads = orjson.loads
        json_dumps = orjson_dumps_extra_compatible

    def _reset_fields(self) -> Set[str]:
        """A set of field names that are reset when the PrefectBaseModel is copied.
        These fields are also disregarded for equality comparisons.
        """
        return set()

    def __eq__(self, other: Any) -> bool:
        """Equaltiy operator that ignores the resettable fields of the PrefectBaseModel.

        NOTE: this equality operator will only be applied if the PrefectBaseModel is
        the left-hand operand. This is a limitation of Python.
        """
        copy_dict = self.dict(exclude=self._reset_fields())
        if isinstance(other, PrefectBaseModel):
            return copy_dict == other.dict(exclude=other._reset_fields())
        if isinstance(other, BaseModel):
            return copy_dict == other.dict()
        else:
            return copy_dict == other

    def json(self, *args, include_secrets: bool = False, **kwargs) -> str:
        """
        Returns a representation of the model as JSON.

        If `include_secrets=True`, then `SecretStr` and `SecretBytes` objects are
        fully revealed. Otherwise they are obfuscated.

        """
        if include_secrets:
            if "encoder" in kwargs:
                raise ValueError(
                    "Alternative encoder provided; can not set encoder for"
                    " SecretFields."
                )
            kwargs["encoder"] = partial(
                custom_pydantic_encoder,
                {SecretField: lambda v: v.get_secret_value() if v else None},
            )
        return super().json(*args, **kwargs)

    def dict(
        self, *args, shallow: bool = False, json_compatible: bool = False, **kwargs
    ) -> dict:
        """Returns a representation of the model as a Python dictionary.

        For more information on this distinction please see
        https://pydantic-docs.helpmanual.io/usage/exporting_models/#dictmodel-and-iteration


        Args:
            shallow (bool, optional): If True (default), nested Pydantic fields
                are also coerced to dicts. If false, they are left as Pydantic
                models.
            json_compatible (bool, optional): if True, objects are converted
                into json-compatible representations, similar to calling
                `json.loads(self.json())`. Not compatible with shallow=True.

        Returns:
            dict
        """

        if json_compatible and shallow:
            raise ValueError(
                "`json_compatible` can only be applied to the entire object."
            )

        # return a json-compatible representation of the object
        elif json_compatible:
            return json.loads(self.json(*args, **kwargs))

        # if shallow wasn't requested, return the standard pydantic behavior
        elif not shallow:
            return super().dict(*args, **kwargs)

        # if no options were requested, return simple dict transformation
        # to apply shallow conversion
        elif not args and not kwargs:
            return dict(self)

        # if options like include/exclude were provided, perform
        # a full dict conversion then overwrite with any shallow
        # differences
        else:
            deep_dict = super().dict(*args, **kwargs)
            shallow_dict = dict(self)
            for k, v in list(deep_dict.items()):
                if isinstance(v, dict) and isinstance(shallow_dict[k], BaseModel):
                    deep_dict[k] = shallow_dict[k]
            return deep_dict

    def copy(
        self: T,
        *,
        update: Optional[Dict] = None,
        reset_fields: bool = False,
        **kwargs: Any,
    ) -> T:
        """
        Duplicate a model.

        Args:
            update: values to change/add to the model copy
            reset_fields: if True, reset the fields specified in `self._reset_fields`
                to their default value on the new model
            kwargs: kwargs to pass to `pydantic.BaseModel.copy`

        Returns:
            A new copy of the model
        """
        if reset_fields:
            update = update or dict()
            for field in self._reset_fields():
                update.setdefault(field, self.__fields__[field].get_default())
        return super().copy(update=update, **kwargs)

    def __rich_repr__(self):
        # Display all of the fields in the model if they differ from the default value
        for name, field in self.__fields__.items():
            value = getattr(self, name)

            # Simplify the display of some common fields
            if field.type_ == UUID and value:
                value = str(value)
            elif (
                isinstance(field.type_, datetime.datetime)
                and name == "timestamp"
                and value
            ):
                value = pendulum.instance(value).isoformat()
            elif isinstance(field.type_, datetime.datetime) and value:
                value = pendulum.instance(value).diff_for_humans()

            yield name, value, field.get_default()


class IDBaseModel(PrefectBaseModel):
    """
    A PrefectBaseModel with an auto-generated UUID ID value.

    The ID is reset on copy() and not included in equality comparisons.
    """

    id: UUID = Field(default_factory=uuid4)

    def _reset_fields(self) -> Set[str]:
        return super()._reset_fields().union({"id"})


class ORMBaseModel(IDBaseModel):
    """
    A PrefectBaseModel with an auto-generated UUID ID value and created /
    updated timestamps, intended for compatibility with our standard ORM models.

    The ID, created, and updated fields are reset on copy() and not included in
    equality comparisons.
    """

    class Config:
        orm_mode = True

    created: Optional[DateTimeTZ] = Field(default=None, repr=False)
    updated: Optional[DateTimeTZ] = Field(default=None, repr=False)

    def _reset_fields(self) -> Set[str]:
        return super()._reset_fields().union({"created", "updated"})


class ActionBaseModel(PrefectBaseModel):
    class Config:
        extra = "forbid"

    def __iter__(self):
        # By default, `pydantic.BaseModel.__iter__` yields from `self.__dict__` directly
        # instead  of going through `_iter`. We want tor retain our custom logic in
        # `_iter` during `dict(model)` calls which is what Pydantic uses for
        # `parse_obj(model)`
        yield from self._iter(to_dict=True)

    def _iter(self, *args, **kwargs) -> Generator[tuple, None, None]:
        # Drop fields that are marked as `ignored` from json and dictionary outputs
        exclude = kwargs.pop("exclude", None) or set()
        for name, field in self.__fields__.items():
            if field.field_info.extra.get("ignored"):
                exclude.add(name)

        return super()._iter(*args, **kwargs, exclude=exclude)
