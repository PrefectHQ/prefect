"""Module containing tasks and flows for interacting with dbt CLI"""

import os
from pathlib import Path, PosixPath
from typing import Any, Dict, List, Optional, Union

import yaml
from dbt.artifacts.schemas.freshness.v3.freshness import FreshnessResult
from dbt.artifacts.schemas.run.v5.run import RunResult, RunResultOutput
from dbt.cli.main import dbtRunner, dbtRunnerResult
from dbt.contracts.results import ExecutionResult, NodeStatus
from prefect_shell.commands import ShellOperation
from pydantic import Field

from prefect import task
from prefect.artifacts import acreate_markdown_artifact
from prefect.logging import get_run_logger
from prefect.states import Failed
from prefect.utilities.asyncutils import sync_compatible
from prefect.utilities.filesystem import relative_path_to_current_platform
from prefect_dbt.cli.credentials import DbtCliProfile


@task
@sync_compatible
async def trigger_dbt_cli_command(
    command: str,
    profiles_dir: Optional[Union[Path, str]] = None,
    project_dir: Optional[Union[Path, str]] = None,
    overwrite_profiles: bool = False,
    dbt_cli_profile: Optional[DbtCliProfile] = None,
    create_summary_artifact: bool = False,
    summary_artifact_key: Optional[str] = "dbt-cli-command-summary",
    extra_command_args: Optional[List[str]] = None,
    stream_output: bool = True,
) -> Optional[dbtRunnerResult]:
    """
    Task for running dbt commands.

    If no profiles.yml file is found or if overwrite_profiles flag is set to True, this
    will first generate a profiles.yml file in the profiles_dir directory. Then run the dbt
    CLI shell command.

    Args:
        command: The dbt command to be executed.
        profiles_dir: The directory to search for the profiles.yml file. Setting this
            appends the `--profiles-dir` option to the command provided. If this is not set,
            will try using the DBT_PROFILES_DIR environment variable, but if that's also not
            set, will use the default directory `$HOME/.dbt/`.
        project_dir: The directory to search for the dbt_project.yml file.
            Default is the current working directory and its parents.
        overwrite_profiles: Whether the existing profiles.yml file under profiles_dir
            should be overwritten with a new profile.
        dbt_cli_profile: Profiles class containing the profile written to profiles.yml.
            Note! This is optional and will raise an error if profiles.yml already exists
            under profile_dir and overwrite_profiles is set to False.
        create_summary_artifact: If True, creates a Prefect artifact on the task run
            with the dbt results using the specified artifact key.
            Defaults to False.
        summary_artifact_key: The key under which to store the dbt results artifact in Prefect.
            Defaults to 'dbt-cli-command-summary'.
        extra_command_args: Additional command arguments to pass to the dbt command.
            These arguments get appended to the command that gets passed to the dbtRunner client.
            Example: extra_command_args=["--model", "foo_model"]
        stream_output: If True, the output from the dbt command will be logged in Prefect
            as it happens.
            Defaults to True.

    Returns:
        last_line_cli_output (str): The last line of the CLI output will be returned
            if `return_all` in `shell_run_command_kwargs` is False. This is the default
            behavior.
        full_cli_output (List[str]): Full CLI output will be returned if `return_all`
            in `shell_run_command_kwargs` is True.

    Examples:
        Execute `dbt debug` with a pre-populated profiles.yml.
        ```python
        from prefect import flow
        from prefect_dbt.cli.commands import trigger_dbt_cli_command

        @flow
        def trigger_dbt_cli_command_flow():
            result = trigger_dbt_cli_command("dbt debug")
            return result

        trigger_dbt_cli_command_flow()
        ```

        Execute `dbt debug` without a pre-populated profiles.yml.
        ```python
        from prefect import flow
        from prefect_dbt.cli.credentials import DbtCliProfile
        from prefect_dbt.cli.commands import trigger_dbt_cli_command
        from prefect_dbt.cli.configs import SnowflakeTargetConfigs
        from prefect_snowflake.credentials import SnowflakeCredentials

        @flow
        def trigger_dbt_cli_command_flow():
            credentials = SnowflakeCredentials(
                user="user",
                password="password",
                account="account.region.aws",
                role="role",
            )
            connector = SnowflakeConnector(
                schema="public",
                database="database",
                warehouse="warehouse",
                credentials=credentials,
            )
            target_configs = SnowflakeTargetConfigs(
                connector=connector
            )
            dbt_cli_profile = DbtCliProfile(
                name="jaffle_shop",
                target="dev",
                target_configs=target_configs,
            )
            result = trigger_dbt_cli_command(
                "dbt run",
                overwrite_profiles=True,
                dbt_cli_profile=dbt_cli_profile,
                extra_command_args=["--model", "foo_model"]
            )
            return result

        trigger_dbt_cli_command_flow()
        ```
    """
    logger = get_run_logger()

    if profiles_dir is None:
        profiles_dir = os.getenv("DBT_PROFILES_DIR", str(Path.home()) + "/.dbt")

    # https://docs.getdbt.com/dbt-cli/configure-your-profile
    # Note that the file always needs to be called profiles.yml,
    # regardless of which directory it is in.
    profiles_path = profiles_dir + "/profiles.yml"
    logger.debug(f"Using this profiles path: {profiles_path}")

    # write the profile if overwrite or no profiles exist
    if overwrite_profiles or not Path(profiles_path).expanduser().exists():
        if dbt_cli_profile is None:
            raise ValueError(
                "Profile not found. Provide `dbt_cli_profile` or"
                f" ensure profiles.yml exists at {profiles_path}."
            )
        profile = dbt_cli_profile.get_profile()
        Path(profiles_dir).expanduser().mkdir(exist_ok=True)
        with open(profiles_path, "w+") as f:
            yaml.dump(profile, f, default_flow_style=False)
        logger.info(f"Wrote profile to {profiles_path}")
    elif dbt_cli_profile is not None:
        raise ValueError(
            f"Since overwrite_profiles is False and profiles_path ({profiles_path}) "
            f"already exists, the profile within dbt_cli_profile could not be used; "
            f"if the existing profile is satisfactory, do not pass dbt_cli_profile"
        )

    # append the options
    cli_args = [arg for arg in command.split() if arg != "dbt"]
    cli_args.append("--profiles-dir")
    cli_args.append(profiles_dir)
    if project_dir is not None:
        project_dir = Path(project_dir).expanduser()
        cli_args.append("--project-dir")
        cli_args.append(project_dir)

    if extra_command_args:
        for value in extra_command_args:
            cli_args.append(value)

    # Add the dbt event log callback if enabled
    callbacks = []
    if stream_output:

        def _stream_output(event):
            if event.info.level != "debug":
                logger.info(event.info.msg)

        callbacks.append(_stream_output)

    # fix up empty shell_run_command_kwargs
    dbt_runner_client = dbtRunner(callbacks=callbacks)
    logger.info(f"Running dbt command: {cli_args}")
    result: dbtRunnerResult = dbt_runner_client.invoke(cli_args)

    if result.exception is not None:
        logger.error(f"dbt task failed with exception: {result.exception}")
        raise result.exception

    # Creating the dbt Summary Markdown if enabled
    if create_summary_artifact and isinstance(result.result, ExecutionResult):
        run_results = consolidate_run_results(result)
        markdown = create_summary_markdown(run_results, command)
        artifact_id = await acreate_markdown_artifact(
            markdown=markdown, key=summary_artifact_key
        )
        if not artifact_id:
            logger.error(f"Summary Artifact was not created for dbt {command} task")
        else:
            logger.info(
                f"dbt {command} task completed successfully with artifact {artifact_id}"
            )
    else:
        logger.debug(
            f"Artifacts were not created for dbt {command} this task "
            "due to create_artifact=False or the dbt command did not "
            "return any RunExecutionResults. "
            "See https://docs.getdbt.com/reference/programmatic-invocations "
            "for more details on dbtRunnerResult."
        )
    if isinstance(result.result, ExecutionResult) and not result.success:
        return Failed(
            message=f"dbt task result success: {result.success} with exception: {result.exception}"
        )
    return result


