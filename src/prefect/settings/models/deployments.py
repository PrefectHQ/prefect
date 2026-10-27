from typing import ClassVar, Optional

from pydantic import AliasChoices, AliasPath, Field
from pydantic_settings import SettingsConfigDict

from prefect.settings.base import PrefectBaseSettings, build_settings_config


class DeploymentsSettings(PrefectBaseSettings):
    """
    Settings for configuring deployments defaults
    """

    model_config: ClassVar[SettingsConfigDict] = build_settings_config(("deployments",))

    clear_schedules_on_empty: bool = Field(
        default=False,
        description=(
            "Clear existing schedules when an empty schedules list is passed to "
            "RunnerDeployment.apply or aapply, including via prefect deploy. "
            "This opt-in setting will be removed when clearing becomes the default, "
            "after a deprecation period of at least six months or three minor "
            "releases, whichever is longer."
        ),
    )

    default_work_pool_name: Optional[str] = Field(
        default=None,
        description="The default work pool to use when creating deployments.",
        validation_alias=AliasChoices(
            AliasPath("default_work_pool_name"),
            "prefect_deployments_default_work_pool_name",
            "prefect_default_work_pool_name",
        ),
    )

    default_docker_build_namespace: Optional[str] = Field(
        default=None,
        description="The default Docker namespace to use when building images.",
        validation_alias=AliasChoices(
            AliasPath("default_docker_build_namespace"),
            "prefect_deployments_default_docker_build_namespace",
            "prefect_default_docker_build_namespace",
        ),
        examples=[
            "my-dockerhub-registry",
            "4999999999999.dkr.ecr.us-east-2.amazonaws.com/my-ecr-repo",
        ],
    )
