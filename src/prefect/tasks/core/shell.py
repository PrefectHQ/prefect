import subprocess

import prefect


class ShellTask(prefect.Task):
    """
    Task for running arbitrary shell commands.
    """
    def __init__(self, command, **kwargs):
        self.command = command
        super().__init__(**kwargs)

    def run(self):
        out = subprocess.check_output(["bash", "-c", self.command],
                                      stderr=subprocess.STDOUT)
        return out
