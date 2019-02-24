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
        - helper_fns (List[str], optional): a list of strings, each of which
            defines a shell function when executed by the shell; will be made available to
            the executed command
        - shell (string, optional): shell to run the command with; defaults to "bash"
        - **kwargs: additional keyword arguments to pass to the Task constructor

    Example:
        ```python
        from prefect import Flow
        from prefect.tasks.shell import ShellTask

        task = ShellTask()
        with Flow() as f:
            res = task(command='ls')

        out = f.run(return_tasks=[res])
        ```
    """

    def __init__(
        self,
        command: str = None,
        env: dict = None,
        helper_fns: List[str] = None,
        shell: str = "bash",
        **kwargs: Any
    ):
        self.command = command
        self.env = env
        self.helper_fns = helper_fns or []
        self.shell = shell
        super().__init__(**kwargs)

    @defaults_from_attrs("command", "env")
    def run(self, command: str = None, env: dict = None) -> bytes:  # type: ignore
        """
        Run the shell command.

        Args:
            - command (string): shell command to be executed; can also be
                provided at task initialization
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
            if self.helper_fns:
                tmp.write("\n".join(self.helper_fns).encode())
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
                raise prefect.engine.signals.FAIL(msg) from None
        return out
