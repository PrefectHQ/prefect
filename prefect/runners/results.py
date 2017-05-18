from collections import namedtuple

RunResult = namedtuple('RunResult', ['state', 'result'])


class Progress:

    def __init__(self, progress=None):
        self.set_progress(progress)

    def set_progress(self, progress):
        self.progress = progress
