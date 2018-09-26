# Licensed under LICENSE.md; also available at https://www.prefect.io/licenses/alpha-eula

import os
import subprocess
import tempfile
from collections import defaultdict
from typing import Any, Dict, Iterable, Iterator, List, Union

import cloudpickle

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
        self.reset_flow(self.flow_state)
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

    def reset_flow(self, state):
        map_counts = defaultdict(lambda: 0)
        mapped_tasks = {}
        edges = []
        for task in self.flow.sorted_tasks():
            old_edges = self.flow.edges_to(task)
            for edge in old_edges:
                if not edge.mapped:
                    if edge.upstream_task in mapped_tasks:
                        new_edges = [
                            prefect.core.edge.Edge(
                                upstream_task=t, downstream_task=task
                            )
                            for t in mapped_tasks[edge.upstream_task]
                        ]
                        edges.extend(new_edges)
                    else:
                        edges.append(edge)
                else:
                    # create copies corresponding to each mapped result
                    new_tasks = [task.copy() for _ in state.result[task]]
                    mapped_tasks[task] = new_tasks
                    for t in new_tasks:
                        t.name = task.name + "<mapped-{}>".format(map_counts[task.name])
                        map_counts[task.name] += 1

                    if edge.upstream_task in mapped_tasks:
                        upstream = [t for t in mapped_tasks[edge.upstream_task]]
                    else:
                        upstream = [edge.upstream_task for _ in range(len(new_tasks))]

                    new_edges = [
                        prefect.core.edge.Edge(
                            upstream_task=up, downstream_task=task, key=edge.key
                        )
                        for up, task in zip(upstream, new_tasks)
                    ]
                    edges.extend(new_edges)
                    states = state.result.pop(task)
                    for t, s in zip(new_tasks, states):
                        state.result[t] = s

        self.flow = prefect.Flow(edges=edges, name=self.flow.name)
        self.flow_state = state

    def compute_depths(self):
        flow = self.flow
        depths = {task: 0 for task in flow.tasks}
        for task in flow.sorted_tasks():
            depths[task] = max(
                [depths[ut] + 1 for ut in flow.upstream_tasks(task)], default=0
            )
        return depths
