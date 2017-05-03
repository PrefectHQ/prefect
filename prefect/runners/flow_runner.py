import datetime
import prefect
from prefect.runners.task_runner import TaskRunner
import uuid


class FlowRunner:
    """
    The FlowRunner class takes a Flow and executes a FlowRun with a specific
    id.

    The FlowRunner is responsible for creating TaskRunners for each task in
    the flow and waits for them to complete. It returns the flow's state.
    """

    def __init__(self, flow, executor=None, run_id=None):

        self.flow = flow
        if run_id is None:
            run_id = uuid.uuid4().hex
        self.run_id = run_id

        if executor is None:
            executor = getattr(
                prefect.runners.executors,
                prefect.config.get('prefect', 'default_executor'))()
        self.executor = executor

    def run(self, state=None, **params):

        if state is None:
            state = prefect.state.FlowRunState()

        for req in self.flow.required_params:
            if req not in params:
                raise ValueError(
                    'A required parameter was not provided: {}'.format(req))

        context = {
            'dt': None,  #TODO
            'as_of_dt': None,  # TODO
            'last_dt': None,  # TODO
            'flow_id': self.flow.id,
            'flow_namespace': self.flow.namespace,
            'flow_name': self.flow.name,
            'flow_version': self.flow.version,
            'run_id': self.run_id,
            'params': params,
        }

        task_results = {}

        with self.executor() as executor:

            for task in self.flow.sorted_tasks():

                task_runner = TaskRunner(
                    task=task, executor=self.executor, run_id=self.run_id)

                upstream_edges = []
                for edge in self.flow.edges_to(task):
                    edge = edge.as_dict()
                    edge['state'] = task_results[edge['upstream_task']]
                    upstream_edges.append(edge)

                task_results[task.name] = executor.run_task(
                    task_runner=task_runner,
                    upstream_edges=upstream_edges,
                    context=context)

            task_results = executor.gather_task_results(task_results)

        try:
            terminal_results = {
                t.name: task_results[t.name]
                for t in self.flow.terminal_tasks()
            }
            if any(r.is_waiting() for r in task_results.values()):
                state.wait(result=task_results)
            elif any(r.is_failed() for r in terminal_results.values()):
                state.fail(result=task_results)
            elif all(r.is_successful() for r in terminal_results.values()):
                state.succeed(result=task_results)
        except Exception as e:
            state.fail()

        return state
