import prefect


class GetIndexTask(prefect.Task):

    def __init__(self, index, **kwargs):
        self.index = index
        super().__init__(**kwargs)

    def run(self, task_result):
        return task_result[self.index]
