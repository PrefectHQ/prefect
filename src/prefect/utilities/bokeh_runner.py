import cloudpickle
import dask
import datetime
import os
import networkx as nx
import subprocess
import tempfile
from contextlib import contextmanager
from typing import Any, Callable, Dict, Iterable, Iterator, List, Union

from prefect.core import Flow, Task
from prefect.engine.flow_runner import handle_signals, FlowRunner
from prefect.engine.state import Failed, Pending, Running, State, Success


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
        self.flow_state = super().run(state=state, task_states=task_states, start_tasks=start_tasks, return_tasks=self.flow.tasks, parameters=parameters, executor=executor, context=context, task_contexts=task_contexts)
        if viz:
            with tempfile.NamedTemporaryFile() as tmp:
                cloudpickle.dump(self, tmp)
                env = os.environ
                env.update({"BOKEH_DATA": tmp.name})
                tmp.flush()
                bokeh_app = os.path.join(os.path.dirname(__file__), 'bokehapp.py')
                subprocess.run("bokeh serve --show {}".format(bokeh_app).split(), env=env)
        return self.flow_state

    def compute_depths(self):
        flow = self.flow
        depths = {task: 0 for task in flow.tasks}
        for task in flow.sorted_tasks():
            depths[task] = max([depths[ut] + 1 for ut in flow.upstream_tasks(task)], default=0)
        return depths

#class BokehExecutor(Executor):
#    @contextmanager
#    def start(self) -> Iterable[None]:
#        self.graph = nx.DiGraph()
#        self.task_depth = {}
#
#        with dask.config.set(scheduler="synchronous") as cfg:
#            yield cfg
#
#    def submit(self, fn: Callable, *args: Any, **kwargs: Any) -> Any:
#        """
#        Submit a function to the executor for execution. Returns a future
#        """
#        future = dask.delayed(fn)(*args, **kwargs)
#        if fn.__name__ == 'run':
#            task = fn.__self__.task
#            upstream = kwargs.get("upstream_states", {})
#            self.task_depth[task] = max([self.task_depth[u] + 1 for u in upstream.keys()], default=0)
#            self.graph.add_node(task, state=kwargs.get("state"), future=future, depth=self.task_depth[task])
#            for up_task, edge in upstream.items():
#                self.graph.add_edge(up_task, task)
#
#        return future
#
#    def wait(self, futures: Iterable, timeout: datetime.timedelta = None) -> Iterable:
#        """
#        Compile the Bokeh graph and perform iterative, button-clickable execution!
#        """
#        with tempfile.NamedTemporaryFile() as tmp:
#            cloudpickle.dump(self.graph, tmp)
#            env = os.environ
#            env.update({"BOKEH_DATA": tmp.name})
#            tmp.flush()
#            subprocess.run("bokeh serve --show /Users/chris/Developer/bokeh/flowgraph.py".split(), env=env)
#
#        computed = dask.compute(futures)
#        return computed[0]
