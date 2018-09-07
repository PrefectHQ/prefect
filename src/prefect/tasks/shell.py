import os
import subprocess

import prefect


class ShellTask(prefect.Task):
    """
    Task for running arbitrary shell commands.

    Args:
        - shell (string, optional): shell to run the command with; defaults to "bash"
        - command (string, optional): shell command to be executed; can also be
            provided post-initialization by calling this task instance
        - **kwargs: additional keyword arguments to pass to the Task constructor
    """

    def __init__(self, shell="bash", command=None, **kwargs):
        self.shell = shell
        self.command = command
        super().__init__(**kwargs)

    def run(self, command=None, env=None):
        """
        Run the shell command.

        Args:
            - command (string): shell command to be executed; can also be
                provided at task initialization
            - env (dict, optional): dictionary of environment variables to use for
                the subprocess; if provided, will override all other environment variables present
                on the system

        Returns:
            - stdout + stderr (bytes): anything printed to standard out /
                standard error during command execution

        Raises:
            - prefect.engine.signals.FAIL: if command has an exit code other
                than 0
        """
        command = command or self.command
        if command is None:
            raise TypeError("run() missing required argument: 'command'")

        current_env = env or os.environ.copy()
        try:
            out = subprocess.check_output(
                [self.shell, "-c", command], stderr=subprocess.STDOUT, env=current_env
            )
        except subprocess.CalledProcessError as exc:
            msg = "Command failed with exit code {0}: {1}".format(
                exc.returncode, exc.output
            )
            raise prefect.engine.signals.FAIL(msg) from None
        return out
