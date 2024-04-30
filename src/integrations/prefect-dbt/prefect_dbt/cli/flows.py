from pathlib import Path
from typing import Optional, Union

from dbt.cli.main import dbtRunner

from prefect import flow, get_run_logger
from prefect_dbt.cli.commands import create_dbt_artifact
from prefect_dbt.cli.credentials import DbtCliProfile
from prefect_dbt.cli.tasks import dbt_build_task


@flow
def dbt_flow(
    profiles_dir: Optional[Union[Path, str]] = None,
    project_dir: Optional[Union[Path, str]] = None,
    overwrite_profiles: bool = False,
    dbt_cli_profile: Optional[DbtCliProfile] = None,
    create_artifact: bool = True,
    artifact_key: str = "dbt-flow-summary",
):
    """
    Executes the 'dbt build' command within a Prefect flow,
    and optionally creates a Prefect artifact summarizing the dbt build results.

    Args:
        profiles_dir: The directory to search for the profiles.yml file. Setting this
            appends the `--profiles-dir` option to the command provided.
            If this is not set, will try using the DBT_PROFILES_DIR env variable,
            but if that's also not set, will use the default directory `$HOME/.dbt/`.
        project_dir: The directory to search for the dbt_project.yml file.
            Default is the current working directory and its parents.
        overwrite_profiles: Whether the existing profiles.yml file under profiles_dir
            should be overwritten with a new profile.
        dbt_cli_profile: Profiles class containing the profile written to profiles.yml.
            Note! This is optional and will raise an error
            if profiles.yml already exists under profile_dir
            and overwrite_profiles is set to False.
        create_artifact: If True, creates a Prefect artifact on the task run
            with the dbt build results using the specified artifact key.
            Defaults to True.
        artifact_key: The key under which to store
            the dbt build results artifact in Prefect.
            Defaults to 'dbt-build-task-summary'.

    Example:
    ```python
        from prefect import flow
        from prefect_dbt.cli.flow import dbt_flow

        @flow
        def dbt_test_flow():
            dbt_flow(
                project_dir="/Users/test/my_dbt_project_dir"
            )
    ```

    Raises:
        ValueError: If required dbt_cli_profile is not provided
                    when needed for profile writing.
        RuntimeError: If the dbt build fails for any reason,
                    it will be indicated by the exception raised.
    """
    logger = get_run_logger()
    results = dbt_build_task(
        profiles_dir=profiles_dir,
        project_dir=project_dir,
        overwrite_profiles=overwrite_profiles,
        dbt_cli_profile=dbt_cli_profile,
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
