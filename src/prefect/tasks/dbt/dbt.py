import os
from typing import Any

import yaml

from prefect.core.task import Task
from prefect.tasks.shell import ShellTask
from prefect.utilities.tasks import defaults_from_attrs
from prefect.backend.artifacts import create_markdown_artifact

from .dbt_cloud_utils import (
    DbtCloudListArtifactsFailed,
    list_run_artifact_links,
    trigger_job_run,
    wait_for_job_run,
)


class DbtShellTask(ShellTask):
    """
    Task for running dbt commands. It will create a profiles.yml file prior to running dbt commands.

    This task inherits all configuration options from the
    [ShellTask](https://docs.prefect.io/api/latest/tasks/shell.html#shelltask).

    Args:
        - command (string, optional): dbt command to be executed; can also be
            provided post-initialization by calling this task instance
        - dbt_kwargs (dict, optional): keyword arguments used to populate the profiles.yml file
            (e.g.  `{'type': 'snowflake', 'threads': 4, 'account': '...'}`); can also be
            provided at runtime
        - env (dict, optional): dictionary of environment variables to use for
            the subprocess; can also be provided at runtime
        - environment (string, optional): The default target your dbt project will use
        - overwrite_profiles (boolean, optional): flag to indicate whether existing
            profiles.yml file should be overwritten; defaults to `False`
        - profile_name (string, optional): Profile name used for populating the profile name of
            profiles.yml
        - profiles_dir (string, optional): path to directory where the profile.yml file will be
            contained
        - set_profiles_envar (boolean, optional): flag to indicate whether DBT_PROFILES_DIR
            should be set to the provided profiles_dir; defaults to `True`
        - helper_script (str, optional): a string representing a shell script, which
            will be executed prior to the `command` in the same process. Can be used to
            change directories, define helper functions, etc. when re-using this Task
            for different commands in a Flow; can also be provided at runtime
        - shell (string, optional): shell to run the command with; defaults to "bash"
        - return_all (bool, optional): boolean specifying whether this task should return all
            lines of stdout as a list, or just the last line as a string; defaults to `False`
        - log_stderr (bool, optional): boolean specifying whether this task
            should log the output from stderr in the case of a non-zero exit code;
            defaults to `False`
        - **kwargs: additional keyword arguments to pass to the Task constructor

    Example:
        ```python
        from prefect import Flow
        from prefect.tasks.dbt import DbtShellTask

        with Flow(name="dbt_flow") as f:
            task = DbtShellTask(
                profile_name='default',
                environment='test',
                dbt_kwargs={
                    'type': 'snowflake',
                    'threads': 1,
                    'account': 'account.us-east-1'
                },
                overwrite_profiles=True,
                profiles_dir=test_path
            )(command='dbt run')

        out = f.run()
        ```
    """

    def __init__(
        self,
        command: str = None,
        profile_name: str = None,
        env: dict = None,
        environment: str = None,
        overwrite_profiles: bool = False,
        profiles_dir: str = None,
        set_profiles_envar: bool = True,
        dbt_kwargs: dict = None,
        helper_script: str = None,
        shell: str = "bash",
        return_all: bool = False,
        log_stderr: bool = False,
        **kwargs: Any,
    ):
        self.command = command
        self.profile_name = profile_name
        self.environment = environment
        self.overwrite_profiles = overwrite_profiles
        self.profiles_dir = profiles_dir
        self.set_profiles_envar = set_profiles_envar
        self.dbt_kwargs = dbt_kwargs or {}
        super().__init__(
            **kwargs,
            command=command,
            env=env,
            helper_script=helper_script,
            shell=shell,
            return_all=return_all,
            log_stderr=log_stderr,
        )

    @defaults_from_attrs("command", "env", "helper_script", "dbt_kwargs")
    def run(
        self,
        command: str = None,
        env: dict = None,
        helper_script: str = None,
        dbt_kwargs: dict = None,
    ) -> str:
        """
        If no profiles.yml file is found or if overwrite_profiles flag is set to True, this
        will first generate a profiles.yml file in the profiles_dir directory. Then run the dbt
        cli shell command.

        Args:
            - command (string): shell command to be executed; can also be
                provided at task initialization. Any variables / functions defined in
                `self.helper_script` will be available in the same process this command
                runs in
            - env (dict, optional): dictionary of environment variables to use for
                the subprocess
            - helper_script (str, optional): a string representing a shell script, which
                will be executed prior to the `command` in the same process. Can be used to
                change directories, define helper functions, etc. when re-using this Task
                for different commands in a Flow
            - dbt_kwargs(dict, optional): keyword arguments used to populate the profiles.yml file

        Returns:
            - stdout (string): if `return_all` is `False` (the default), only the last line of
                stdout is returned, otherwise all lines are returned, which is useful for
                passing result of shell command to other downstream tasks. If there is no
                output, `None` is returned.

        Raises:
            - prefect.engine.signals.FAIL: if command has an exit code other
                than 0
        """
        DEFAULT_PROFILES_DIR = os.path.join(os.path.expanduser("~"), ".dbt")
        profiles_exists = False
        if os.getenv("DBT_PROFILES_DIR"):
            dbt_profiles_dir = os.path.expanduser(
                os.getenv("DBT_PROFILES_DIR", DEFAULT_PROFILES_DIR)
            )
            profiles_exists = os.path.exists(
                os.path.join(dbt_profiles_dir, "profiles.yml")
            )
        elif self.profiles_dir:
            profiles_exists = os.path.exists(
                os.path.join(self.profiles_dir, "profiles.yml")
            )
        else:
            profiles_exists = os.path.exists(
                os.path.join(DEFAULT_PROFILES_DIR, "profiles.yml")
            )

        dbt_kwargs = {**self.dbt_kwargs, **(dbt_kwargs or {})}

        if self.overwrite_profiles or not profiles_exists:
            profile = {
                self.profile_name: {
                    "outputs": {self.environment: dbt_kwargs},
                    "target": self.environment,
                }
            }

            if not self.profiles_dir:
                try:
                    os.mkdir(DEFAULT_PROFILES_DIR)
                except OSError:
                    self.logger.warning(
                        "Creation of directory %s has failed" % DEFAULT_PROFILES_DIR
                    )
                profile_path = os.path.join(DEFAULT_PROFILES_DIR, "profiles.yml")
                self.profiles_dir = DEFAULT_PROFILES_DIR
            else:
                profile_path = os.path.join(self.profiles_dir, "profiles.yml")

            with open(profile_path, "w+") as yaml_file:
                yaml.dump(profile, yaml_file, default_flow_style=False)

        if self.set_profiles_envar:
            os.environ["DBT_PROFILES_DIR"] = self.profiles_dir

        return super(DbtShellTask, self).run(
            command=command, env=env, helper_script=helper_script
        )


