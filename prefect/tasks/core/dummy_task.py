import prefect

class DummyTask(prefect.Task):
    """
    A task that doesn't do anything but can be used as a placeholder.
    """

    def run(self):
        pass
