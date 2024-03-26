import json
from typing import Type

import pytest

from prefect._internal.pydantic import HAS_PYDANTIC_V2

if HAS_PYDANTIC_V2:
    from pydantic.v1 import ValidationError
else:
    from pydantic import ValidationError

from prefect.events import RelatedResource, Resource


@pytest.mark.parametrize("resource_class", [Resource, RelatedResource])
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


@pytest.mark.parametrize("resource_class", [Resource, RelatedResource])
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
