import datetime
from uuid import UUID, uuid4
import copy

import json
from typing import List
from pydantic import BaseModel, Field

from prefect import settings


def pydantic_subclass(
    base: BaseModel,
    name: str = None,
    include_fields: List[str] = None,
    exclude_fields: List[str] = None,
) -> BaseModel:
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
        class Parent(pydantic.BaseModel):
            x: int = 1
            y: int = 2

        Child = pydantic_subclass(Parent, 'Child', exclude_fields=['y'])

        # equivalent, for extending the subclass further
        # with new fields
        class Child(pydantic_subclass(Parent, exclude_fields=['y'])):
            pass

        assert hasattr(Child(), 'x')
        assert not hasattr(Child(), 'y')
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


class PrefectBaseModel(BaseModel):
    class Config:
        # when testing, extra attributes are prohibited to help
        # catch unintentional errors; otherwise they are ignored.
        extra = "forbid" if settings.test_mode else "ignore"

    @classmethod
    def subclass(
        cls,
        name: str = None,
        include_fields: List[str] = None,
        exclude_fields: List[str] = None,
    ) -> BaseModel:
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

    def json_dict(self, *args, **kwargs) -> dict:
        """Returns a dict of JSON-compatible values, equivalent
        to `json.loads(self.json())`.

        `self.dict()` returns Python-native types, including UUIDs
        and datetimes; `self.json()` returns a JSON string. This
        method is useful when we require a JSON-compatible Python
        object.

        Returns:
            dict: a JSON-compatible dict
        """
        return json.loads(self.json(*args, **kwargs))

    def dict(self, *args, shallow: bool = False, **kwargs) -> dict:
        """Returns a representation of the model as a Python dictionary.
        Identical to calling `model.dict()` unless
        `shallow=True` in which case the behavior is equivalent
        to calling `dict(model)` because the raw field values are returned
        and the dict coercion does not recurse into nested Pydantic models.

        For more information on this distinction please see
        https://pydantic-docs.helpmanual.io/usage/exporting_models/#dictmodel-and-iteration


        Args:
            shallow (bool, optional): If True, nested Pydantic fields
                are also coerced to dicts.

        Returns:
            dict
        """
        # standard pydantic behavior
        if not shallow:
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


class APIBaseModel(PrefectBaseModel):
    class Config:
        orm_mode = True

    id: UUID = Field(default_factory=uuid4)
    created: datetime.datetime = Field(None, repr=False)
    updated: datetime.datetime = Field(None, repr=False)