class DbtCoreOperation(ShellOperation):
    """
    A block representing a dbt operation, containing multiple dbt and shell commands.

    For long-lasting operations, use the trigger method and utilize the block as a
    context manager for automatic closure of processes when context is exited.
    If not, manually call the close method to close processes.

    For short-lasting operations, use the run method. Context is automatically managed
    with this method.

    Attributes:
        commands: A list of commands to execute sequentially.
        stream_output: Whether to stream output.
        env: A dictionary of environment variables to set for the shell operation.
        working_dir: The working directory context the commands will be executed within.
        shell: The shell to use to execute the commands.
        extension: The extension to use for the temporary file.
            if unset defaults to `.ps1` on Windows and `.sh` on other platforms.
        profiles_dir: The directory to search for the profiles.yml file.
            Setting this appends the `--profiles-dir` option to the dbt commands
            provided. If this is not set, will try using the DBT_PROFILES_DIR
            environment variable, but if that's also not
            set, will use the default directory `$HOME/.dbt/`.
        project_dir: The directory to search for the dbt_project.yml file.
            Default is the current working directory and its parents.
        overwrite_profiles: Whether the existing profiles.yml file under profiles_dir
            should be overwritten with a new profile.
        dbt_cli_profile: Profiles class containing the profile written to profiles.yml.
            Note! This is optional and will raise an error if profiles.yml already
            exists under profile_dir and overwrite_profiles is set to False.

    Examples:
        Load a configured block.
        ```python
        from prefect_dbt import DbtCoreOperation

        dbt_op = DbtCoreOperation.load("BLOCK_NAME")
        ```

        Execute short-lasting dbt debug and list with a custom DbtCliProfile.
        ```python
        from prefect_dbt import DbtCoreOperation, DbtCliProfile
        from prefect_dbt.cli.configs import SnowflakeTargetConfigs
        from prefect_snowflake import SnowflakeConnector

        snowflake_connector = await SnowflakeConnector.load("snowflake-connector")
        target_configs = SnowflakeTargetConfigs(connector=snowflake_connector)
        dbt_cli_profile = DbtCliProfile(
            name="jaffle_shop",
            target="dev",
            target_configs=target_configs,
        )
        dbt_init = DbtCoreOperation(
            commands=["dbt debug", "dbt list"],
            dbt_cli_profile=dbt_cli_profile,
            overwrite_profiles=True
        )
        dbt_init.run()
        ```

        Execute a longer-lasting dbt run as a context manager.
        ```python
        with DbtCoreOperation(commands=["dbt run"]) as dbt_run:
            dbt_process = dbt_run.trigger()
            # do other things
            dbt_process.wait_for_completion()
            dbt_output = dbt_process.fetch_result()
        ```
    """

    _block_type_name = "dbt Core Operation"
    _logo_url = "https://images.ctfassets.net/gm98wzqotmnx/5zE9lxfzBHjw3tnEup4wWL/9a001902ed43a84c6c96d23b24622e19/dbt-bit_tm.png?h=250"  # noqa
    _documentation_url = "https://docs.prefect.io/integrations/prefect-dbt"  # noqa

    profiles_dir: Optional[Path] = Field(
        default=None,
        description=(
            "The directory to search for the profiles.yml file. "
            "Setting this appends the `--profiles-dir` option to the dbt commands "
            "provided. If this is not set, will try using the DBT_PROFILES_DIR "
            "environment variable, but if that's also not "
            "set, will use the default directory `$HOME/.dbt/`."
        ),
    )
    project_dir: Optional[Path] = Field(
        default=None,
        description=(
            "The directory to search for the dbt_project.yml file. "
            "Default is the current working directory and its parents."
        ),
    )
    overwrite_profiles: bool = Field(
        default=False,
        description=(
            "Whether the existing profiles.yml file under profiles_dir "
            "should be overwritten with a new profile."
        ),
    )
    dbt_cli_profile: Optional[DbtCliProfile] = Field(
        default=None,
        description=(
            "Profiles class containing the profile written to profiles.yml. "
            "Note! This is optional and will raise an error if profiles.yml already "
            "exists under profile_dir and overwrite_profiles is set to False."
        ),
    )

    def _find_valid_profiles_dir(self) -> PosixPath:
        """
        Ensure that there is a profiles.yml available for use.
        """
        profiles_dir = self.profiles_dir
        if profiles_dir is None:
            if self.env.get("DBT_PROFILES_DIR") is not None:
                # get DBT_PROFILES_DIR from the user input env
                profiles_dir = self.env["DBT_PROFILES_DIR"]
            else:
                # get DBT_PROFILES_DIR from the system env, or default to ~/.dbt
                profiles_dir = os.getenv("DBT_PROFILES_DIR", Path.home() / ".dbt")
        profiles_dir = relative_path_to_current_platform(
            Path(profiles_dir).expanduser()
        )

        # https://docs.getdbt.com/dbt-cli/configure-your-profile
        # Note that the file always needs to be called profiles.yml,
        # regardless of which directory it is in.
        profiles_path = profiles_dir / "profiles.yml"
        overwrite_profiles = self.overwrite_profiles
        dbt_cli_profile = self.dbt_cli_profile
        if not profiles_path.exists() or overwrite_profiles:
            if dbt_cli_profile is None:
                raise ValueError(
                    "Since overwrite_profiles is True or profiles_path is empty, "
                    "need `dbt_cli_profile` to write a profile"
                )
            profile = dbt_cli_profile.get_profile()
            profiles_dir.mkdir(exist_ok=True)
            with open(profiles_path, "w+") as f:
                yaml.dump(profile, f, default_flow_style=False)
        elif dbt_cli_profile is not None:
            raise ValueError(
                f"Since overwrite_profiles is False and profiles_path {profiles_path} "
                f"already exists, the profile within dbt_cli_profile couldn't be used; "
                f"if the existing profile is satisfactory, do not set dbt_cli_profile"
            )
        return profiles_dir

    def _append_dirs_to_commands(self, profiles_dir) -> List[str]:
        """
        Append profiles_dir and project_dir options to dbt commands.
        """
        project_dir = self.project_dir

        commands = []
        for command in self.commands:
            command += f' --profiles-dir "{profiles_dir}"'
            if project_dir is not None:
                project_dir = Path(project_dir).expanduser()
                command += f' --project-dir "{project_dir}"'
            commands.append(command)
        return commands

    def _compile_kwargs(self, **open_kwargs: Dict[str, Any]) -> Dict[str, Any]:
        """
        Helper method to compile the kwargs for `open_process` so it's not repeated
        across the run and trigger methods.
        """
        profiles_dir = self._find_valid_profiles_dir()
        commands = self._append_dirs_to_commands(profiles_dir=profiles_dir)

        # _compile_kwargs is called within trigger() and run(), prior to execution.
        # However _compile_kwargs directly uses self.commands, but here we modified
        # the commands without saving back to self.commands so we need to create a copy.
        # was also thinking of using env vars but DBT_PROJECT_DIR is not supported yet.
        modified_self = self.copy()
        modified_self.commands = commands
        return super(type(self), modified_self)._compile_kwargs(**open_kwargs)


