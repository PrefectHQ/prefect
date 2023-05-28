"""
Utilities for creating and working with Prefect REST API schemas.
"""
import copy
from typing import List, Type, TypeVar

from pydantic import BaseModel

from prefect._internal.schemas.bases import IDBaseModel as _IDBaseModel
from prefect._internal.schemas.bases import ObjectBaseModel
from prefect._internal.schemas.bases import PrefectBaseModel as _PrefectBaseModel
from prefect._internal.schemas.fields import DateTimeTZ as DateTimeTZ
from prefect._internal.schemas.serializers import orjson_dumps as orjson_dumps
from prefect._internal.schemas.serializers import (
    orjson_dumps_extra_compatible as orjson_dumps_extra_compatible,
)
from prefect._internal.schemas.transformations import FieldFrom as FieldFrom
from prefect._internal.schemas.transformations import (
    copy_model_fields as copy_model_fields,
)

T = TypeVar("T")
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


class SubclassMethodMixin:
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


class PrefectBaseModel(_PrefectBaseModel, SubclassMethodMixin):
    # Definition of this class moved to prefect._internal.schemas.base_schemas
    # Here, it is extended to retain support for the `subclass` method
    pass


class IDBaseModel(_IDBaseModel, SubclassMethodMixin):
    # Definition of this class moved to prefect._internal.schemas.base_schemas
    # Here, it is extended to retain support for the `subclass` method
    pass


class ORMBaseModel(ObjectBaseModel, SubclassMethodMixin):
    # Definition of this class moved to prefect._internal.schemas.base_schemas
    # Here, it is extended to retain support for the `subclass` method
    pass
