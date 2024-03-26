import json
from typing import Type
from uuid import uuid4

import pendulum
import pytest

from prefect._internal.pydantic import HAS_PYDANTIC_V2
from prefect.settings import (
    PREFECT_EVENTS_MAXIMUM_LABELS_PER_RESOURCE,
    PREFECT_EVENTS_MAXIMUM_RELATED_RESOURCES,
    temporary_settings,
)

if HAS_PYDANTIC_V2:
    from pydantic.v1 import ValidationError
else:
    from pydantic import ValidationError

from prefect.events import Event, RelatedResource, Resource, ResourceSpecification
from prefect.events.schemas.labelling import LabelDiver


def test_resource_openapi_schema() -> None:
    assert Resource.schema() == {
        "title": "Resource",
        "description": "An observable business object of interest to the user",
        "type": "object",
        "additionalProperties": {"type": "string"},
    }


def test_related_resource_openapi_schema() -> None:
    assert RelatedResource.schema() == {
        "title": "RelatedResource",
        "description": "A Resource with a specific role in an Event",
        "type": "object",
        "additionalProperties": {"type": "string"},
    }


@pytest.mark.parametrize(
    "resource_class", [Resource, RelatedResource, ResourceSpecification]
)
def test_resource_root_is_required(resource_class: Type[Resource]) -> None:
    with pytest.raises(ValidationError) as error:
        resource_class(__root__=None)

    assert error.value.errors() == [
        {
            "loc": ("__root__",),
            "msg": "none is not an allowed value",
            "type": "type_error.none.not_allowed",
        }
    ]


@pytest.mark.parametrize(
    "resource_class", [Resource, RelatedResource, ResourceSpecification]
)
def test_resource_root_is_a_dictionary(resource_class: Type[Resource]) -> None:
    with pytest.raises(ValidationError) as error:
        resource_class(__root__=11)

    assert error.value.errors() == [
        {
            "loc": ("__root__",),
            "msg": "value is not a valid dict",
            "type": "type_error.dict",
        }
    ]


@pytest.mark.parametrize("resource_class", [Resource, RelatedResource])
def test_resource_requires_resource_id(resource_class: Type[Resource]) -> None:
    with pytest.raises(ValidationError) as error:
        resource_class(
            __root__={
                "prefect.resource.role": "any-role",
            }
        )

    assert error.value.errors() == [
        {
            "loc": ("__root__",),
            "msg": "Resources must include the prefect.resource.id label",
            "type": "value_error",
        }
    ]


def test_related_resources_require_role() -> None:
    with pytest.raises(ValidationError) as error:
        RelatedResource(
            __root__={
                "prefect.resource.id": "my.unique.resource",
            }
        )

    assert error.value.errors() == [
        {
            "loc": ("__root__",),
            "msg": "Related Resources must include the prefect.resource.role label",
            "type": "value_error",
        },
    ]


def test_related_resources_require_non_empty_role() -> None:
    with pytest.raises(ValidationError) as error:
        RelatedResource(
            __root__={
                "prefect.resource.id": "my.unique.resource",
                "prefect.resource.role": None,
            }
        )

    assert error.value.errors() == [
        {
            "loc": ("__root__",),
            "msg": "The prefect.resource.role label must be non-empty",
            "type": "value_error",
        },
    ]


@pytest.mark.parametrize("resource_class", [Resource, RelatedResource])
def test_resource_requires_non_empty_resource_id(
    resource_class: Type[Resource],
) -> None:
    with pytest.raises(ValidationError) as error:
        resource_class(
            __root__={
                "prefect.resource.id": None,
                "prefect.resource.role": "any-role",
            }
        )

    assert error.value.errors() == [
        {
            "loc": ("__root__",),
            "msg": "The prefect.resource.id label must be non-empty",
            "type": "value_error",
        }
    ]


def test_empty_resource_specification_allowed_and_includes_all_resources() -> None:
    specification = ResourceSpecification(__root__={})
    assert specification.includes(
        [Resource.parse_obj({"prefect.resource.id": "any.thing", "any": "thing"})]
    )
    assert specification.includes(
        [
            Resource.parse_obj(
                {
                    "prefect.resource.id": "this.too",
                    "prefect.resource.role": "also",
                    "this": "too",
                }
            )
        ]
    )


@pytest.mark.parametrize("resource_class", [Resource, RelatedResource])
def test_resource_disallows_none_values(resource_class: Type[Resource]) -> None:
    with pytest.raises(ValidationError) as error:
        resource_class(
            __root__={
                "prefect.resource.id": "my.unique.resource",
                "prefect.resource.role": "any-role",
                "another.thing": None,
            }
        )

    assert error.value.errors() == [
        {
            "loc": ("__root__", "another.thing"),
            "msg": "none is not an allowed value",
            "type": "type_error.none.not_allowed",
        },
    ]


