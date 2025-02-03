import warnings
from typing import (
    Any,
    Callable,
    Generic,
    Optional,
    TypeVar,
    Union,
    cast,
    get_origin,
    overload,
)

from pydantic import (
    BaseModel,
    Secret,
    TypeAdapter,
    ValidationError,
)
from pydantic_core import to_jsonable_python
from typing_extensions import Literal

from prefect.utilities.dispatch import get_dispatch_key, lookup_type, register_base_type
from prefect.utilities.importtools import from_qualified_name, to_qualified_name
from prefect.utilities.names import obfuscate

D = TypeVar("D", bound=Any)
M = TypeVar("M", bound=BaseModel)
T = TypeVar("T", bound=Any)


def _reduce_model(self: BaseModel) -> tuple[Any, ...]:
    """
    Helper for serializing a cythonized model with cloudpickle.

    Keyword arguments can provide additional settings to the `json` call. Since
    `__reduce__` takes no arguments, these are set on the `__reduce_kwargs__` attr.
    """
    return (
        _unreduce_model,
        (
            to_qualified_name(type(self)),
            self.model_dump_json(**getattr(self, "__reduce_kwargs__", {})),
        ),
    )


def _unreduce_model(model_name: str, json: str) -> Any:
    """Helper for restoring model after serialization"""
    model = from_qualified_name(model_name)
    return model.model_validate_json(json)


@overload
def add_cloudpickle_reduction(__model_cls: type[M]) -> type[M]: ...


@overload
def add_cloudpickle_reduction(
    __model_cls: None = None, **kwargs: Any
) -> Callable[[type[M]], type[M]]: ...


def add_cloudpickle_reduction(
    __model_cls: Optional[type[M]] = None, **kwargs: Any
) -> Union[type[M], Callable[[type[M]], type[M]]]:
    """
    Adds a `__reducer__` to the given class that ensures it is cloudpickle compatible.

    Workaround for issues with cloudpickle when using cythonized pydantic which
    throws exceptions when attempting to pickle the class which has "compiled"
    validator methods dynamically attached to it.

    We cannot define this utility in the model class itself because the class is the
    type that contains unserializable methods.

    Any model using some features of Pydantic (e.g. `Path` validation) with a Cython
    compiled Pydantic installation may encounter pickling issues.

    See related issue at https://github.com/cloudpipe/cloudpickle/issues/408
    """
    if __model_cls:
        __model_cls.__reduce__ = _reduce_model
        setattr(__model_cls, "__reduce_kwargs__", kwargs)
        return __model_cls

    def reducer_with_kwargs(__model_cls: type[M]) -> type[M]:
        return add_cloudpickle_reduction(__model_cls, **kwargs)

    return reducer_with_kwargs


def get_class_fields_only(model: type[BaseModel]) -> set[str]:
    """
    Gets all the field names defined on the model class but not any parent classes.
    Any fields that are on the parent but redefined on the subclass are included.
    """
    subclass_class_fields = set(model.__annotations__.keys())
    parent_class_fields: set[str] = set()

    for base in model.__class__.__bases__:
        if issubclass(base, BaseModel):
            parent_class_fields.update(base.__annotations__.keys())

    return (subclass_class_fields - parent_class_fields) | (
        subclass_class_fields & parent_class_fields
    )


def add_type_dispatch(model_cls: type[M]) -> type[M]:
    """
    Extend a Pydantic model to add a 'type' field that is used as a discriminator field
    to dynamically determine the subtype that when deserializing models.

    This allows automatic resolution to subtypes of the decorated model.

    If a type field already exists, it should be a string literal field that has a
    constant value for each subclass. The default value of this field will be used as
    the dispatch key.

    If a type field does not exist, one will be added. In this case, the value of the
    field will be set to the value of the `__dispatch_key__`. The base class should
    define a `__dispatch_key__` class method that is used to determine the unique key
    for each subclass. Alternatively, each subclass can define the `__dispatch_key__`
    as a string literal.

    The base class must not define a 'type' field. If it is not desirable to add a field
    to the model and the dispatch key can be tracked separately, the lower level
    utilities in `prefect.utilities.dispatch` should be used directly.
    """
    defines_dispatch_key = hasattr(
        model_cls, "__dispatch_key__"
    ) or "__dispatch_key__" in getattr(model_cls, "__annotations__", {})

    defines_type_field = "type" in model_cls.model_fields

    if not defines_dispatch_key and not defines_type_field:
        raise ValueError(
            f"Model class {model_cls.__name__!r} does not define a `__dispatch_key__` "
            "or a type field. One of these is required for dispatch."
        )

    elif not defines_dispatch_key and defines_type_field:
        field_type_annotation = model_cls.model_fields["type"].annotation
        if field_type_annotation is not str and field_type_annotation is not None:
            raise TypeError(
                f"Model class {model_cls.__name__!r} defines a 'type' field with "
                f"type {field_type_annotation.__name__!r} but it must be 'str'."
            )

        # Set the dispatch key to retrieve the value from the type field
        @classmethod
        def dispatch_key_from_type_field(cls: type[M]) -> str:
            return cls.model_fields["type"].default

        setattr(model_cls, "__dispatch_key__", dispatch_key_from_type_field)

    else:
        raise ValueError(
            f"Model class {model_cls.__name__!r} defines a `__dispatch_key__` "
            "and a type field. Only one of these may be defined for dispatch."
        )

    cls_init = model_cls.__init__
    cls_new = model_cls.__new__

    def __init__(__pydantic_self__: M, **data: Any) -> None:
        type_string = (
            get_dispatch_key(__pydantic_self__)
            if type(__pydantic_self__) is not model_cls
            else "__base__"
        )
        data.setdefault("type", type_string)
        cls_init(__pydantic_self__, **data)

    def __new__(cls: type[M], **kwargs: Any) -> M:
        if "type" in kwargs:
            try:
                subcls = lookup_type(cls, dispatch_key=kwargs["type"])
            except KeyError as exc:
                raise ValidationError.from_exception_data(
                    title=cls.__name__,
                    line_errors=[{"type": str(exc), "input": kwargs["type"]}],
                    input_type="python",
                )
            return cls_new(subcls)
        else:
            return cls_new(cls)

    model_cls.__init__ = __init__
    model_cls.__new__ = __new__

    register_base_type(model_cls)

    return model_cls


