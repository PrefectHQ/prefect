import copy
import datetime
import json
from typing import List
from uuid import UUID, uuid4

import pendulum
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


class APIBaseModel(PrefectBaseModel):
    class Config:
        orm_mode = True

    id: UUID = Field(default_factory=uuid4)
    created: datetime.datetime = Field(None, repr=False)
    updated: datetime.datetime = Field(None, repr=False)

    def copy(self, *, update: dict = None, **kwargs):
        """
        Copying API models should return an object that could be inserted into the
        database again. The 'id' is set to a new UUID and the database generated
        'created' and 'updated' fields are cleared.
        """
        update = update or dict()

        update.setdefault("id", uuid4())
        update.setdefault("created", None)
        update.setdefault("updated", None)

        return super().copy(update=update, **kwargs)