@pytest.mark.parametrize("resource_class", [Resource, RelatedResource])
def test_resource_coerces_other_values(resource_class: Type[Resource]) -> None:
    resource = resource_class(
        __root__={
            "prefect.resource.id": "my.unique.resource",
            "prefect.resource.role": "any-role",
            "another.thing": 5,
        }
    )
    assert resource["another.thing"] == "5"


@pytest.mark.parametrize("resource_class", [Resource, RelatedResource])
def test_resources_support_indexing(resource_class: Type[Resource]) -> None:
    resource = resource_class(
        __root__={
            "prefect.resource.id": "my.unique.resource",
            "prefect.resource.role": "any-role",
            "this.thing": "hello",
            "that.thing": "world",
        }
    )
    assert resource["this.thing"] == "hello"
    assert resource["that.thing"] == "world"


@pytest.mark.parametrize("resource_class", [Resource, RelatedResource])
def test_resource_id_shortcut(resource_class: Type[Resource]) -> None:
    resource = resource_class(
        __root__={
            "prefect.resource.id": "my.unique.resource",
            "prefect.resource.role": "any-role",
        }
    )
    assert resource.id == "my.unique.resource"


def test_resource_role_shortcut() -> None:
    resource = RelatedResource(
        __root__={
            "prefect.resource.id": "my.unique.resource",
            "prefect.resource.role": "any-role",
        }
    )
    assert resource.role == "any-role"


@pytest.mark.parametrize("resource_class", [Resource, RelatedResource])
def test_resource_labels_are_iterable(resource_class: Type[Resource]) -> None:
    resource = resource_class(
        __root__={
            "prefect.resource.id": "my.unique.resource",
            "prefect.resource.role": "any-role",
            "hello": "world",
            "goodbye": "moon",
        }
    )
    assert set(resource.keys()) == {
        "prefect.resource.id",
        "prefect.resource.role",
        "hello",
        "goodbye",
    }


@pytest.mark.parametrize("resource_class", [Resource, RelatedResource])
def test_resource_label_pairs_are_iterable(resource_class: Type[Resource]) -> None:
    resource = resource_class(
        __root__={
            "prefect.resource.id": "my.unique.resource",
            "prefect.resource.role": "any-role",
            "hello": "world",
            "goodbye": "moon",
        }
    )
    assert set(resource.items()) == {
        ("prefect.resource.id", "my.unique.resource"),
        ("prefect.resource.role", "any-role"),
        ("hello", "world"),
        ("goodbye", "moon"),
    }


@pytest.mark.parametrize("resource_class", [Resource, RelatedResource])
def test_resources_export_to_simple_dicts(resource_class: Type[Resource]) -> None:
    resource = resource_class(
        __root__={
            "prefect.resource.id": "my.unique.resource",
            "prefect.resource.role": "any-role",
            "hello": "world",
            "goodbye": "moon",
        }
    )
    assert json.loads(resource.json()) == {
        "prefect.resource.id": "my.unique.resource",
        "prefect.resource.role": "any-role",
        "hello": "world",
        "goodbye": "moon",
    }


def test_label_diving_repr():
    representation = repr(
        LabelDiver(
            {
                "first": "a",
                "first.second": "b",
                "first.second.third": "c",
                "first.second.fourth": "d",
                "fifth.sixth": "e",
                "seventh": "f",
            }
        )
    )
    assert representation.startswith("LabelDiver(")
    assert "first" in representation
    assert "first.second" not in representation
    assert representation.endswith(")")


def test_label_diving():
    diver = LabelDiver(
        {
            "first": "a",
            "first.second": "b",
            "first.second.third": "c",
            "first.second.fourth": "d",
            "fifth.sixth": "e",
            "seventh": "f",
        }
    )

    assert str(diver.first) == "a"
    assert str(diver.first.second) == "b"
    assert str(diver.first.second.third) == "c"
    assert str(diver.first.second.fourth) == "d"
    assert str(diver.fifth.sixth) == "e"

    with pytest.raises(AttributeError):
        diver.non_existant

    with pytest.raises(AttributeError):
        diver.first.non_existant

    with pytest.raises(AttributeError):
        diver.seventh.eighth


def test_limit_on_labels():
    with temporary_settings(updates={PREFECT_EVENTS_MAXIMUM_LABELS_PER_RESOURCE: 10}):
        with pytest.raises(ValidationError, match="maximum number of labels"):
            Resource(
                __root__={
                    "prefect.resource.id": "the.thing",
                    **{str(i): str(i) for i in range(10)},
                }
            )


def test_limit_on_related_resources():
    with temporary_settings(updates={PREFECT_EVENTS_MAXIMUM_RELATED_RESOURCES: 10}):
        with pytest.raises(ValidationError, match="maximum number of related"):
            Event(
                occurred=pendulum.now("UTC"),
                event="anything",
                resource={"prefect.resource.id": "the.thing"},
                related=[
                    {
                        "prefect.resource.id": f"another.thing.{i}",
                        "prefect.resource.role": "related",
                    }
                    for i in range(11)
                ],
                id=uuid4(),
            )