class PartialModel(Generic[M]):
    """
    A utility for creating a Pydantic model in several steps.

    Fields may be set at initialization, via attribute assignment, or at finalization
    when the concrete model is returned.

    Pydantic validation does not occur until finalization.

    Each field can only be set once and a `ValueError` will be raised on assignment if
    a field already has a value.

    Example:
        >>> class MyModel(BaseModel):
        >>>     x: int
        >>>     y: str
        >>>     z: float
        >>>
        >>> partial_model = PartialModel(MyModel, x=1)
        >>> partial_model.y = "two"
        >>> model = partial_model.finalize(z=3.0)
    """

    def __init__(self, __model_cls: type[M], **kwargs: Any) -> None:
        self.fields = kwargs
        # Set fields first to avoid issues if `fields` is also set on the `model_cls`
        # in our custom `setattr` implementation.
        self.model_cls = __model_cls

        for name in kwargs.keys():
            self.raise_if_not_in_model(name)

    def finalize(self, **kwargs: Any) -> M:
        for name in kwargs.keys():
            self.raise_if_already_set(name)
            self.raise_if_not_in_model(name)
        return self.model_cls(**self.fields, **kwargs)

    def raise_if_already_set(self, name: str) -> None:
        if name in self.fields:
            raise ValueError(f"Field {name!r} has already been set.")

    def raise_if_not_in_model(self, name: str) -> None:
        if name not in self.model_cls.model_fields:
            raise ValueError(f"Field {name!r} is not present in the model.")

    def __setattr__(self, __name: str, __value: Any) -> None:
        if __name in {"fields", "model_cls"}:
            return super().__setattr__(__name, __value)

        self.raise_if_already_set(__name)
        self.raise_if_not_in_model(__name)
        self.fields[__name] = __value

    def __repr__(self) -> str:
        dsp_fields = ", ".join(
            f"{key}={repr(value)}" for key, value in self.fields.items()
        )
        return f"PartialModel(cls={self.model_cls.__name__}, {dsp_fields})"


def custom_pydantic_encoder(
    type_encoders: dict[Any, Callable[[type[Any]], Any]], obj: Any
) -> Any:
    # Check the class type and its superclasses for a matching encoder
    for base in obj.__class__.__mro__[:-1]:
        try:
            encoder = type_encoders[base]
        except KeyError:
            continue

        return encoder(obj)
    else:  # We have exited the for loop without finding a suitable encoder
        if isinstance(obj, BaseModel):
            return obj.model_dump(mode="json")
        else:
            return to_jsonable_python(obj)


def parse_obj_as(
    type_: type[T],
    data: Any,
    mode: Literal["python", "json", "strings"] = "python",
) -> T:
    """Parse a given data structure as a Pydantic model via `TypeAdapter`.

    Read more about `TypeAdapter` [here](https://docs.pydantic.dev/latest/concepts/type_adapter/).

    Args:
        type_: The type to parse the data as.
        data: The data to be parsed.
        mode: The mode to use for parsing, either `python`, `json`, or `strings`.
            Defaults to `python`, where `data` should be a Python object (e.g. `dict`).

    Returns:
        The parsed `data` as the given `type_`.


    Example:
        Basic Usage of `parse_as`
        ```python
        from prefect.utilities.pydantic import parse_as
        from pydantic import BaseModel

        class ExampleModel(BaseModel):
            name: str

        # parsing python objects
        parsed = parse_as(ExampleModel, {"name": "Marvin"})
        assert isinstance(parsed, ExampleModel)
        assert parsed.name == "Marvin"

        # parsing json strings
        parsed = parse_as(
            list[ExampleModel],
            '[{"name": "Marvin"}, {"name": "Arthur"}]',
            mode="json"
        )
        assert all(isinstance(item, ExampleModel) for item in parsed)
        assert parsed[0].name == "Marvin"
        assert parsed[1].name == "Arthur"

        # parsing raw strings
        parsed = parse_as(int, '123', mode="strings")
        assert isinstance(parsed, int)
        assert parsed == 123
        ```

    """
    adapter = TypeAdapter(type_)

    origin: Optional[Any] = get_origin(type_)
    if origin is list and isinstance(data, dict):
        values_dict: dict[Any, Any] = data
        data = next(iter(values_dict.values()))

    parser: Callable[[Any], T] = getattr(adapter, f"validate_{mode}")

    return parser(data)


def handle_secret_render(value: object, context: dict[str, Any]) -> object:
    if hasattr(value, "get_secret_value"):
        return (
            cast(Secret[object], value).get_secret_value()
            if context.get("include_secrets", False)
            else obfuscate(value)
        )
    elif isinstance(value, BaseModel):
        return value.model_dump(context=context)
    return value


def __getattr__(name: str) -> Any:
    """
    Handles imports from this module that are deprecated.
    """

    if name == "JsonPatch":
        warnings.warn(
            "JsonPatch is deprecated and will be removed after March 2025. "
            "Please use `JsonPatch` from the `jsonpatch` package instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        from ._deprecated import JsonPatch

        return JsonPatch
    else:
        raise AttributeError(f"module '{__name__}' has no attribute '{name}'")
