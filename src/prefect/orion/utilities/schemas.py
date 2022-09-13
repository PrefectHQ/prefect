"""
Utilities for creating and working with Orion API schemas.
"""
import copy
import datetime
import json
import os
from functools import partial
from typing import Any, Dict, List, Set, Type, TypeVar
from uuid import UUID, uuid4

import orjson
import pendulum
import pydantic
from packaging.version import Version
from pydantic import BaseModel, Field, SecretBytes, SecretStr
from pydantic.json import custom_pydantic_encoder

T = TypeVar("T")


class DateTimeTZ(pendulum.DateTime):
    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v):
        if isinstance(v, str):
            return pendulum.parse(v)
        elif isinstance(v, datetime.datetime):
            return pendulum.instance(v)
        else:
            raise ValueError("Unrecognized datetime.")


B = TypeVar("B", bound=BaseModel)


def pydantic_subclass(
    base: Type[B],
    name: str = None,
    include_fields: List[str] = None,
    exclude_fields: List[str] = None,
) -> Type[B]:
    """Creates a subclass of a Pydantic model that excludes certain fields.
    Pydantic models use the __fields__ attribute of their parent class to
    determine inherited fields, so to create a subclass without fields, we
    temporarily remove those fields from the parent __fields__ and use
    `create_model` to dynamically generate a new subclass.

    Args:
        base (pydantic.BaseModel): a Pydantic BaseModel
        name (str): a name for the subclass. If not provided
            it will have the same name as the base class.
        include_fields (List[str]): a set of field names to include.
            If `None`, all fields are included.
        exclude_fields (List[str]): a list of field names to exclude.
            If `None`, no fields are excluded.

    Returns:
        pydantic.BaseModel: a new model subclass that contains only the specified fields.

    Example:
        To subclass a model with a subset of fields:
        ```python
        class Parent(pydantic.BaseModel):
            x: int = 1
            y: int = 2

        Child = pydantic_subclass(Parent, 'Child', exclude_fields=['y'])
        assert hasattr(Child(), 'x')
        assert not hasattr(Child(), 'y')
        ```

        To subclass a model with a subset of fields but include a new field:
        ```python
        class Child(pydantic_subclass(Parent, exclude_fields=['y'])):
            z: int = 3

        assert hasattr(Child(), 'x')
        assert not hasattr(Child(), 'y')
        assert hasattr(Child(), 'z')
        ```
    """

    # collect field names
    field_names = set(include_fields or base.__fields__)
    excluded_fields = set(exclude_fields or [])
    if field_names.difference(base.__fields__):
        raise ValueError(
            "Included fields not found on base class: "
            f"{field_names.difference(base.__fields__)}"
        )
    elif excluded_fields.difference(base.__fields__):
        raise ValueError(
            "Excluded fields not found on base class: "
            f"{excluded_fields.difference(base.__fields__)}"
        )
    field_names.difference_update(excluded_fields)

    # create a new class that inherits from `base` but only contains the specified
    # pydantic __fields__
    new_cls = type(
        name or base.__name__,
        (base,),
        {
            "__fields__": {
                k: copy.copy(v) for k, v in base.__fields__.items() if k in field_names
            }
        },
    )

    return new_cls


def orjson_dumps(v: Any, *, default: Any) -> str:
    """
    Utility for dumping a value to JSON using orjson.

    orjson.dumps returns bytes, to match standard json.dumps we need to decode.
    """
    return orjson.dumps(v, default=default).decode()


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

        pydantic_version = getattr(pydantic, "__version__", None)
        if pydantic_version is not None and Version(pydantic_version) >= Version(
            "1.9.2"
        ):
            copy_on_model_validation = "none"
        else:
            copy_on_model_validation = False

        # Use orjson for serialization
        json_loads = orjson.loads
        json_dumps = orjson_dumps

    @classmethod
    def subclass(
        cls: Type[B],
        name: str = None,
        include_fields: List[str] = None,
        exclude_fields: List[str] = None,
    ) -> Type[B]:
        """Creates a subclass of this model containing only the specified fields.

        See `pydantic_subclass()`.

        Args:
            name (str, optional): a name for the subclass
            include_fields (List[str], optional): fields to include
            exclude_fields (List[str], optional): fields to exclude

        Returns:
            BaseModel: a subclass of this class
        """
        return pydantic_subclass(
            base=cls,
            name=name,
            include_fields=include_fields,
            exclude_fields=exclude_fields,
        )

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
                    "Alternative encoder provided; can not set encoder for SecretStr and SecretBytes."
                )
            kwargs["encoder"] = partial(
                custom_pydantic_encoder,
                {
                    SecretStr: lambda v: v.get_secret_value() if v else None,
                    SecretBytes: lambda v: v.get_secret_value() if v else None,
                },
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
        self: T, *, update: Dict = None, reset_fields: bool = False, **kwargs: Any
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

    created: DateTimeTZ = Field(None, repr=False)
    updated: DateTimeTZ = Field(None, repr=False)

    def _reset_fields(self) -> Set[str]:
        return super()._reset_fields().union({"created", "updated"})
