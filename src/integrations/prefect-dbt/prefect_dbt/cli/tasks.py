"""Module containing pre-built tasks that execute specific
 dbt tasks including optional summmary artifacts."""

from pathlib import Path
from typing import Optional, Union

from prefect_dbt.cli.commands import trigger_dbt_cli_command
from prefect_dbt.cli.credentials import DbtCliProfile


def dbt_build_task(
    profiles_dir: Optional[Union[Path, str]] = None,
    project_dir: Optional[Union[Path, str]] = None,
    overwrite_profiles: bool = False,
    dbt_cli_profile: Optional[DbtCliProfile] = None,
    create_artifact: bool = True,
    artifact_key: str = "dbt-build-task-summary",
    **command_kwargs,
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

    results = trigger_dbt_cli_command(
        command="build",
        profiles_dir=profiles_dir,
        project_dir=project_dir,
        overwrite_profiles=overwrite_profiles,
        dbt_cli_profile=dbt_cli_profile,
        create_artifact=create_artifact,
        artifact_key=artifact_key,
        **command_kwargs
    )
    return results


def dbt_run_task(
    profiles_dir: Optional[Union[Path, str]] = None,
    project_dir: Optional[Union[Path, str]] = None,
    overwrite_profiles: bool = False,
    dbt_cli_profile: Optional[DbtCliProfile] = None,
    create_artifact: bool = True,
    artifact_key: str = "dbt-run-task-summary",
    **command_kwargs
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

    results = trigger_dbt_cli_command(
        command="run",
        profiles_dir=profiles_dir,
        project_dir=project_dir,
        overwrite_profiles=overwrite_profiles,
        dbt_cli_profile=dbt_cli_profile,
        create_artifact=create_artifact,
        artifact_key=artifact_key,
        **command_kwargs
    )

    return results


def run_dbt_test(
    profiles_dir: Optional[Union[Path, str]] = None,
    project_dir: Optional[Union[Path, str]] = None,
    overwrite_profiles: bool = False,
    dbt_cli_profile: Optional[DbtCliProfile] = None,
    create_artifact: bool = True,
    artifact_key: str = "dbt-test-task-summary",
    **command_kwargs
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

    results = trigger_dbt_cli_command(
        command="test",
        profiles_dir=profiles_dir,
        project_dir=project_dir,
        overwrite_profiles=overwrite_profiles,
        dbt_cli_profile=dbt_cli_profile,
        create_artifact=create_artifact,
        artifact_key=artifact_key,
        **command_kwargs
    )

    return results


def run_dbt_snapshot(
    profiles_dir: Optional[Union[Path, str]] = None,
    project_dir: Optional[Union[Path, str]] = None,
    overwrite_profiles: bool = False,
    dbt_cli_profile: Optional[DbtCliProfile] = None,
    create_artifact: bool = True,
    artifact_key: str = "dbt-snapshot-task-summary",
    **command_kwargs
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

    results = trigger_dbt_cli_command(
        command="snapshot",
        profiles_dir=profiles_dir,
        project_dir=project_dir,
        overwrite_profiles=overwrite_profiles,
        dbt_cli_profile=dbt_cli_profile,
        create_artifact=create_artifact,
        artifact_key=artifact_key,
        **command_kwargs
    )

    return results


def run_dbt_seed(
    profiles_dir: Optional[Union[Path, str]] = None,
    project_dir: Optional[Union[Path, str]] = None,
    overwrite_profiles: bool = False,
    dbt_cli_profile: Optional[DbtCliProfile] = None,
    create_artifact: bool = True,
    artifact_key: str = "dbt-seed-task-summary",
    **command_kwargs
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

    results = trigger_dbt_cli_command(
        command="seed",
        profiles_dir=profiles_dir,
        project_dir=project_dir,
        overwrite_profiles=overwrite_profiles,
        dbt_cli_profile=dbt_cli_profile,
        create_artifact=create_artifact,
        artifact_key=artifact_key,
        **command_kwargs
    )

    return results
