import os
from pathlib import Path

from pydantic import root_validator, validator
from typing_extensions import Literal

from prefect.infrastructure.base import Infrastructure


class Subprocess(Infrastructure):
    type: Literal["subprocess"] = "subprocess"
    stream_output: bool = True

    @validator("condaenv")
    def coerce_pathlike_string_to_path(cls, value):
        if (
            not isinstance(value, Path)
            and value is not None
            and (value.startswith(os.sep) or value.startswith("~"))
        ):
            value = Path(value)
        return value

    @root_validator
    def ensure_only_one_env_was_given(cls, values):
        if values.get("condaenv") and values.get("virtualenv"):
            raise ValueError(
                "Received incompatible settings. You cannot provide both a conda and "
                "virtualenv to use."
            )
        return values


class Thread(Infrastructure):
    type: Literal["thread"] = "thread"
