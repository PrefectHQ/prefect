import inspect
from functools import partial
from typing import Any, Dict, Tuple, Type

from pydantic import (
    AliasChoices,
    AliasPath,
    SerializationInfo,
    SerializerFunctionWrapHandler,
    model_serializer,
)
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
)

from prefect.settings.sources import (
    EnvFilterSettingsSource,
    PrefectTomlConfigSettingsSource,
    ProfileSettingsTomlLoader,
    PyprojectTomlConfigSettingsSource,
)
from prefect.utilities.collections import visit_collection
from prefect.utilities.pydantic import handle_secret_render


class PrefectBaseSettings(BaseSettings):
    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: Type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> Tuple[PydanticBaseSettingsSource, ...]:
        """
        Define an order for Prefect settings sources.

        The order of the returned callables decides the priority of inputs; first item is the highest priority.

        See https://docs.pydantic.dev/latest/concepts/pydantic_settings/#customise-settings-sources
        """
        env_filter = set()
        for field in settings_cls.model_fields.values():
            if field.validation_alias is not None and isinstance(
                field.validation_alias, AliasChoices
            ):
                for alias in field.validation_alias.choices:
                    if isinstance(alias, AliasPath) and len(alias.path) > 0:
                        env_filter.add(alias.path[0])
        return (
            init_settings,
            EnvFilterSettingsSource(
                settings_cls,
                case_sensitive=cls.model_config.get("case_sensitive"),
                env_prefix=cls.model_config.get("env_prefix"),
                env_nested_delimiter=cls.model_config.get("env_nested_delimiter"),
                env_ignore_empty=cls.model_config.get("env_ignore_empty"),
                env_parse_none_str=cls.model_config.get("env_parse_none_str"),
                env_parse_enums=cls.model_config.get("env_parse_enums"),
                env_filter=list(env_filter),
            ),
            dotenv_settings,
            file_secret_settings,
            PrefectTomlConfigSettingsSource(settings_cls),
            PyprojectTomlConfigSettingsSource(settings_cls),
            ProfileSettingsTomlLoader(settings_cls),
        )

    def to_environment_variables(
        self,
        exclude_unset: bool = False,
        include_secrets: bool = True,
    ) -> Dict[str, str]:
        """Convert the settings object to a dictionary of environment variables."""

        env: Dict[str, Any] = self.model_dump(
            exclude_unset=exclude_unset,
            mode="json",
            context={"include_secrets": include_secrets},
        )
        env_variables = {}
        for key in self.model_fields.keys():
            if isinstance(child_settings := getattr(self, key), PrefectBaseSettings):
                child_env = child_settings.to_environment_variables(
                    exclude_unset=exclude_unset,
                    include_secrets=include_secrets,
                )
                env_variables.update(child_env)
            elif (value := env.get(key)) is not None:
                env_variables[
                    f"{self.model_config.get('env_prefix')}{key.upper()}"
                ] = str(value)
        return env_variables

    @model_serializer(
        mode="wrap", when_used="always"
    )  # TODO: reconsider `when_used` default for more control
    def ser_model(
        self, handler: SerializerFunctionWrapHandler, info: SerializationInfo
    ) -> Any:
        jsonable_self = handler(self)
        # iterate over fields to ensure child models that have been updated are also included
        for key in self.model_fields.keys():
            if info.exclude and key in info.exclude:
                continue
            if info.include and key not in info.include:
                continue

            child_include = None
            child_exclude = None
            if info.include and key in info.include and isinstance(info.include, dict):
                child_include = info.include[key]

            if isinstance(child_settings := getattr(self, key), PrefectBaseSettings):
                child_jsonable = child_settings.model_dump(
                    mode=info.mode,
                    include=child_include,  # type: ignore
                    exclude=child_exclude,
                    exclude_unset=info.exclude_unset,
                    context=info.context,
                    by_alias=info.by_alias,
                    exclude_none=info.exclude_none,
                    exclude_defaults=info.exclude_defaults,
                    serialize_as_any=info.serialize_as_any,
                )
                if child_jsonable:
                    jsonable_self[key] = child_jsonable
        if info.context and info.context.get("include_secrets") is True:
            jsonable_self.update(
                {
                    field_name: visit_collection(
                        expr=getattr(self, field_name),
                        visit_fn=partial(handle_secret_render, context=info.context),
                        return_data=True,
                    )
                    for field_name in set(jsonable_self.keys())  # type: ignore
                }
            )

        return jsonable_self


class PrefectSettingsConfigDict(SettingsConfigDict, total=False):
    """
    Configuration for the behavior of Prefect settings models.
    """

    prefect_toml_table_header: tuple[str, ...]
    """
    Header of the TOML table within a prefect.toml file to use when filling variables.
    This is supplied as a `tuple[str, ...]` instead of a `str` to accommodate for headers
    containing a `.`.

    To use the root table, exclude this config setting or provide an empty tuple.
    """


def _add_environment_variables(
    schema: Dict[str, Any], model: Type[PrefectBaseSettings]
) -> None:
    for property in schema["properties"]:
        env_vars = []
        schema["properties"][property]["supported_environment_variables"] = env_vars
        field = model.model_fields[property]
        if inspect.isclass(field.annotation) and issubclass(
            field.annotation, PrefectBaseSettings
        ):
            continue
        elif field.validation_alias:
            if isinstance(field.validation_alias, AliasChoices):
                for alias in field.validation_alias.choices:
                    if isinstance(alias, str):
                        env_vars.append(alias.upper())
        else:
            env_vars.append(f"{model.model_config.get('env_prefix')}{property.upper()}")


def _build_settings_config(
    path: Tuple[str, ...] = tuple(),
) -> PrefectSettingsConfigDict:
    env_prefix = f"PREFECT_{'_'.join(path).upper()}_" if path else "PREFECT_"
    return PrefectSettingsConfigDict(
        env_prefix=env_prefix,
        env_file=".env",
        extra="ignore",
        toml_file="prefect.toml",
        prefect_toml_table_header=path,
        pyproject_toml_table_header=("tool", "prefect", *path),
        json_schema_extra=_add_environment_variables,
    )
