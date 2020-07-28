import os
import tempfile
from subprocess import PIPE, STDOUT, Popen
from typing import Any

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
        - return_all (bool, optional): boolean specifying whether this task
            should return all lines of stdout as a list, or just the last line
            as a string; defaults to `False`
        - log_stderr (bool, optional): boolean specifying whether this task
            should log the output from stderr in the case of a non-zero exit code;
            defaults to `False`
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
        return_all: bool = False,
        log_stderr: bool = False,
        **kwargs: Any
    ):
        self.command = command
        self.env = env
        self.helper_script = helper_script
        self.shell = shell
        self.return_all = return_all
        self.log_stderr = log_stderr
        super().__init__(**kwargs)

    @defaults_from_attrs("command", "env")
    def run(self, command: str = None, env: dict = None) -> str:
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
            - stdout (string): if `return_all` is `False` (the default), only
                the last line of stdout is returned, otherwise all lines are
                returned, which is useful for passing result of shell command
                to other downstream tasks. If there is no output, `None` is
                returned.

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
            with Popen(
                [self.shell, tmp.name], stdout=PIPE, stderr=STDOUT, env=current_env
            ) as sub_process:
                lines = []
                line = None
                for raw_line in iter(sub_process.stdout.readline, b""):
                    line = raw_line.decode("utf-8").rstrip()
                    if self.return_all:
                        lines.append(line)
                    else:
                        # if we're returning all, we don't log every line
                        self.logger.debug(line)
                sub_process.wait()
                if sub_process.returncode:
                    msg = "Command failed with exit code {}".format(
                        sub_process.returncode,
                    )
                    self.logger.error(msg)

                    if self.log_stderr:
                        self.logger.error("\n".join(lines))

                    raise prefect.engine.signals.FAIL(msg) from None  # type: ignore
        if self.return_all:
            return lines
        else:
            return line