@sync_compatible
@task
async def run_dbt_build(
    profiles_dir: Optional[Union[Path, str]] = None,
    project_dir: Optional[Union[Path, str]] = None,
    overwrite_profiles: bool = False,
    dbt_cli_profile: Optional[DbtCliProfile] = None,
    create_summary_artifact: bool = False,
    summary_artifact_key: str = "dbt-build-task-summary",
    extra_command_args: Optional[List[str]] = None,
    stream_output: bool = True,
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
        create_summary_artifact: If True, creates a Prefect artifact on the task run
            with the dbt build results using the specified artifact key.
            Defaults to False.
        summary_artifact_key: The key under which to store
            the dbt build results artifact in Prefect.
            Defaults to 'dbt-build-task-summary'.
        extra_command_args: Additional command arguments to pass to the dbt build command.
        stream_output: If True, the output from the dbt command will be logged in Prefect
            as it happens.
            Defaults to True.

    Example:
    ```python
        from prefect import flow
        from prefect_dbt.cli.tasks import dbt_build_task

        @flow
        def dbt_test_flow():
            dbt_build_task(
                project_dir="/Users/test/my_dbt_project_dir",
                extra_command_args=["--model", "foo_model"]
            )
    ```

    Raises:
        ValueError: If required dbt_cli_profile is not provided
                    when needed for profile writing.
        RuntimeError: If the dbt build fails for any reason,
                    it will be indicated by the exception raised.
    """

    results = await trigger_dbt_cli_command.fn(
        command="build",
        profiles_dir=profiles_dir,
        project_dir=project_dir,
        overwrite_profiles=overwrite_profiles,
        dbt_cli_profile=dbt_cli_profile,
        create_summary_artifact=create_summary_artifact,
        summary_artifact_key=summary_artifact_key,
        extra_command_args=extra_command_args,
        stream_output=stream_output,
    )
    return results


@sync_compatible
@task
async def run_dbt_model(
    profiles_dir: Optional[Union[Path, str]] = None,
    project_dir: Optional[Union[Path, str]] = None,
    overwrite_profiles: bool = False,
    dbt_cli_profile: Optional[DbtCliProfile] = None,
    create_summary_artifact: bool = False,
    summary_artifact_key: str = "dbt-run-task-summary",
    extra_command_args: Optional[List[str]] = None,
    stream_output: bool = True,
):
    """
    Executes the 'dbt run' command within a Prefect task,
    and optionally creates a Prefect artifact summarizing the dbt model results.

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
        create_summary_artifact: If True, creates a Prefect artifact on the task run
            with the dbt model run results using the specified artifact key.
            Defaults to False.
        summary_artifact_key: The key under which to store
            the dbt model run results artifact in Prefect.
            Defaults to 'dbt-run-task-summary'.
        extra_command_args: Additional command arguments to pass to the dbt run command.
        stream_output: If True, the output from the dbt command will be logged in Prefect
            as it happens.
            Defaults to True.

    Example:
    ```python
        from prefect import flow
        from prefect_dbt.cli.tasks import dbt_run_task

        @flow
        def dbt_test_flow():
            dbt_run_task(
                project_dir="/Users/test/my_dbt_project_dir",
                extra_command_args=["--model", "foo_model"]
            )
    ```

    Raises:
        ValueError: If required dbt_cli_profile is not provided
                    when needed for profile writing.
        RuntimeError: If the dbt build fails for any reason,
                    it will be indicated by the exception raised.
    """

    results = await trigger_dbt_cli_command.fn(
        command="run",
        profiles_dir=profiles_dir,
        project_dir=project_dir,
        overwrite_profiles=overwrite_profiles,
        dbt_cli_profile=dbt_cli_profile,
        create_summary_artifact=create_summary_artifact,
        summary_artifact_key=summary_artifact_key,
        extra_command_args=extra_command_args,
        stream_output=stream_output,
    )

    return results


@sync_compatible
@task
async def run_dbt_test(
    profiles_dir: Optional[Union[Path, str]] = None,
    project_dir: Optional[Union[Path, str]] = None,
    overwrite_profiles: bool = False,
    dbt_cli_profile: Optional[DbtCliProfile] = None,
    create_summary_artifact: bool = False,
    summary_artifact_key: str = "dbt-test-task-summary",
    extra_command_args: Optional[List[str]] = None,
    stream_output: bool = True,
):
    """
    Executes the 'dbt test' command within a Prefect task,
    and optionally creates a Prefect artifact summarizing the dbt test results.

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
        create_summary_artifact: If True, creates a Prefect artifact on the task run
            with the dbt test results using the specified artifact key.
            Defaults to False.
        summary_artifact_key: The key under which to store
            the dbt test results artifact in Prefect.
            Defaults to 'dbt-test-task-summary'.
        extra_command_args: Additional command arguments to pass to the dbt test command.
        stream_output: If True, the output from the dbt command will be logged in Prefect
            as it happens.
            Defaults to True.

    Example:
    ```python
        from prefect import flow
        from prefect_dbt.cli.tasks import dbt_test_task

        @flow
        def dbt_test_flow():
            dbt_test_task(
                project_dir="/Users/test/my_dbt_project_dir",
                extra_command_args=["--model", "foo_model"]
            )
    ```

    Raises:
        ValueError: If required dbt_cli_profile is not provided
                    when needed for profile writing.
        RuntimeError: If the dbt build fails for any reason,
                    it will be indicated by the exception raised.
    """

    results = await trigger_dbt_cli_command.fn(
        command="test",
        profiles_dir=profiles_dir,
        project_dir=project_dir,
        overwrite_profiles=overwrite_profiles,
        dbt_cli_profile=dbt_cli_profile,
        create_summary_artifact=create_summary_artifact,
        summary_artifact_key=summary_artifact_key,
        extra_command_args=extra_command_args,
        stream_output=stream_output,
    )

    return results


@sync_compatible
@task
async def run_dbt_snapshot(
    profiles_dir: Optional[Union[Path, str]] = None,
    project_dir: Optional[Union[Path, str]] = None,
    overwrite_profiles: bool = False,
    dbt_cli_profile: Optional[DbtCliProfile] = None,
    create_summary_artifact: bool = False,
    summary_artifact_key: str = "dbt-snapshot-task-summary",
    extra_command_args: Optional[List[str]] = None,
    stream_output: bool = True,
):
    """
    Executes the 'dbt snapshot' command within a Prefect task,
    and optionally creates a Prefect artifact summarizing the dbt snapshot results.

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
        create_summary_artifact: If True, creates a Prefect artifact on the task run
            with the dbt snapshot results using the specified artifact key.
            Defaults to False.
        summary_artifact_key: The key under which to store
            the dbt snapshot results artifact in Prefect.
            Defaults to 'dbt-snapshot-task-summary'.
        extra_command_args: Additional command arguments to pass to the dbt snapshot command.
        stream_output: If True, the output from the dbt command will be logged in Prefect
            as it happens.
            Defaults to True.

    Example:
    ```python
        from prefect import flow
        from prefect_dbt.cli.tasks import dbt_snapshot_task

        @flow
        def dbt_test_flow():
            dbt_snapshot_task(
                project_dir="/Users/test/my_dbt_project_dir",
                extra_command_args=["--fail-fast"]
            )
    ```

    Raises:
        ValueError: If required dbt_cli_profile is not provided
                    when needed for profile writing.
        RuntimeError: If the dbt build fails for any reason,
                    it will be indicated by the exception raised.
    """

    results = await trigger_dbt_cli_command.fn(
        command="snapshot",
        profiles_dir=profiles_dir,
        project_dir=project_dir,
        overwrite_profiles=overwrite_profiles,
        dbt_cli_profile=dbt_cli_profile,
        create_summary_artifact=create_summary_artifact,
        summary_artifact_key=summary_artifact_key,
        extra_command_args=extra_command_args,
        stream_output=stream_output,
    )

    return results


@sync_compatible
@task
async def run_dbt_seed(
    profiles_dir: Optional[Union[Path, str]] = None,
    project_dir: Optional[Union[Path, str]] = None,
    overwrite_profiles: bool = False,
    dbt_cli_profile: Optional[DbtCliProfile] = None,
    create_summary_artifact: bool = False,
    summary_artifact_key: str = "dbt-seed-task-summary",
    extra_command_args: Optional[List[str]] = None,
    stream_output: bool = True,
):
    """
    Executes the 'dbt seed' command within a Prefect task,
    and optionally creates a Prefect artifact summarizing the dbt seed results.

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
        create_summary_artifact: If True, creates a Prefect artifact on the task run
            with the dbt seed results using the specified artifact key.
            Defaults to False.
        summary_artifact_key: The key under which to store
            the dbt seed results artifact in Prefect.
            Defaults to 'dbt-seed-task-summary'.
        extra_command_args: Additional command arguments to pass to the dbt seed command.
        stream_output: If True, the output from the dbt command will be logged in Prefect
            as it happens.
            Defaults to True.

    Example:
    ```python
        from prefect import flow
        from prefect_dbt.cli.tasks import dbt_seed_task

        @flow
        def dbt_test_flow():
            dbt_seed_task(
                project_dir="/Users/test/my_dbt_project_dir",
                extra_command_args=["--fail-fast"]
            )
    ```

    Raises:
        ValueError: If required dbt_cli_profile is not provided
                    when needed for profile writing.
        RuntimeError: If the dbt build fails for any reason,
                    it will be indicated by the exception raised.
    """

    results = await trigger_dbt_cli_command.fn(
        command="seed",
        profiles_dir=profiles_dir,
        project_dir=project_dir,
        overwrite_profiles=overwrite_profiles,
        dbt_cli_profile=dbt_cli_profile,
        create_summary_artifact=create_summary_artifact,
        summary_artifact_key=summary_artifact_key,
        extra_command_args=extra_command_args,
        stream_output=stream_output,
    )

    return results


@sync_compatible
@task
async def run_dbt_source_freshness(
    profiles_dir: Optional[Union[Path, str]] = None,
    project_dir: Optional[Union[Path, str]] = None,
    overwrite_profiles: bool = False,
    dbt_cli_profile: Optional[DbtCliProfile] = None,
    create_summary_artifact: bool = False,
    summary_artifact_key: str = "dbt-source-freshness-task-summary",
    extra_command_args: Optional[List[str]] = None,
    stream_output: bool = True,
):
    """
    Executes the 'dbt source freshness' command within a Prefect task,
    and optionally creates a Prefect artifact summarizing the dbt source freshness results.

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
        create_summary_artifact: If True, creates a Prefect artifact on the task run
            with the dbt source freshness results using the specified artifact key.
            Defaults to False.
        summary_artifact_key: The key under which to store
            the dbt source freshness results artifact in Prefect.
            Defaults to 'dbt-source-freshness-task-summary'.
        extra_command_args: Additional command arguments to pass to the dbt source freshness command.
        stream_output: If True, the output from the dbt command will be logged in Prefect
            as it happens.
            Defaults to True.

    Example:
    ```python
        from prefect import flow
        from prefect_dbt.cli.commands import run_dbt_source_freshness

        @flow
        def dbt_test_flow():
            run_dbt_source_freshness(
                project_dir="/Users/test/my_dbt_project_dir",
                extra_command_args=["--fail-fast"]
            )
    ```

    Raises:
        ValueError: If required dbt_cli_profile is not provided
                    when needed for profile writing.
        RuntimeError: If the dbt build fails for any reason,
                    it will be indicated by the exception raised.
    """

    results = await trigger_dbt_cli_command.fn(
        command="source freshness",
        profiles_dir=profiles_dir,
        project_dir=project_dir,
        overwrite_profiles=overwrite_profiles,
        dbt_cli_profile=dbt_cli_profile,
        create_summary_artifact=create_summary_artifact,
        summary_artifact_key=summary_artifact_key,
        extra_command_args=extra_command_args,
        stream_output=stream_output,
    )

    return results


def create_summary_markdown(run_results: dict[str, Any], command: str) -> str:
    """
    Creates a Prefect task artifact summarizing the results
    of the above predefined prefrect-dbt task.
    """
    prefix = "dbt" if not command.startswith("dbt") else ""
    markdown = f"# {prefix} {command} Task Summary\n"
    markdown += _create_node_summary_table_md(run_results=run_results)

    if (
        run_results["Error"] != []
        or run_results["Fail"] != []
        or run_results["Skipped"] != []
        or run_results["Warn"] != []
    ):
        markdown += "\n\n ## Unsuccessful Nodes ❌\n\n"
        markdown += _create_unsuccessful_markdown(run_results=run_results)

    if run_results["Success"] != []:
        successful_runs_str = ""
        for r in run_results["Success"]:
            if isinstance(r, (RunResult, FreshnessResult)):
                successful_runs_str += f"* {r.node.name}\n"
            elif isinstance(r, RunResultOutput):
                successful_runs_str += f"* {r.unique_id}\n"
            else:
                successful_runs_str += f"* {r}\n"
        markdown += f"""\n## Successful Nodes ✅\n\n{successful_runs_str}\n\n"""

    return markdown


def _create_node_info_md(node_name, resource_type, message, path, compiled_code) -> str:
    """
    Creates template for unsuccessful node information
    """
    markdown = f"""
**{node_name}**

Type: {resource_type}

Message: 

> {message}


Path: {path}

"""

    if compiled_code:
        markdown += f"""
Compiled code:

```sql
{compiled_code}
```
        """

    return markdown


def _create_node_summary_table_md(run_results: dict) -> str:
    """
    Creates a table for node summary
    """

    markdown = f"""
| Successes | Errors | Failures | Skips | Warnings |
| :-------: | :----: | :------: | :---: | :------: |
| {len(run_results["Success"])} |  {len(run_results["Error"])} | {len(run_results["Fail"])} | {len(run_results["Skipped"])} | {len(run_results["Warn"])} |
    """
    return markdown


def _create_unsuccessful_markdown(run_results: dict) -> str:
    """
    Creates markdown summarizing the results
    of unsuccessful nodes, including compiled code.
    """
    markdown = ""
    if len(run_results["Error"]) > 0:
        markdown += "\n### Errored Nodes:\n"
        for n in run_results["Error"]:
            markdown += _create_node_info_md(
                n.node.name,
                n.node.resource_type,
                n.message,
                n.node.path,
                (
                    n.node.compiled_code
                    if n.node.resource_type not in ["seed", "source"]
                    else None
                ),
            )
    if len(run_results["Fail"]) > 0:
        markdown += "\n### Failed Nodes:\n"
        for n in run_results["Fail"]:
            markdown += _create_node_info_md(
                n.node.name,
                n.node.resource_type,
                n.message,
                n.node.path,
                (
                    n.node.compiled_code
                    if n.node.resource_type not in ["seed", "source"]
                    else None
                ),
            )
    if len(run_results["Skipped"]) > 0:
        markdown += "\n### Skipped Nodes:\n"
        for n in run_results["Skipped"]:
            markdown += _create_node_info_md(
                n.node.name,
                n.node.resource_type,
                n.message,
                n.node.path,
                (
                    n.node.compiled_code
                    if n.node.resource_type not in ["seed", "source"]
                    else None
                ),
            )
    if len(run_results["Warn"]) > 0:
        markdown += "\n### Warned Nodes:\n"
        for n in run_results["Warn"]:
            markdown += _create_node_info_md(
                n.node.name,
                n.node.resource_type,
                n.message,
                n.node.path,
                (
                    n.node.compiled_code
                    if n.node.resource_type not in ["seed", "source"]
                    else None
                ),
            )
    return markdown


def consolidate_run_results(results: dbtRunnerResult) -> dict:
    run_results: Dict[str, List[str]] = {
        "Success": [],
        "Fail": [],
        "Skipped": [],
        "Error": [],
        "Warn": [],
    }

    if results.exception is None:
        for r in results.result.results:
            if r.status == NodeStatus.Fail:
                run_results["Fail"].append(r)
            elif r.status == NodeStatus.Error or r.status == NodeStatus.RuntimeErr:
                run_results["Error"].append(r)
            elif r.status == NodeStatus.Skipped:
                run_results["Skipped"].append(r)
            elif r.status == NodeStatus.Success or r.status == NodeStatus.Pass:
                run_results["Success"].append(r)
            elif r.status == NodeStatus.Warn:
                run_results["Warn"].append(r)

    return run_results
