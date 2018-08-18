# Licensed under LICENSE.md; also available at https://www.prefect.io/licenses/alpha-eula

import prefect
from prefect import Task


class GetResumeLink(Task):
    def __init__(self, start_tasks=None, name=None, **kwargs):
        self.start_tasks = start_tasks

        super().__init__(name=name, **kwargs)

    def run(self):
        client = prefect.Client()
        return client.flow_runs.get_resume_url(start_tasks=self.start_tasks)
