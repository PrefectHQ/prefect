import json
from typing import List
from pydantic import BaseModel, create_model


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
    # copying a class doesn't work (`base is deepcopy(base)`), so we need to
    # make sure we don't modify the actual parent class. Instead, we store its
    # original __fields__ attribute, replace it with a modified one for the
    # subclass operation, and then restore the original value.

    # collect required field names
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

    # create model
    new_fields = {k: v for k, v in base.__fields__.items() if k in field_names}
    new_cls = create_model(name or base.__name__, __base__=base, __fields__=new_fields)

    return new_cls


class PrefectBaseModel(BaseModel):
    class Config:
        # TODO: enforced during early testing to help catch errors
        # while models are changing; can be relaxed later.
        extra = "forbid"

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
