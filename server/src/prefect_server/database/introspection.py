# Licensed under the Prefect Community License, available at
# https://www.prefect.io/legal/prefect-community-license


import dataclasses
import typing as t
from pathlib import Path

from box import Box

from prefect_server.database.hasura import HasuraClient


def process_nested_dataclass(instance, field):
    if not dataclasses.is_dataclass(field.type):
        return

    value = getattr(instance, field.name)
    if not isinstance(value, dict):
        return

    new_value = field.type(**value)
    object.__setattr__(instance, field.name, new_value)


def process_nested_dataclass_list(instance, field):
    if not field.type.__base__ is t.List and dataclasses.is_dataclass(
        field.type.__args__[0]
    ):
        return

    value = getattr(instance, field.name)
    if not isinstance(value, list):
        return

    new_value = [field.type.__args__[0](**v) for v in value]
    object.__setattr__(instance, field.name, new_value)


def process_nested_dataclass_dict(instance, field):
    if not field.type.__base__ is t.Dict and dataclasses.is_dataclass(
        field.type.__args__[1]
    ):
        return

    value = getattr(instance, field.name)
    if not isinstance(value, list):
        return

    new_value = [field.type.__args__[1](**v) for v in value]
    new_value_dict = Box()
    new_value_dict.update({v.name: v for v in new_value})
    object.__setattr__(instance, field.name, new_value_dict)


@dataclasses.dataclass
class NestedDataclass:
    def __post_init__(self):
        """
        Convert all fields of type `dataclass` into an instance of the
        specified data class if the current value is of type dict.
        """
        cls = type(self)
        for f in dataclasses.fields(cls):

            # evaluate lazy types
            if f.type.__base__ is t.Type:
                f.type = f.type.__args__[0]._eval_type(globals(), locals())

            if f.type.__base__ is t.List:
                process_nested_dataclass_list(self, f)
            elif f.type.__base__ is t.Dict:
                process_nested_dataclass_dict(self, f)
            else:
                process_nested_dataclass(self, f)


@dataclasses.dataclass(frozen=True)
class OfType(NestedDataclass):
    kind: str
    name: str
    ofType: t.Type["OfType"]


@dataclasses.dataclass(frozen=True)
class TypeRef(NestedDataclass):
    kind: str
    name: str
    ofType: OfType


@dataclasses.dataclass(frozen=True)
class InputValue(NestedDataclass):
    name: str
    description: str
    type: TypeRef
    defaultValue: str


@dataclasses.dataclass(frozen=True)
class Field(NestedDataclass):
    name: str
    description: str
    args: t.Dict[str, InputValue]
    type: TypeRef
    isDeprecated: bool
    deprecationReason: str


@dataclasses.dataclass(frozen=True)
class Enum(NestedDataclass):
    name: str
    description: str
    isDeprecated: bool
    deprecationReason: str


@dataclasses.dataclass(frozen=True)
class Directive(NestedDataclass):
    name: str
    description: str
    locations: str
    args: t.Dict[str, InputValue]


@dataclasses.dataclass(frozen=True)
class Type(NestedDataclass):
    name: str
    kind: str
    description: str
    fields: t.Dict[str, Field]
    inputFields: t.Dict[str, InputValue]
    interfaces: t.List[TypeRef]
    enumValues: t.Dict[str, Enum]
    possibleTypes: t.List[TypeRef]


@dataclasses.dataclass(frozen=True)
class RootType(NestedDataclass):
    name: str


@dataclasses.dataclass(frozen=True)
class Schema(NestedDataclass):
    queryType: RootType
    mutationType: RootType
    types: t.Dict[str, Type]
    directives: t.Dict[str, Directive]
    subscriptionType: RootType = None
    _registry: dict = dataclasses.field(default_factory=dict)

    def get_field_type(self, field_def):
        if field_def.type.ofType is None:
            ofType = field_def.type
        else:
            ofType = field_def.type.ofType
        while ofType.kind not in ("SCALAR", "OBJECT", "ENUM"):
            ofType = ofType.ofType
        return self.types[ofType.name]


def get_schema(url=None):
    with open(Path(__file__).parents[0] / "introspection_query.graphql") as f:
        introspection_query = f.read()
    client = HasuraClient(url)
    schema = client.run(introspection_query).__schema
    return Schema(**schema)
