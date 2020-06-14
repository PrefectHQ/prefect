import datetime
import json
import sys
import types
from typing import Any, Callable, List, Tuple, Union, cast, TypeVar

import pendulum
import pydantic

import prefect


FunctionReference = Union['Serializable', Callable, str]


def to_qualified_name(obj: Any) -> str:
    """
    Given an object, returns its fully-qualified name, meaning a string that represents its
    Python import path

    Args:
        - obj (Any): an importable Python object

    Returns:
        - str: the qualified name
    """
    return obj.__module__ + "." + obj.__qualname__


def from_qualified_name(obj_str: str) -> Any:
    """
    Retrives an object from a fully qualified string path. 
    IMPORTANT: No code is imported or executed by this function. The object
    must already be imported and available at the path.

    Args:
        - obj_str (str): the qualified path of the object

    Returns:
        - Any: the object retrieved from the qualified path

    Raises:
        - ValueError: if the object could not be loaded from the supplied path. Note that
            this function will not import objects; they must be imported in advance.
    """

    path_components = obj_str.split(".")
    try:
        for i in range(len(path_components), 0, -1):
            module_path = ".".join(path_components[:i])
            if module_path in sys.modules:
                obj = sys.modules[module_path]
                for p in path_components[i:]:
                    obj = getattr(obj, p)
                return obj
    except Exception:
        pass  # exceptions are raised by the catch-all at the end
    raise ValueError(f"Couldn't load \"{obj_str}\"; maybe it hasn't been imported yet?")


def as_pendulum(value: Union[str, datetime.datetime]) -> pendulum.DateTime:
    if isinstance(value, datetime.datetime):
        return pendulum.instance(value).in_tz("UTC")
    else:
        return pendulum.parse(value).in_tz("UTC")


def apply_fn_to_field(field: pydantic.Field, field_value: Any, fn: Callable) -> Any:
    """
    A convenience function that helps applying transformations to Pydantic fields
    that may be inside containers (shape > 1)
    """
    if field.shape == 1:
        return fn(field_value)
    else:
        return type(field_value)(fn(v) for v in field_value)


class PrefectModel(pydantic.BaseModel):
    """
    A base Pydantic model that has extensions for working with
    certain kinds of types
    """

    class Config:
        json_encoders = {
            pendulum.DateTime: str,
            pendulum.Date: str,
            pendulum.Time: str,
            pendulum.Duration: lambda x: str(x.total_seconds()),
            pendulum.Period: lambda x: str(x.total_seconds()),
            types.FunctionType: to_qualified_name,
            types.MethodType: to_qualified_name,
        }

    @pydantic.root_validator(pre=True)
    def _convert_types(cls, model_values: dict) -> dict:
        """
        A globally-applied Pydantic validator that:
            - converts datetimes to pendulum instances
            - converts Serializable classes to objects

        Args:
            - model_values (dict): the raw model values

        Returns:
            - dict: the modified model values 
        """
        for field_name, field_value in list(model_values.items()):
            field = cast(pydantic.Field, cls.__fields__.get(field_name))

            # if the field isn't interesting, keep going
            if field is None or field_value is None:
                continue

            # convert datetimes to pendulum.DateTime in UTC
            elif isinstance(field.type_, type) and issubclass(
                field.type_, datetime.datetime
            ):
                model_values[field_name] = apply_fn_to_field(
                    field, field_value, as_pendulum
                )

            # convert FunctionReferences to functions if possible
            elif (field.outer_type_ is FunctionReference) and isinstance(
                field_value, str
            ):
                try:
                    model_values[field_name] = apply_fn_to_field(
                        field, field_value, lambda v: from_qualified_name(v)
                    )
                # if the access fails, continue
                except ValueError:
                    continue

        return model_values


class Metadata(PrefectModel):
    class Config:
        extra = "allow"

    prefect_version: str = None
    type_mro: List[str] = pydantic.Field(default_factory=list)

    @pydantic.validator("prefect_version", pre=True, always=True)
    def _set_prefect_version(cls, value: Any) -> str:
        # this is called on initialization and the __version__ attribute
        # may not exist yet
        return value or getattr(prefect, '__version__', None)


class Serializable(PrefectModel):

    metadata: Metadata = pydantic.Field(default_factory=Metadata)

    @pydantic.validator("metadata", always=True)
    def _set_type_mro(cls, value: Any) -> List[str]:
        if value.type_mro == []:
            # prepare type metadata
            for i, o in enumerate(cls.mro()):
                # stop once the mro is uninteresting
                if i > 0 and o is Serializable:
                    break
                value.type_mro.append(to_qualified_name(o))

        return value

    @classmethod
    def _from_object(cls, obj: Any, **kwargs) -> "Serializable":
        init_kwargs = {f: getattr(obj, f) for f in cls.__fields__ if hasattr(obj, f)}
        init_kwargs.update(kwargs)

        metadata = init_kwargs.setdefault("metadata", {})
        if isinstance(metadata, Metadata):
            metadata = metadata.dict()
        else:
            # copy to avoid mutating the object
            metadata = metadata.copy()

        # prepare type metadata
        type_mro = []
        for i, o in enumerate(type(obj).mro()):
            # stop once the mro is uninteresting
            if i > 0 and o in (Serializable, object):
                break
            type_mro.append(to_qualified_name(o))
        metadata["type_mro"] = type_mro

        # reassign metadata
        init_kwargs["metadata"] = metadata

        return cls(**init_kwargs)

    def _to_object(self, **kwargs: Any) -> Any:
        init_data = self.dict(
            exclude={"metadata", "type"}, exclude_unset=True, exclude_defaults=True,
        )
        init_data.update(kwargs)

        for k in init_data:
            model_type = self.__fields__[k].type_
            if isinstance(model_type, type) and issubclass(model_type, Serializable):
                init_data[k] = apply_fn_to_field(
                    self.__fields__[k],
                    getattr(self, k),
                    lambda o: o._to_object() if isinstance(o, Serializable) else o,
                )

        cls = self._get_obj_class()
        return cls(**init_data)

    def _get_obj_class(self) -> Any:
        cls = None
        for name in self.metadata.type_mro:
            try:
                cls = from_qualified_name(name)
                break
            except ValueError:
                continue
        if cls is None:
            raise ValueError("Could not load object class.")
        return cls


class PolymorphicSerializable(Serializable):
    """
    PolymorphicSerializable is intended to be used when one large Serializable
    contains many optional fields. It does not export fields that have their default
    value.
    """

    type: str = None

    def __repr_args__(self) -> str:
        return list(self.dict().items())

    def dict(self, **kwargs):
        kwargs["exclude_defaults"] = True
        return super().dict(**kwargs)

    @classmethod
    def _from_object(cls, obj: Any, **kwargs: Any) -> "PolymorphicSerializable":
        kwargs.setdefault("type", type(obj).__name__)
        return super()._from_object(obj, **kwargs)

