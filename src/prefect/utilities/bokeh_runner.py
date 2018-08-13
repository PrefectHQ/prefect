import cloudpickle
import os
import subprocess
import tempfile
from typing import Any, Dict, Iterable, Iterator, List, Union

from prefect.core import Task
from prefect.engine.flow_runner import FlowRunner
from prefect.engine.state import State


class BokehRunner(FlowRunner):
    def run(
        self,
        state: State = None,
        task_states: Dict[Task, State] = None,
        start_tasks: Iterable[Task] = None,
        parameters: Dict[str, Any] = None,
        executor: "prefect.engine.executors.Executor" = None,
        context: Dict[str, Any] = None,
        task_contexts: Dict[Task, Dict[str, Any]] = None,
        viz: bool = True,
    ) -> State:
        self.task_states = task_states or {}
        self.start_tasks = start_tasks or []
        self.parameters = parameters or {}
        self.flow_state = super().run(
            state=state,
            task_states=task_states,
            start_tasks=start_tasks,
            return_tasks=self.flow.tasks,
            parameters=parameters,
            executor=executor,
            context=context,
            task_contexts=task_contexts,
        )
        if viz:
            with tempfile.NamedTemporaryFile() as tmp:
                cloudpickle.dump(self, tmp)
                env = os.environ
                env.update({"BOKEH_DATA": tmp.name})
                tmp.flush()
                bokeh_app = os.path.join(os.path.dirname(__file__), "bokehapp.py")
                subprocess.run(
                    "bokeh serve --show {}".format(bokeh_app).split(), env=env
                )
        return self.flow_state

    def compute_depths(self):
        flow = self.flow
        depths = {task: 0 for task in flow.tasks}
        for task in flow.sorted_tasks():
            depths[task] = max(
                [depths[ut] + 1 for ut in flow.upstream_tasks(task)], default=0
            )
        return depths
