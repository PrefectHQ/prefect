from typing import Optional

from pydantic import Field
from pydantic_settings import SettingsConfigDict

from prefect.settings.base import PrefectBaseSettings


class CLISettings(PrefectBaseSettings):
    """
    Settings for controlling CLI behavior
    """

    model_config = SettingsConfigDict(
        env_prefix="PREFECT_CLI_", env_file=".env", extra="ignore"
    )

    colors: bool = Field(
        default=True,
        description="If True, use colors in CLI output. If `False`, output will not include colors codes.",
    )

    prompt: Optional[bool] = Field(
        default=None,
        description="If `True`, use interactive prompts in CLI commands. If `False`, no interactive prompts will be used. If `None`, the value will be dynamically determined based on the presence of an interactive-enabled terminal.",
    )

    wrap_lines: bool = Field(
        default=True,
        description="If `True`, wrap text by inserting new lines in long lines in CLI output. If `False`, output will not be wrapped.",
    )
