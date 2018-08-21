import os
import subprocess

import prefect


class ShellTask(prefect.Task):
    """
    Task for running arbitrary shell commands.
    """

    def __init__(self, command, env=None, **kwargs):
        self.command = command
        self.env = env or dict()
        super().__init__(**kwargs)

    def run(self):
        current_env = os.environ.copy()
        current_env.update(self.env)
        out = subprocess.check_output(
            ["bash", "-c", self.command], stderr=subprocess.STDOUT, env=current_env
        )
        return out
