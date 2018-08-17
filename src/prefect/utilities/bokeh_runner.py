import cloudpickle
import os
import subprocess
import tempfile
from typing import Any, Dict, Iterable, Iterator, List, Union

import prefect


try:
    import bokeh
except ImportError:
    msg = (
        "This feature requires bokeh.\n"
        "Try re-installing prefect with `pip install prefect[viz]`"
    )
    raise ImportError(msg)


class BokehRunner(prefect.engine.flow_runner.FlowRunner):
    """
    The BokehRunner class is a special [FlowRunner](../engine/flow_runner.html) subclass meant for debugging, exploring, visualizing, and
    demonstrating Prefect Flow state logic.

    Initialized and handled exactly like the standard FlowRunner class.
    """

    def run(
        self,
        state=None,
        task_states=None,
        start_tasks=None,
        parameters=None,
        executor=None,
        context=None,
        task_contexts=None,
        title=None,
        viz=True,
    ):
        """
        Runs the Flow, and then opens up a Bokeh webapp for retroactively inspecting
        the execution of the Flow.
        """
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
        self.title = title or "Prefect Flow Interactive Demonstration: {}".format(
            self.flow.name
        )
        if viz:
            with tempfile.NamedTemporaryFile() as tmp:
                cloudpickle.dump(self, tmp)
                env = os.environ
                env.update({"BOKEH_RUNNER": tmp.name})
                tmp.flush()
                bokeh_app = os.path.join(os.path.dirname(__file__), "bokeh_app.py")
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
