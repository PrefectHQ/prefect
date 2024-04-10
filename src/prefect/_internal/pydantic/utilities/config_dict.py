import typing

from prefect._internal.pydantic._base_model import BaseModel, ConfigDict
from prefect._internal.pydantic._flags import HAS_PYDANTIC_V2, USE_PYDANTIC_V2

if HAS_PYDANTIC_V2:
    from pydantic.v1.main import ModelMetaclass as PydanticModelMetaclass
else:
    from pydantic.main import ModelMetaclass as PydanticModelMetaclass


if USE_PYDANTIC_V2:

    class ConfigMixin(BaseModel):  # type: ignore
        pass

else:
    T = typing.TypeVar("T")

    CONFIG_V1_V2_KEYS: typing.Dict[str, str] = {
        "allow_population_by_field_name": "populate_by_name",
        "anystr_lower": "str_to_lower",
        "anystr_strip_whitespace": "str_strip_whitespace",
        "anystr_upper": "str_to_upper",
        "keep_untouched": "ignored_types",
        "max_anystr_length": "str_max_length",
        "min_anystr_length": "str_min_length",
        "orm_mode": "from_attributes",
        "schema_extra": "json_schema_extra",
        "validate_all": "validate_default",
        "copy_on_model_validation": "revalidate_instances",
    }

    CONFIG_V2_V1_KEYS: typing.Dict[str, str] = {
        v: k for k, v in CONFIG_V1_V2_KEYS.items()
    }

    def _convert_v2_config_to_v1_config(
        config_dict: typing.Union[ConfigDict, typing.Dict[str, typing.Any]],
    ) -> type:
        deprecated_renamed_keys = CONFIG_V2_V1_KEYS.keys() & config_dict.keys()
        output: typing.Dict[str, typing.Any] = {}
        for k in sorted(deprecated_renamed_keys):
            if CONFIG_V2_V1_KEYS[k] == "copy_on_model_validation":
                value = config_dict.get(k)
                if value == "never":
                    output[CONFIG_V2_V1_KEYS[k]] = "none"
                if value == "always":
                    output[CONFIG_V2_V1_KEYS[k]] = "deep"
                if value == "subclass-instances":
                    output[CONFIG_V2_V1_KEYS[k]] = "deep"
            else:
                output[CONFIG_V2_V1_KEYS[k]] = config_dict.get(k)
        return type("Config", (), output)

    class ConfigMeta(PydanticModelMetaclass):  # type: ignore
        def __new__(  # type: ignore
            cls,
            name: str,
            bases: typing.Any,
            namespace: typing.Dict[str, typing.Any],
            **kwargs: typing.Any,
        ):  # type: ignore
            if model_config := namespace.get("model_config"):
                namespace["Config"] = _convert_v2_config_to_v1_config(model_config)
            return super().__new__(cls, name, bases, namespace, **kwargs)  # type: ignore

    class ConfigMixin(BaseModel, metaclass=ConfigMeta):
        model_config: typing.ClassVar[ConfigDict]


__all__ = ["ConfigMixin"]
