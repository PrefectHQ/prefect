# Licensed under LICENSE.md; also available at https://www.prefect.io/licenses/alpha-eula
"""
The BokehRunner class is a special [FlowRunner](../engine/flow_runner.html) subclass meant for debugging, exploring, visualizing, and
demonstrating Prefect Flow state logic.

This is _not_ intended as a replacement for a full-fledge UI, but simply an additional tool
for locally inspecting and groking how Prefect handles Flow execution logic, including how
states propagate throughout the Flow.

**Example:**

```python
from prefect import Flow, task
from prefect.utilities.bokeh_runner import BokehRunner

@task
def add(x, y):
    return x + y

@task
def div(x, y):
    return x / y

with Flow("bokeh-example") as f:
    x, y = Parameter("x"), Parameter("y")
    t1 = add(x, y)
    t2 = div(x, y)
    t3 = add(t1, t2)

BokehRunner(flow=f).run(parameters={"x": 5, "y": 0}) # opens a new webapp
```

<img src='/bokeh_runner_doc_example.png'>
"""

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

    Example:
        ```python
        from prefect.utilities.bokeh_runner import BokehRunner
        from prefect import task, Flow

        @task
        def add(x, y):
            return x + y

        with Flow() as f:
            one = add(0, 1)
            two = add(0, 2)
            res = add(one, two)

        BokehRunner(flow=f).run() # opens up a webapp
        ```
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

        Args:
            - state (State, optional): starting state for the Flow. Defaults to
                `Pending`
            - task_states (dict, optional): dictionary of task states to begin
                computation with, with keys being Tasks and values their corresponding state
            - start_tasks ([Task], optional): list of Tasks to begin computation
                from; if any `start_tasks` have upstream dependencies, their states may need to be provided as well.
                Defaults to `self.flow.root_tasks()`
            - parameters (dict, optional): dictionary of any needed Parameter
                values, with keys being strings representing Parameter names and values being their corresponding values
            - executor (Executor, optional): executor to use when performing
                computation; defaults to the executor provided in your prefect configuration
            - context (dict, optional): prefect.Context to use for execution
            - task_contexts (dict, optional): dictionary of individual contexts
                to use for each Task run
            - title (str, optional): optional title for the webapp plot;
                defaults to "Prefect Flow Interactive Demonstration: {{ flow.name }}"
            - viz (bool, optional): if `False`, will simply run the Flow and
                return its state (with all tasks returned) without opening the webapp.

        Returns:
            - State: `State` representing the final post-run state of the `Flow`.

        Raises:
            - ValueError: if any throttle values are `<= 0`
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
        self._reset_flow(self.flow_state)
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

    def _reset_flow(self, state):
        """
        Expands out any mapped tasks into the appropriate number of copies, based
        on the data provided in `state`.  Creates a new Flow and a new flow state
        and saves them in `self.flow` and `self.flow_state` attributes, in place.

        Args:
            - state (State): the final, post-run Flow state used for determining
                how many task copies to make for mapped tasks

        Returns:
            - None
        """
        map_counts = defaultdict(lambda: 0)
        mapped_tasks = {}
        edges = []

        for task in self.flow.sorted_tasks():
            old_edges = self.flow.edges_to(task)
            mapped_edges = [e for e in old_edges if e.mapped]
            unmapped_edges = [e for e in old_edges if not e.mapped]

            # update unmapped edges
            for edge in unmapped_edges:
                if edge.upstream_task in mapped_tasks:
                    new_edges = [
                        prefect.core.edge.Edge(upstream_task=t, downstream_task=task)
                        for t in mapped_tasks[edge.upstream_task]
                    ]
                    edges.extend(new_edges)
                else:
                    edges.append(edge)

            # update mapped edges
            for edge in mapped_edges:
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

    def _compute_depths(self):
        flow = self.flow
        depths = {task: 0 for task in flow.tasks}
        for task in flow.sorted_tasks():
            depths[task] = max(
                [depths[ut] + 1 for ut in flow.upstream_tasks(task)], default=0
            )
        return depths
