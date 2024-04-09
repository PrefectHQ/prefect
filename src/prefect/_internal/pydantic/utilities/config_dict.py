import typing

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
}


CONFIG_V2_V1_KEYS: typing.Dict[str, str] = {v: k for k, v in CONFIG_V1_V2_KEYS.items()}
