"""Module containing pre-built tasks that execute specific DBT CLI commands"""

import logging
import os
from pathlib import Path
from typing import Dict, List, Optional, Union
from uuid import UUID

import yaml
from dbt.cli.main import dbtRunner, dbtRunnerResult
from dbt.contracts.results import NodeStatus

from prefect import get_run_logger, task
from prefect.artifacts import create_markdown_artifact
from prefect_dbt.cli.credentials import DbtCliProfile


@task
def dbt_build_task(
    profiles_dir: Optional[Union[Path, str]] = None,
    project_dir: Optional[Union[Path, str]] = None,
    overwrite_profiles: bool = False,
    dbt_cli_profile: Optional[DbtCliProfile] = None,
    dbt_client: Optional[dbtRunner] = None,
    create_artifact: bool = True,
    artifact_key: str = "dbt-build-task-summary",
):
    """
    Executes the 'dbt build' command within a Prefect task,
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
        dbt_client: An instance of a dbtRunner client to execute dbt commands. If None,
            a new instance is created.
        create_artifact: If True, creates a Prefect artifact on the task run
            with the dbt build results using the specified artifact key.
            Defaults to True.
        artifact_key: The key under which to store
            the dbt build results artifact in Prefect.
            Defaults to 'dbt-build-task-summary'.

    Example:
    ```python
        from prefect import flow
        from prefect_dbt.cli.tasks import dbt_build_task

        @flow
        def dbt_test_flow():
            dbt_build_task(
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
    logger.info("Running dbt build task.")

    results = dbt_run(
        command="build",
        profiles_dir=profiles_dir,
        project_dir=project_dir,
        overwrite_profiles=overwrite_profiles,
        dbt_cli_profile=dbt_cli_profile,
        dbt_client=dbt_client,
        create_artifact=create_artifact,
        artifact_key=artifact_key,
        logger=logger,
    )
    return results


@task
def dbt_run_task(
    profiles_dir: Optional[Union[Path, str]] = None,
    project_dir: Optional[Union[Path, str]] = None,
    overwrite_profiles: bool = False,
    dbt_cli_profile: Optional[DbtCliProfile] = None,
    dbt_client: Optional[dbtRunner] = None,
    create_artifact: bool = True,
    artifact_key: str = "dbt-run-task-summary",
):
    """
    Executes the 'dbt run' command within a Prefect task,
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
        dbt_client: An instance of a dbtRunner client to execute dbt commands. If None,
            a new instance is created.
        create_artifact: If True, creates a Prefect artifact on the task run
            with the dbt build results using the specified artifact key.
            Defaults to True.
        artifact_key: The key under which to store
            the dbt run results artifact in Prefect.
            Defaults to 'dbt-run-task-summary'.

    Example:
    ```python
        from prefect import flow
        from prefect_dbt.cli.tasks import dbt_run_task

        @flow
        def dbt_test_flow():
            dbt_run_task(
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
    logger.info("Running dbt run task.")

    results = dbt_run(
        command="run",
        profiles_dir=profiles_dir,
        project_dir=project_dir,
        overwrite_profiles=overwrite_profiles,
        dbt_cli_profile=dbt_cli_profile,
        dbt_client=dbt_client,
        create_artifact=create_artifact,
        artifact_key=artifact_key,
        logger=logger,
    )

    return results


@task
def dbt_test_task(
    profiles_dir: Optional[Union[Path, str]] = None,
    project_dir: Optional[Union[Path, str]] = None,
    overwrite_profiles: bool = False,
    dbt_cli_profile: Optional[DbtCliProfile] = None,
    dbt_client: Optional[dbtRunner] = None,
    create_artifact: bool = True,
    artifact_key: str = "dbt-test-task-summary",
):
    """
    Executes the 'dbt test' command within a Prefect task,
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
        dbt_client: An instance of a dbtRunner client to execute dbt commands. If None,
            a new instance is created.
        create_artifact: If True, creates a Prefect artifact on the task run
            with the dbt build results using the specified artifact key.
            Defaults to True.
        artifact_key: The key under which to store
            the dbt test results artifact in Prefect.
            Defaults to 'dbt-test-task-summary'.

    Example:
    ```python
        from prefect import flow
        from prefect_dbt.cli.tasks import dbt_test_task

        @flow
        def dbt_test_flow():
            dbt_test_task(
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
    logger.info("Running dbt test task.")

    results = dbt_run(
        command="test",
        profiles_dir=profiles_dir,
        project_dir=project_dir,
        overwrite_profiles=overwrite_profiles,
        dbt_cli_profile=dbt_cli_profile,
        dbt_client=dbt_client,
        create_artifact=create_artifact,
        artifact_key=artifact_key,
        logger=logger,
    )

    return results


@task
def dbt_snapshot_task(
    profiles_dir: Optional[Union[Path, str]] = None,
    project_dir: Optional[Union[Path, str]] = None,
    overwrite_profiles: bool = False,
    dbt_cli_profile: Optional[DbtCliProfile] = None,
    dbt_client: Optional[dbtRunner] = None,
    create_artifact: bool = True,
    artifact_key: str = "dbt-snapshot-task-summary",
):
    """
    Executes the 'dbt snapshot' command within a Prefect task,
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
        dbt_client: An instance of a dbtRunner client to execute dbt commands. If None,
            a new instance is created.
        create_artifact: If True, creates a Prefect artifact on the task run
            with the dbt build results using the specified artifact key.
            Defaults to True.
        artifact_key: The key under which to store
            the dbt build results artifact in Prefect.
            Defaults to 'dbt-snapshot-task-summary'.

    Example:
    ```python
        from prefect import flow
        from prefect_dbt.cli.tasks import dbt_snapshot_task

        @flow
        def dbt_test_flow():
            dbt_snapshot_task(
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
    logger.info("Running dbt snapshot task.")

    results = dbt_run(
        command="snapshot",
        profiles_dir=profiles_dir,
        project_dir=project_dir,
        overwrite_profiles=overwrite_profiles,
        dbt_cli_profile=dbt_cli_profile,
        dbt_client=dbt_client,
        create_artifact=create_artifact,
        artifact_key=artifact_key,
        logger=logger,
    )

    return results


@task
def dbt_seed_task(
    profiles_dir: Optional[Union[Path, str]] = None,
    project_dir: Optional[Union[Path, str]] = None,
    overwrite_profiles: bool = False,
    dbt_cli_profile: Optional[DbtCliProfile] = None,
    dbt_client: Optional[dbtRunner] = None,
    create_artifact: bool = True,
    artifact_key: str = "dbt-seed-task-summary",
):
    """
    Executes the 'dbt seed' command within a Prefect task,
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
        dbt_client: An instance of a dbtRunner client to execute dbt commands. If None,
            a new instance is created.
        create_artifact: If True, creates a Prefect artifact on the task run
            with the dbt build results using the specified artifact key.
            Defaults to True.
        artifact_key: The key under which to store
            the dbt build results artifact in Prefect.
            Defaults to 'dbt-seed-task-summary'.

    Example:
    ```python
        from prefect import flow
        from prefect_dbt.cli.tasks import dbt_seed_task

        @flow
        def dbt_test_flow():
            dbt_seed_task(
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
    logger.info("Running dbt seed task.")

    results = dbt_run(
        command="seed",
        profiles_dir=profiles_dir,
        project_dir=project_dir,
        overwrite_profiles=overwrite_profiles,
        dbt_cli_profile=dbt_cli_profile,
        dbt_client=dbt_client,
        create_artifact=create_artifact,
        artifact_key=artifact_key,
        logger=logger,
    )

    return results


def dbt_run(
    command: str = "build",
    profiles_dir: Optional[Union[Path, str]] = None,
    project_dir: Optional[Union[Path, str]] = None,
    overwrite_profiles: bool = False,
    dbt_cli_profile: Optional[DbtCliProfile] = None,
    dbt_client: Optional[dbtRunner] = None,
    create_artifact: bool = True,
    artifact_key: str = "dbt-build-task-summary",
    logger: Optional[logging.Logger] = None,
    **kwargs,
):
    """
    Each of the tasks above uses this function to run the corresponding DBT command.
    The results of the DBT command are then passed into create_dbt_task_artifact
    in order to create the task artifact if create_artifact is true.
    """
    if not dbt_client:
        dbt_client = dbtRunner()

    if profiles_dir is None:
        profiles_dir = os.getenv("DBT_PROFILES_DIR", Path.home() / ".dbt")
    profiles_dir = Path(profiles_dir).expanduser()

    # https://docs.getdbt.com/dbt-cli/configure-your-profile
    # Note that the file always needs to be called profiles.yml,
    # regardless of which directory it is in.
    profiles_path = profiles_dir / "profiles.yml"

    # write the profile if overwrite or no profiles exist
    if overwrite_profiles or not profiles_path.exists():
        if dbt_cli_profile is None:
            raise ValueError("Provide `dbt_cli_profile` keyword for writing profiles")
        profile = dbt_cli_profile.get_profile()
        profiles_dir.mkdir(exist_ok=True)
        with open(profiles_path, "w+") as f:
            yaml.dump(profile, f, default_flow_style=False)
        logger.info(f"Wrote profile to {profiles_path}")
    elif dbt_cli_profile is not None:
        raise ValueError(
            f"Since overwrite_profiles is False and profiles_path ({profiles_path!r})"
            f"already exists, the profile within dbt_cli_profile could not be used; "
            f"if the existing profile is satisfactory, do not pass dbt_cli_profile"
        )

    # create CLI args as a list of strings
    cli_args = [command]

    # append the options
    cli_args.append("--profiles-dir")
    cli_args.append(profiles_dir)
    if project_dir is not None:
        project_dir = Path(project_dir).expanduser()
        cli_args.append("--project-dir")
        cli_args.append(project_dir)

    # run the command
    res: dbtRunnerResult = dbt_client.invoke(cli_args)

    if res.exception is not None:
        logger.error(f"dbt build task failed with exception: {res.exception}")
        raise res.exception

    if create_artifact:
        artifact_id = create_dbt_artifact(
            artifact_key=artifact_key, results=res, command=command
        )
        if not artifact_id:
            logger.error(f"Artifact was not created for dbt {command} task")
        else:
            logger.info(
                f"dbt {command} task completed successfully with artifact {artifact_id}"
            )

    return res


def create_dbt_artifact(
    artifact_key: str, results: dbtRunnerResult, command: str
) -> UUID:
    """
    Creates a Prefect task artifact summarizing the results
    of the above predefined prefrect-dbt task.
    """
    # Create Summary Markdown Artifact
    run_statuses: Dict[str, List[str]] = {
        "successful": [],
        "failed": [],
        "skipped": [],
    }

    for r in results.result.results:
        if r.status == NodeStatus.Success or r.status == NodeStatus.Pass:
            run_statuses["successful"].append(r)
        elif (
            r.status == NodeStatus.Fail
            or r.status == NodeStatus.Error
            or r.status == NodeStatus.RuntimeErr
        ):
            run_statuses["failed"].append(r)
        elif r.status == NodeStatus.Skipped:
            run_statuses["skipped"].append(r)

    markdown = f"# DBT {command.capitalize()} Task Summary"

    if run_statuses["failed"] != []:
        failed_runs_str = ""
        for r in run_statuses["failed"]:
            failed_runs_str += f"**{r.node.name}**\n \
                Node Type: {r.node.resource_type}\n \
                Node Path: {r.node.original_file_path}"
            if r.message:
                message = r.message.replace("\n", ".")
                failed_runs_str += f"\nError Message: {message}\n"
        markdown += f"""\n## Failed Runs 🔴\n\n{failed_runs_str}\n\n"""

    if run_statuses["successful"] != []:
        successful_runs_str = "\n".join(
            [f"**{r.node.name}**" for r in run_statuses["successful"]]
        )
        markdown += f"""\n## Successful Runs ✅\n\n{successful_runs_str}\n\n"""

    if run_statuses["skipped"] != []:
        skipped_runs_str = "\n".join(
            [f"**{r.node.name}**" for r in run_statuses["skipped"]]
        )
        markdown += f""" ## Skipped Runs 🚫\n\n{skipped_runs_str}\n\n"""

    return create_markdown_artifact(
        markdown=markdown,
        key=artifact_key,
    )
