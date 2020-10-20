import base64
import datetime
import inspect
import json
import sys
import types
from typing import Any, Callable, List

import marshmallow_oneofschema
import pendulum
from marshmallow import (
    EXCLUDE,
    Schema,
    SchemaOpts,
    ValidationError,
    fields,
    missing,
    post_dump,
    post_load,
    pre_load,
)

import prefect


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
    Retrives an object from a fully qualified string path. The object must be
    imported in advance.

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
    raise ValueError(
        "Couldn't load \"{}\"; maybe it hasn't been imported yet?".format(obj_str)
    )


class ObjectSchemaOptions(SchemaOpts):
    def __init__(self, meta: Any, **kwargs: Any) -> None:
        super().__init__(meta, **kwargs)
        self.object_class = getattr(meta, "object_class", None)
        self.exclude_fields = getattr(meta, "exclude_fields", None) or []
        self.unknown = getattr(meta, "unknown", EXCLUDE)


class ObjectSchema(Schema):
    """
    This Marshmallow Schema automatically instantiates an object whose type is indicated by the
    `object_class` attribute of the class `Meta`. All deserialized fields are passed to the
    constructor's `__init__()` unless the name of the field appears in `Meta.exclude_fields`.
    """

    OPTIONS_CLASS = ObjectSchemaOptions

    class Meta:
        object_class = None  # type: type
        exclude_fields = []  # type: List[str]
        unknown = EXCLUDE

    @pre_load
    def _remove_version(self, data: dict, **kwargs: Any) -> dict:
        """
        Removes a __version__ field from the data, if present.

        Args:
            - data (dict): the serialized data

        Returns:
            - dict: the data dict, without its __version__ field
        """
        # don't mutate data
        data = data.copy()
        data.pop("__version__", None)
        return data

    @post_dump
    def _add_version(self, data: dict, **kwargs: Any) -> dict:
        """
        Adds a __version__ field to the data, if not already provided.

        Args:
            - data (dict): the serialized data

        Returns:
            - dict: the data dict, with an additional __version__ field
        """
        # don't mutate data
        data = data.copy()
        data.setdefault("__version__", prefect.__version__)
        return data

    def load(self, data: dict, create_object: bool = True, **kwargs: Any) -> Any:
        """
        Loads an object by first retrieving the appropate schema version (based on the data's
        __version__ key).

        Args:
            - data (dict): the serialized data
            - create_object (bool): if True, an instantiated object will be returned. Otherwise,
                the deserialized data dict will be returned.
            - **kwargs (Any): additional keyword arguments for the load() method

        Returns:
            - Any: the deserialized object or data
        """
        self.context.setdefault("create_object", create_object)
        return super().load(data, **kwargs)

    @post_load
    def create_object(self, data: dict, **kwargs: Any) -> Any:
        """
        By default, returns an instantiated object using the ObjectSchema's `object_class`.
        Otherwise, returns a data dict.

        Args:
            - data (dict): the deserialized data

        Returns:
            - Any: an instantiated object, if `create_object` is found in context; otherwise,
                the data dict
        """
        if self.context.get("create_object", True):
            object_class = self.opts.object_class
            if object_class is not None:
                if isinstance(object_class, types.FunctionType):
                    object_class = object_class()
                init_data = {
                    k: v for k, v in data.items() if k not in self.opts.exclude_fields
                }
                return object_class(**init_data)
        return data


class JSONCompatible(fields.Field):
    """
    Field that ensures its values are JSON-compatible during serialization and deserialization

    Args:
        - *args (Any): the arguments accepted by `marshmallow.Field`
        - **kwargs (Any): the keyword arguments accepted by `marshmallow.Field`
    """

    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)
        self.validators.insert(0, self._validate_json)

    def _serialize(self, value, attr, obj, **kwargs):  # type: ignore
        try:
            json.dumps(value)
        except TypeError:
            raise ValidationError(
                "When running with Prefect Cloud/Server, values for "
                f"`{type(obj).__name__}.{attr}` must be JSON compatible. "
                f"Unable to serialize `{value!r}`."
            ) from None
        return super()._serialize(value, attr, obj, **kwargs)

    def _validate_json(self, value: Any) -> None:
        try:
            json.dumps(value)
        except TypeError:
            raise ValidationError(
                f"Values must be JSON compatible, got `{value!r}`"
            ) from None


