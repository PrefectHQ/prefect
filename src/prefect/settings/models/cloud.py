import re
from typing import Optional

from pydantic import Field, model_validator
from typing_extensions import Self

from prefect.settings.base import (
    PrefectBaseSettings,
    _build_settings_config,
)


def default_cloud_ui_url(settings: "CloudSettings") -> Optional[str]:
    value = settings.ui_url
    if value is not None:
        return value

    # Otherwise, infer a value from the API URL
    ui_url = api_url = settings.api_url

    if re.match(r"^https://api[\.\w]*.prefect.[^\.]+/", api_url):
        ui_url = ui_url.replace("https://api", "https://app", 1)

    if ui_url.endswith("/api"):
        ui_url = ui_url[:-4]

    return ui_url


class CloudSettings(PrefectBaseSettings):
    """
    Settings for interacting with Prefect Cloud
    """

    model_config = _build_settings_config(("cloud",))

    api_url: str = Field(
        default="https://api.prefect.cloud/api",
        description="API URL for Prefect Cloud. Used for authentication with Prefect Cloud.",
    )

    ui_url: Optional[str] = Field(
        default=None,
        description="The URL of the Prefect Cloud UI. If not set, the client will attempt to infer it.",
    )

    @model_validator(mode="after")
    def post_hoc_settings(self) -> Self:
        """refactor on resolution of https://github.com/pydantic/pydantic/issues/9789

        we should not be modifying __pydantic_fields_set__ directly, but until we can
        define dependencies between defaults in a first-class way, we need clean up
        post-hoc default assignments to keep set/unset fields correct after instantiation.
        """
        if self.ui_url is None:
            self.ui_url = default_cloud_ui_url(self)
            self.__pydantic_fields_set__.remove("ui_url")
        return self