class DbtCloudRunJob(Task):
    """
    Task for running a dbt Cloud job using dbt Cloud APIs v2.
    For info about dbt Cloud APIs, please refer to https://docs.getdbt.com/dbt-cloud/api-v2
    Please note that this task will fail if any call to dbt Cloud APIs fails.

    Running this task will generate a markdown artifact viewable in the Prefect UI. The artifact
    will contain links to the dbt artifacts generate as a result of the job run.

    Args:
        - cause (string): A string describing the reason for triggering the job run
        - account_id (int, optional): dbt Cloud account ID.
            Can also be passed as an env var.
        - job_id (int, optional): dbt Cloud job ID
        - token (string, optional): dbt Cloud token.
            Please note that this token must have access at least to the dbt Trigger Job API.
        - additional_args (dict, optional): additional information to pass to the Trigger Job API.
            For a list of the possible information,
            have a look at: https://docs.getdbt.com/dbt-cloud/api-v2#operation/triggerRun
        - account_id_env_var_name (string, optional):
            the name of the env var that contains the dbt Cloud account ID.
            Defaults to DBT_CLOUD_ACCOUNT_ID.
            Used only if account_id is None.
        - job_id_env_var_name (string, optional):
            the name of the env var that contains the dbt Cloud job ID
            Default to DBT_CLOUD_JOB_ID.
            Used only if job_id is None.
        - token_env_var_name (string, optional):
            the name of the env var that contains the dbt Cloud token
            Default to DBT_CLOUD_TOKEN.
            Used only if token is None.
        - wait_for_job_run_completion (boolean, optional):
            Whether the task should wait for the job run completion or not.
            Default to False.
        - max_wait_time (int, optional): The number of seconds to wait for the dbt Cloud
            job to finish.
            Used only if wait_for_job_run_completion = True.
        - domain (str, optional): Custom domain for API call. Defaults to `cloud.getdbt.com`.

    Returns:
        - (dict) if wait_for_job_run_completion = False, then returns the trigger run result.
            The trigger run result is the dict under the "data" key.
            Have a look at the Response section at:
            https://docs.getdbt.com/dbt-cloud/api-v2#operation/triggerRun

          if wait_for_job_run_completion = True, then returns the get job result.
            The get job result is the dict under the "data" key.
            Have a look at the Response section at:
            https://docs.getdbt.com/dbt-cloud/api-v2#operation/getRunById

    Raises:
        - prefect.engine.signals.FAIL: whether there's a HTTP status code != 200
            and also whether the run job result has a status != 10 AND "finished_at" is not None
            Have a look at the status codes at:
            https://docs.getdbt.com/dbt-cloud/api-v2#operation/getRunById
    """

    def __init__(
        self,
        cause: str = None,
        account_id: int = None,
        job_id: int = None,
        token: str = None,
        additional_args: dict = None,
        account_id_env_var_name: str = "DBT_CLOUD_ACCOUNT_ID",
        job_id_env_var_name: str = "DBT_CLOUD_JOB_ID",
        token_env_var_name: str = "DBT_CLOUD_TOKEN",
        wait_for_job_run_completion: bool = False,
        max_wait_time: int = None,
        domain: str = "cloud.getdbt.com",
    ):
        super().__init__()
        self.token = token if token else os.environ.get(token_env_var_name, None)
        self.account_id = account_id
        if account_id is None and account_id_env_var_name in os.environ:
            self.account_id = int(os.environ[account_id_env_var_name])
        self.job_id = job_id
        if job_id is None and job_id_env_var_name in os.environ:
            self.job_id = int(os.environ[job_id_env_var_name])
        self.cause = cause
        self.additional_args = additional_args
        self.wait_for_job_run_completion = wait_for_job_run_completion
        self.max_wait_time = max_wait_time
        self.domain = domain or "cloud.getdbt.com"

    @defaults_from_attrs(
        "cause",
        "account_id",
        "job_id",
        "token",
        "additional_args",
        "wait_for_job_run_completion",
        "max_wait_time",
        "domain",
    )
    def run(
        self,
        cause: str = None,
        account_id: int = None,
        job_id: int = None,
        token: str = None,
        additional_args: dict = None,
        account_id_env_var_name: str = "ACCOUNT_ID",
        job_id_env_var_name: str = "JOB_ID",
        token_env_var_name: str = "DBT_CLOUD_TOKEN",
        wait_for_job_run_completion: bool = False,
        max_wait_time: int = None,
        domain: str = None,
    ) -> dict:
        """
        All params available to the run method can also be passed during initialization.

        Args:
            - cause (string): A string describing the reason for triggering the job run
            - account_id (int, optional): dbt Cloud account ID.
                Can also be passed as an env var.
            - job_id (int, optional): dbt Cloud job ID
            - token (string, optional): dbt Cloud token.
                Please note that this token must have access at least to the dbt Trigger Job API.
            - additional_args (dict, optional): additional information to pass to the Trigger Job API.
                For a list of the possible information,
                have a look at: https://docs.getdbt.com/dbt-cloud/api-v2#operation/triggerRun
            - account_id_env_var_name (string, optional):
                the name of the env var that contains the dbt Cloud account ID.
                Defaults to DBT_CLOUD_ACCOUNT_ID.
                Used only if account_id is None.
            - job_id_env_var_name (string, optional):
                the name of the env var that contains the dbt Cloud job ID
                Default to DBT_CLOUD_JOB_ID.
                Used only if job_id is None.
            - token_env_var_name (string, optional):
                the name of the env var that contains the dbt Cloud token
                Default to DBT_CLOUD_TOKEN.
                Used only if token is None.
            - wait_for_job_run_completion (boolean, optional):
                Whether the task should wait for the job run completion or not.
                Default to False.
            - max_wait_time (int, optional): The number of seconds to wait for the dbt Cloud
                job to finish.
                Used only if wait_for_job_run_completion = True.
        - domain (str, optional): Custom domain for API call. Defaults to `cloud.getdbt.com`.

        Returns:
            - (dict) if wait_for_job_run_completion = False, then returns the trigger run result.
                The trigger run result is the dict under the "data" key.
                Have a look at the Response section at:
                https://docs.getdbt.com/dbt-cloud/api-v2#operation/triggerRun

              if wait_for_job_run_completion = True, then returns the get job result.
                The get job result is the dict under the "data" key. Links to the dbt artifacts are
                also included under the `artifact_urls` key.
                Have a look at the Response section at:
                https://docs.getdbt.com/dbt-cloud/api-v2#operation/getRunById

        Raises:
            - prefect.engine.signals.FAIL: whether there's a HTTP status code != 200
                and also whether the run job result has a status != 10 AND "finished_at" is not None
                Have a look at the status codes at:
                https://docs.getdbt.com/dbt-cloud/api-v2#operation/getRunById
        """
        if cause is None:
            raise ValueError(
                """
                Cause cannot be None.
                Please provide a cause to trigger the dbt Cloud job.
                """
            )

        if account_id is None and account_id_env_var_name in os.environ:
            account_id = int(os.environ[account_id_env_var_name])

        if account_id is None:
            raise ValueError(
                """
                dbt Cloud Account ID cannot be None.
                Please provide an Account ID or the name of the env var that contains it.
                """
            )

        if job_id is None and job_id_env_var_name in os.environ:
            job_id = int(os.environ[job_id_env_var_name])

        if job_id is None:
            raise ValueError(
                """
                dbt Cloud Job ID cannot be None.
                Please provide a Job ID or the name of the env var that contains it.
                """
            )

        if domain is None:
            domain = "cloud.getdbt.com"

        if token is None and token_env_var_name in os.environ:
            token = os.environ.get(token_env_var_name)

        if token is None:
            raise ValueError(
                """
                dbt Cloud token cannot be None.
                Please provide a token or the name of the env var that contains it.
                """
            )

        run = trigger_job_run(
            account_id=account_id,
            job_id=job_id,
            cause=cause,
            additional_args=additional_args,
            token=token,
            domain=domain,
        )
        if wait_for_job_run_completion:
            job_run_result = wait_for_job_run(
                account_id=account_id,
                run_id=run["id"],
                token=token,
                max_wait_time=max_wait_time,
                domain=domain,
            )

            artifact_links = []
            try:
                artifact_links = list_run_artifact_links(
                    account_id=account_id, run_id=run["id"], token=token, domain=domain
                )

                markdown = f"Artifacts for dbt Cloud run {run['id']} of job {job_id}\n"
                for link, name in artifact_links:
                    markdown += f"- [{name}]({link})\n"
                create_markdown_artifact(markdown)

            except DbtCloudListArtifactsFailed as err:
                self.logger.warning(
                    f"Unable to retrieve artifacts generated by dbt Cloud job run: {err}"
                )

            job_run_result["artifact_urls"] = [link for link, _ in artifact_links]

            return job_run_result

        else:
            return run