class Nested(fields.Nested):
    """
    An extension of the Marshmallow Nested field that allows the value to be selected
    via a value_selection_fn.

    Note that because the value_selection_fn is always called, users must return
    `marshmallow.missing` if they don't want this field included in the resulting serialized
    object.

    Args:
        - nested (type): the nested schema class
        - value_selection_fn (Callable): a function that is called whenever the object is
            serialized, to retrieve the object (if not available as a simple attribute of the
            parent schema)
        - **kwargs (Any): the keyword arguments accepted by `marshmallow.Field`
    """

    def __init__(self, nested: type, value_selection_fn: Callable, **kwargs: Any):
        super().__init__(nested=nested, **kwargs)
        self.value_selection_fn = value_selection_fn

        if value_selection_fn is not None:
            self._CHECK_ATTRIBUTE = False

    def _serialize(self, value, attr, obj, **kwargs):  # type: ignore
        if self.value_selection_fn is not None:
            self.context.update(value=value, attr=attr)
            value = self.value_selection_fn(obj, self.context)
        if value is missing:
            return value
        return super()._serialize(value, attr, obj, **kwargs)


class OneOfSchema(marshmallow_oneofschema.OneOfSchema):
    """
    A subclass of marshmallow_oneofschema.OneOfSchema that excludes unknown fields
    """

    class Meta:
        unknown = EXCLUDE


class Bytes(fields.Field):
    """
    A Marshmallow Field that serializes bytes to a base64-encoded string, and deserializes
    a base64-encoded string to bytes.

    Args:
        - *args (Any): the arguments accepted by `marshmallow.Field`
        - **kwargs (Any): the keyword arguments accepted by `marshmallow.Field`
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)

    def _serialize(self, value, attr, obj, **kwargs):  # type: ignore
        if value is not None:
            return base64.b64encode(value).decode("utf-8")

    def _deserialize(self, value, attr, data, **kwargs):  # type: ignore
        if value is not None:
            return base64.b64decode(value)


class UUID(fields.UUID):
    """
    Replacement for fields.UUID that performs validation but returns string objects,
    not UUIDs

    Args:
        - *args (Any): the arguments accepted by `marshmallow.Field`
        - **kwargs (Any): the keyword arguments accepted by `marshmallow.Field`
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)

    def _serialize(self, value, attr, obj, **kwargs):  # type: ignore
        return super()._serialize(value, attr, obj, **kwargs)

    def _deserialize(self, value, attr, data, **kwargs):  # type: ignore
        return str(super()._deserialize(value, attr, data, **kwargs))


class DateTimeTZ(fields.DateTime):
    """
    Replacement for fields.DateTime that stores the time zone (not the time zone offset like
    fields.LocalDateTime)

    Args:
        - *args (Any): the arguments accepted by `marshmallow.Field`
        - **kwargs (Any): the keyword arguments accepted by `marshmallow.Field`
    """

    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)

    def _serialize(self, value, attr, obj, **kwargs):  # type: ignore
        if value is not None:
            dt = pendulum.instance(value)
            return dict(dt=dt.naive().to_iso8601_string(), tz=dt.tzinfo.name)

    def _deserialize(self, value, attr, data, **kwargs):  # type: ignore
        if value is not None:
            return pendulum.parse(value["dt"], tz=value["tz"])


class FunctionReference(fields.Field):
    """
    Field that stores a reference to a function as a string and reloads it when
    deserialized.

    Args:
        - valid_functions (List[Callable]): a list of functions that will be serialized as string
            references
        - reject_invalid (bool): if True, functions not in `valid_functions` will be rejected.
            If False, any value will be allowed, but only functions in `valid_functions` will
            be deserialized.
        - **kwargs (Any): the keyword arguments accepted by `marshmallow.Field`

    """

    def __init__(
        self, valid_functions: list, reject_invalid: bool = True, **kwargs: Any
    ):
        self.valid_functions = {to_qualified_name(f): f for f in valid_functions}
        self.reject_invalid = reject_invalid
        super().__init__(**kwargs)

    def _serialize(self, value, attr, obj, **kwargs):  # type: ignore
        if value is None and self.allow_none:
            return None
        elif value not in self.valid_functions.values() and self.reject_invalid:
            raise ValidationError("Invalid function reference: {}".format(value))
        return to_qualified_name(value)

    def _deserialize(self, value, attr, data, **kwargs):  # type: ignore
        if value is None and self.allow_none:
            return None
        elif value not in self.valid_functions and self.reject_invalid:
            raise ValidationError("Invalid function reference: {}".format(value))
        return self.valid_functions.get(value, value)


