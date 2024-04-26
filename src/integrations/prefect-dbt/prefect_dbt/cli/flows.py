from pathlib import Path  # noqa: I001
from typing import Optional, Union

from dbt.cli.main import dbtRunner
from prefect_dbt.cli.credentials import DbtCliProfile
from prefect_dbt.cli.tasks import create_dbt_artifact, dbt_build_task

from prefect import flow, get_run_logger


@flow
def dbt_flow(
    profiles_dir: Optional[Union[Path, str]] = None,
    project_dir: Optional[Union[Path, str]] = None,
    overwrite_profiles: bool = False,
    dbt_cli_profile: Optional[DbtCliProfile] = None,
    dbt_client: Optional[dbtRunner] = None,
    create_artifact: bool = True,
    artifact_key: str = "dbt-flow-summary",
):
    logger = get_run_logger()
    dbt_client = dbtRunner()
    results = dbt_build_task(
        profiles_dir=profiles_dir,
        project_dir=project_dir,
        overwrite_profiles=overwrite_profiles,
        dbt_cli_profile=dbt_cli_profile,
        dbt_client=dbt_client,
        create_artifact=False,
    )

    if create_artifact:
        artifact_id = create_dbt_artifact(
            results=results, artifact_key=artifact_key, command="flow"
        )

    if not artifact_id and create_artifact:
        logger.error("Artifact was not created for dbt flow")
    elif artifact_id and create_artifact:
        logger.debug(f"dbt flow completed successfully with artifact {artifact_id}")
