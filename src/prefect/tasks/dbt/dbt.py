import os
import yaml
from typing import Any

from prefect.tasks.shell import ShellTask
from prefect.utilities.tasks import defaults_from_attrs


class DbtShellTask(ShellTask):
    """
    Task for running dbt commands. It will create a profiles.yml file prior to running dbt commands.

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
            for different commands in a Flow
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
        from ccde.prefect.tasks.dbt import DbtShellTask

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
        **kwargs: Any
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
            log_stderr=log_stderr
        )

    @defaults_from_attrs("command", "env", "dbt_kwargs")
    def run(
        self, command: str = None, env: dict = None, dbt_kwargs: dict = None
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

        return super(DbtShellTask, self).run(command=command, env=env)