class StatefulFunctionReference(fields.Field):
    """

    Field that stores a reference to a function as a string and reloads it when
    deserialized.

    In addition, if the function was generated by another function, like a factory, then this
    field will store a reference to the factory function and call it with any `kwargs` required
    by the inner function.
    For example:

    ```python
    def outer(x, y):
        def inner(z):
            return x + y + z
        return inner

    f = outer(1, 2)
    ```

    Here, `f` is a "stateful" function because it depends on the values `x` and `y`, but has
    no explicit attribute holding them. It was generated by a closure that requires them.

    We would serialize this function as `{"fn": "outer", "kwargs": {"x": 1, "y": 2}}`

    Note that `nonlocals` MUST be JSON-compatible, with the exception of datetimes.

    Args:
        - valid_functions (List[Callable]): an allow list of valid functions
        - reject_invalid (bool): if True, functions not in `valid_functions` will be rejected.
            If False, any value will be allowed, but only functions in `valid_functions` will
            be deserialized.
        - **kwargs (Any): the keyword arguments accepted by `marshmallow.Field`

    """

    def __init__(
        self, valid_functions: list, reject_invalid: bool = True, **kwargs: Any
    ):
        self.valid_functions = {to_qualified_name(f): f for f in valid_functions}
        self.reject_invalid = reject_invalid
        super().__init__(**kwargs)

    def _serialize(self, value, attr, obj, **kwargs):  # type: ignore
        if value is None and self.allow_none:
            return None

        try:
            qual_name = to_qualified_name(value)
        except Exception:
            valid_bases = []
        else:
            # sort matches such that the longest / most specific match comes first
            valid_bases = sorted(
                [fn for fn in self.valid_functions if qual_name.startswith(fn)],
                key=lambda k: len(k),
                reverse=True,
            )

        if not valid_bases and self.reject_invalid:
            raise ValidationError(
                "When running with Prefect Cloud/Server, custom functions aren't supported "
                f"for `{type(obj).__name__}.{attr}`. Unable to serialize `{value!r}`."
            )
        else:
            base_name = next(filter(None, valid_bases)) if valid_bases else qual_name

        nonlocals = dict(inspect.getclosurevars(value).nonlocals)

        for k, v in list(nonlocals.items()):
            # convert dates to strings
            if isinstance(v, datetime.datetime):
                nonlocals[k] = "//datetime:" + v.isoformat()
            # convert time to strings
            elif isinstance(v, datetime.time):
                nonlocals[k] = "//time:" + v.isoformat()
            # convert timedelta to seconds
            elif isinstance(v, datetime.timedelta):
                nonlocals[k] = "//timedelta:" + str(v.total_seconds())

        return {"fn": base_name, "kwargs": nonlocals}

    def _deserialize(self, value, attr, data, **kwargs):  # type: ignore
        """
        Attempts to return the original function that was serialized, with _no state_.

        If not found, returns `None`.
        """
        if value is None and self.allow_none:
            return None

        # retrieve the function
        base_name = value["fn"]
        if base_name not in self.valid_functions and self.reject_invalid:
            raise ValidationError("Invalid function reference: {}".format(value))
        fn = self.valid_functions.get(base_name)

        if not fn:
            return None

        # call function on state
        kwargs = value.get("kwargs", {}).copy()

        # if there are no kwargs, then this function isn't stateful
        if not kwargs:
            return fn

        # if there ARE kwargs, then this function is actually the parent function and
        # it needs to be called
        for k, v in list(kwargs.items()):
            # parse datetimes
            if isinstance(v, str) and v.startswith("//datetime:"):
                kwargs[k] = pendulum.parse(v.split("//datetime:", 1)[1])
            # parse times
            if isinstance(v, str) and v.startswith("//time:"):
                kwargs[k] = pendulum.parse(v.split("//time:", 1)[1]).time()
            # parse timedeltas
            if isinstance(v, str) and v.startswith("//timedelta:"):
                kwargs[k] = datetime.timedelta(
                    seconds=float(v.split("//timedelta:", 1)[1])
                )
        return fn(**kwargs)
