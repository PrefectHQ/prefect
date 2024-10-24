from typing import Any, Optional

from pydantic import AliasChoices, AliasPath, Field
from pydantic_settings import SettingsConfigDict

from prefect.settings.base import PrefectBaseSettings


class TestingSettings(PrefectBaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="PREFECT_TESTING_", env_file=".env", extra="ignore"
    )

    test_mode: bool = Field(
        default=False,
        description="If `True`, places the API in test mode. This may modify behavior to facilitate testing.",
        validation_alias=AliasChoices(
            AliasPath("test_mode"),
            "prefect_testing_test_mode",
            "prefect_test_mode",
        ),
    )

    unit_test_mode: bool = Field(
        default=False,
        description="This setting only exists to facilitate unit testing. If `True`, code is executing in a unit test context. Defaults to `False`.",
        validation_alias=AliasChoices(
            AliasPath("unit_test_mode"),
            "prefect_testing_unit_test_mode",
            "prefect_unit_test_mode",
        ),
    )

    unit_test_loop_debug: bool = Field(
        default=True,
        description="If `True` turns on debug mode for the unit testing event loop.",
        validation_alias=AliasChoices(
            AliasPath("unit_test_loop_debug"),
            "prefect_testing_unit_test_loop_debug",
            "prefect_unit_test_loop_debug",
        ),
    )

    test_setting: Optional[Any] = Field(
        default="FOO",
        description="This setting only exists to facilitate unit testing. If in test mode, this setting will return its value. Otherwise, it returns `None`.",
        validation_alias=AliasChoices(
            AliasPath("test_setting"),
            "prefect_testing_test_setting",
            "prefect_test_setting",
        ),
    )
