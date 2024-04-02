import operator
import typing

from prefect._internal.pydantic._base_model import BaseModel, FieldInfo
from prefect._internal.pydantic._flags import HAS_PYDANTIC_V2, USE_PYDANTIC_V2

T = typing.TypeVar("T")

if HAS_PYDANTIC_V2 and USE_PYDANTIC_V2:

    class ModelFieldMixin(BaseModel):  # type: ignore [no-redef]
        pass

else:

    def cast_model_field_to_field_info(model_field: typing.Any) -> FieldInfo:
        class _FieldInfo(BaseModel):
            model_field: typing.Any

            @property
            def annotation(self) -> typing.Any:
                return getattr(self.model_field, "outer_type_")

            @property
            def frozen(self) -> bool:
                return not operator.attrgetter("field_info.allow_mutation")(
                    self.model_field
                )

            @property
            def json_schema_extra(self) -> typing.Dict[str, typing.Any]:
                return operator.attrgetter("field_info.extra")(self.model_field)

            def __getattr__(self, key: str) -> typing.Any:
                return getattr(self.model_field, key)

            def __repr__(self) -> str:
                return repr(self.model_field)

        return typing.cast(FieldInfo, _FieldInfo(model_field=model_field))

    class ModelFieldMixin(BaseModel):
        model_fields: typing.ClassVar[typing.Dict[str, FieldInfo]]

        def __init_subclass__(cls, **kwargs: typing.Any) -> None:
            cls.model_fields = {
                field_name: cast_model_field_to_field_info(field)
                for field_name, field in getattr(cls, "__fields__", {}).items()
            }
            super().__init_subclass__(**kwargs)
