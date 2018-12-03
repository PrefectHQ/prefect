# Licensed under LICENSE.md; also available at https://www.prefect.io/licenses/alpha-eula
import types
import prefect
import sys
from typing import Dict, Callable, Optional, Any, List
import json
from marshmallow import (
    Schema,
    post_dump,
    post_load,
    SchemaOpts,
    pre_load,
    fields,
    ValidationError,
)
from prefect.utilities.collections import DotDict, as_nested_dict

import marshmallow_oneofschema

MAX_VERSION = "__MAX_VERSION__"
VERSIONS = {}  # type: Dict[str, Dict[str, VersionedSchema]]


def to_qualified_name(obj: Any) -> str:
    return obj.__module__ + "." + obj.__qualname__


def from_qualified_name(obj_str: str) -> object:
    """
    Retrives an object from a fully qualified string path. The object must be
    imported in advance.
    """

    path_components = obj_str.split(".")
    for i in range(len(path_components), 0, -1):
        module_path = ".".join(path_components[:i])
        if module_path in sys.modules:
            obj = sys.modules[module_path]
            for p in path_components[i:]:
                obj = getattr(obj, p)
            return obj
    raise ValueError(
        "Couldn't load \"{}\"; maybe it hasn't been imported yet?".format(obj_str)
    )


def version(version: str) -> Callable:
    """
    Decorator that registers a schema with a specific version of Prefect.
    """
    if not isinstance(version, str):
        raise TypeError("Version must be a string.")

    def wrapper(cls):
        if not issubclass(cls, VersionedSchema):
            raise TypeError("Expected VersionedSchema")
        VERSIONS.setdefault(to_qualified_name(cls), {})[version] = cls
        return cls

    return wrapper


def get_versioned_schema(schema: "VersionedSchema", version: str) -> "VersionedSchema":
    """
    Attempts to retrieve the registered VersionedSchema corresponding to name with the
    highest version less or than equal to `version`.

    Args:
        - name (str): the fully-qualified name of a registered VersionedSchema
        - version (str): the version number

    Returns:
        - VersionedSchema: the matching schema, or the original schema if no better match
            was found.

    """
    name = to_qualified_name(type(schema))
    versions = VERSIONS.get(name, None)

    if name not in VERSIONS:
        raise ValueError("Unregistered VersionedSchema")

    elif version is MAX_VERSION:
        return VERSIONS[name][max(VERSIONS[name])]

    else:
        matching_versions = [v for v in VERSIONS[name] if v <= version]
        if not matching_versions:
            raise ValueError(
                "No VersionSchema was registered for version {}".format(version)
            )
        return VERSIONS[name][max(matching_versions)]


class VersionedSchemaOptions(SchemaOpts):
    def __init__(self, meta, **kwargs):
        super().__init__(meta, **kwargs)
        self.object_class = getattr(meta, "object_class", None)
        self.object_class_exclude = getattr(meta, "object_class_exclude", None) or []


class VersionedSchema(Schema):
    """
    This Marshmallow Schema automatically adds a `__version__` field when it serializes an
    object, corresponding to the version of Prefect that did the serialization.

    Subclasses of VersionedSchema can be registered for specific versions of Prefect
    by using the `version` decorator.

    When a VersionedSchema is deserialized, it reads the `__version__` field (if available)
    and uses the VersionedSchema with the highest registered version less than or equal to
    the `__version__` value.

    This allows object schemas to be migrated while maintaining compatibility with
    """

    OPTIONS_CLASS = VersionedSchemaOptions

    class Meta:
        object_class = None  # type: type
        object_class_exclude = []  # type: List[str]

    def __init__(self, *args, **kwargs) -> None:
        self._args = args
        self._kwargs = kwargs
        super().__init__(*args, **kwargs)

    def load(self, data, create_object=True, check_version=True, **kwargs):
        self.context.setdefault("create_object", create_object)

        if check_version and isinstance(data, dict):
            schema = get_versioned_schema(self, data.get("__version__", MAX_VERSION))
        else:
            return super().load(data, **kwargs)

        # if we got a different (or no) schema, instantiate it
        if schema is not self:
            schema_instance = schema(*self._args, **self._kwargs)
            schema_instance.context.update(self.context)
            return schema_instance.load(
                data, create_object=create_object, check_version=False, **kwargs
            )
        else:
            return super().load(data, **kwargs)

    @pre_load
    def remove_version(self, data):
        data.pop("__version__", None)
        return data

    @post_dump
    def add_version(self, data):
        """
        Adds a __version__ field, if not already provided.
        """
        data.setdefault("__version__", prefect.__version__)
        return data

    @post_load
    def create_object(self, data):
        if self.context.get("create_object", True):
            object_class = self.opts.object_class
            if object_class is not None:
                if isinstance(object_class, types.FunctionType):
                    object_class = object_class()
                init_data = {
                    k: v
                    for k, v in data.items()
                    if k not in self.opts.object_class_exclude
                }
                return object_class(**init_data)
        return data


class JSONCompatible(fields.Field):
    """
    Field that ensures its values are JSON-compatible during serialization.
    """

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.validators.insert(0, self.validate_json)

    def _serialize(self, value, attr, obj, **kwargs):
        self.validate_json(value)
        return super()._serialize(value, attr, obj, **kwargs)

    def validate_json(self, value):
        # handle dict-like subclasses including DotDict and GraphQLResult
        value = as_nested_dict(value, dict)
        try:
            json.dumps(value)
        except TypeError:
            raise ValidationError("Value is not JSON-compatible")


class Nested(fields.Nested):
    """
    An extension of the Marshmallow Nested field that allows the value to be selected
    via a value_selection_fn.
    """

    def __init__(
        self, nested: type, value_selection_fn: Callable = None, **kwargs
    ) -> None:
        super().__init__(nested=nested, **kwargs)
        self.value_selection_fn = value_selection_fn

        if value_selection_fn is not None:
            self._CHECK_ATTRIBUTE = False

    def _serialize(self, value, attr, obj, **kwargs):
        if self.value_selection_fn is not None:
            value = self.value_selection_fn(obj, self.context)
        return super()._serialize(value, attr, obj, **kwargs)


class OneOfSchema(marshmallow_oneofschema.OneOfSchema):
    """
    A subclass of marshmallow_oneofschema.OneOfSchema that can load DotDicts
    """

    def _load(self, data, partial=None, unknown=None):
        if isinstance(data, DotDict):
            data = as_nested_dict(data, dict)
        return super()._load(data=data, partial=partial, unknown=unknown)
