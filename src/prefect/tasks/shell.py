import os
import subprocess
import tempfile
from typing import Any, List

import prefect
from prefect.utilities.tasks import defaults_from_attrs


class ShellTask(prefect.Task):
    """
    Task for running arbitrary shell commands.

    Args:
        - command (string, optional): shell command to be executed; can also be
            provided post-initialization by calling this task instance
        - env (dict, optional): dictionary of environment variables to use for
            the subprocess; can also be provided at runtime
        - helper_script (str, optional): a string representing a shell script, which
            will be executed prior to the `command` in the same process. Can be used to
            change directories, define helper functions, etc. when re-using this Task
            for different commands in a Flow
        - shell (string, optional): shell to run the command with; defaults to "bash"
        - **kwargs: additional keyword arguments to pass to the Task constructor

    Example:
        ```python
        from prefect import Flow
        from prefect.tasks.shell import ShellTask

        task = ShellTask(helper_script="cd ~")
        with Flow("My Flow") as f:
            # both tasks will be executed in home directory
            contents = task(command='ls')
            mv_file = task(command='mv .vimrc /.vimrc')

        out = f.run()
        ```
    """

    def __init__(
        self,
        command: str = None,
        env: dict = None,
        helper_script: str = None,
        shell: str = "bash",
        **kwargs: Any
    ):
        self.command = command
        self.env = env
        self.helper_script = helper_script
        self.shell = shell
        super().__init__(**kwargs)

    @defaults_from_attrs("command", "env")
    def run(self, command: str = None, env: dict = None) -> bytes:
        """
        Run the shell command.

        Args:
            - command (string): shell command to be executed; can also be
                provided at task initialization. Any variables / functions defined in
                `self.helper_script` will be available in the same process this command
                runs in
            - env (dict, optional): dictionary of environment variables to use for
                the subprocess

        Returns:
            - stdout + stderr (bytes): anything printed to standard out /
                standard error during command execution

        Raises:
            - prefect.engine.signals.FAIL: if command has an exit code other
                than 0
        """
        if command is None:
            raise TypeError("run() missing required argument: 'command'")

        current_env = os.environ.copy()
        current_env.update(env or {})
        with tempfile.NamedTemporaryFile(prefix="prefect-") as tmp:
            if self.helper_script:
                tmp.write(self.helper_script.encode())
                tmp.write("\n".encode())
            tmp.write(command.encode())
            tmp.flush()
            try:
                out = subprocess.check_output(
                    [self.shell, tmp.name], stderr=subprocess.STDOUT, env=current_env
                )
            except subprocess.CalledProcessError as exc:
                msg = "Command failed with exit code {0}: {1}".format(
                    exc.returncode, exc.output
                )
                raise prefect.engine.signals.FAIL(msg) from None  # type: ignore
        return out
