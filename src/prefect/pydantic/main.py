import typing

from prefect._internal.pydantic._compat import BaseModel, Field, FieldInfo


class PrefectBaseModel(BaseModel):
    def _reset_fields(self) -> typing.Set[str]:
        """
        A set of field names that are reset when the PrefectBaseModel is copied.
        These fields are also disregarded for equality comparisons.
        """
        return set()


__all__ = ["BaseModel", "PrefectBaseModel", "Field", "FieldInfo"]
