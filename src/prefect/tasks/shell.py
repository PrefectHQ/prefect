import os
import tempfile
from subprocess import PIPE, STDOUT, Popen
from typing import Any, List, Union, Optional

import prefect
from prefect.utilities.tasks import defaults_from_attrs


class ShellTask(prefect.Task):
    """
    Task for running arbitrary shell commands.

    NOTE: This task combines stderr and stdout because reading from both
          streams without blocking is tricky.

    Args:
        - command (string, optional): shell command to be executed; can also be
            provided post-initialization by calling this task instance
        - env (dict, optional): dictionary of environment variables to use for
            the subprocess; can also be provided at runtime
        - helper_script (str, optional): a string representing a shell script, which
            will be executed prior to the `command` in the same process. Can be used to
            change directories, define helper functions, etc. when re-using this Task
            for different commands in a Flow; can also be provided at runtime
        - shell (string, optional): shell to run the command with; defaults to "bash"
        - return_all (bool, optional): boolean specifying whether this task
            should return all lines of stdout as a list, or just the last line
            as a string; defaults to `False`
        - log_stderr (bool, optional): boolean specifying whether this task should log
            the output in the case of a non-zero exit code; defaults to `False`. This
             actually logs both stderr and stdout and will only log the last line of
             output unless `return_all` is `True`
        - stream_output (bool, optional): specifies whether this task should log
            the output as it occurs. If enabled, `log_stderr` will be ignored as the
            output will have already been logged. defaults to `False`
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
        stream_output: bool = False,
        **kwargs: Any
    ):
        self.command = command
        self.env = env
        self.helper_script = helper_script
        self.shell = shell
        self.return_all = return_all
        self.log_stderr = log_stderr
        self.stream_output = stream_output
        super().__init__(**kwargs)

    @defaults_from_attrs("command", "env", "helper_script")
    def run(
        self, command: str = None, env: dict = None, helper_script: str = None
    ) -> Optional[Union[str, List[str]]]:
        """
        Run the shell command.

        Args:
            - command (string): shell command to be executed; can also be
                provided at task initialization. Any variables / functions defined in
                `helper_script` will be available in the same process this command
                runs in
            - env (dict, optional): dictionary of environment variables to use for
                the subprocess
            - helper_script (str, optional): a string representing a shell script, which
                will be executed prior to the `command` in the same process. Can be used to
                change directories, define helper functions, etc. when re-using this Task
                for different commands in a Flow

        Returns:
            - output (string): if `return_all` is `False` (the default), only
                the last line of output is returned, otherwise all lines are
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
            if helper_script:
                tmp.write(helper_script.encode())
                tmp.write("\n".encode())
            tmp.write(command.encode())
            tmp.flush()
            with Popen(
                [self.shell, tmp.name], stdout=PIPE, stderr=STDOUT, env=current_env
            ) as sub_process:
                line = None
                lines = []
                for raw_line in iter(sub_process.stdout.readline, b""):
                    line = raw_line.decode("utf-8").rstrip()

                    if self.return_all:
                        lines.append(line)

                    if self.stream_output:
                        self.logger.debug(line)

                sub_process.wait()
                if sub_process.returncode:
                    msg = "Command failed with exit code {}".format(
                        sub_process.returncode,
                    )

                    self.logger.error(msg)

                    if self.log_stderr and not self.stream_output:
                        self.logger.error("\n".join(lines) if self.return_all else line)

                    raise prefect.engine.signals.FAIL(
                        msg,
                        result=lines if self.return_all else line,
                    )

        return lines if self.return_all else line
