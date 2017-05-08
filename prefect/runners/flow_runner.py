import datetime
import prefect
from prefect.runners.task_runner import TaskRunner
import uuid


def _deserialize_result(task, state):
    """
    Given a task and corresponding state, returns the state's
    deserialized result. If the state is anything but successful,
    None is returned.
    """
    try:
        if not state.is_successful():
            return None
        else:
            result = state.value['value']
            if state.value['serialized'] is True:
                result = task.serializer.decode(result)
            return result
    except Exception as e:
        raise signals.FAIL(
            'Could not deserialize result of {}: {}'.format(task, e))


def _maybe_index_result(edge, result):
    """
    Given an edge and corresponding task result, attempts to properly
    index the result.
    """
    try:
        if edge.upstream_index is not None:
            return result[edge.upstream_index]
        else:
            return result
    except Exception as e:
        raise signals.FAIL(
            'Could not index result of {}: {}'.format(edge.upstream_task, e))


class FlowRunner:
    """
    The FlowRunner class takes a Flow and executes a FlowRun with a specific
    id.

    The FlowRunner is responsible for creating TaskRunners for each task in
    the flow and waits for them to complete. It returns the flow's state.
    """

    def __init__(self, flow, run_id=None, executor=None):

        self.flow = flow
        if run_id is None:
            run_id = uuid.uuid4().hex
        self.run_id = run_id

        if executor is None:
            executor = getattr(
                prefect.runners.executors,
                prefect.config.get('prefect', 'default_executor'))()
        self.executor = executor

    # def run(self, state=None, block=False, **params):
    #     with self.executor() as executor:
    #         future = executor.submit(self._run, state=state, **params)
    #         if block:
    #             return executor.gather(future)
    #         else:
    #             return executor.ensure(future)

    def run(self, state=None, context=None, **params):

        if state is None:
            state = prefect.state.FlowRunState()

        for req in self.flow.required_params:
            if req not in params:
                raise ValueError(
                    'A required parameter was not provided: {}'.format(req))

        prefect_context = {
            'dt': None,  #TODO
            'as_of_dt': None,  # TODO
            'last_dt': None,  # TODO
            'flow': self.flow,
            'flow_id': self.flow.id,
            'flow_namespace': self.flow.namespace,
            'flow_name': self.flow.name,
            'flow_version': self.flow.version,
            'run_id': self.run_id,
            'params': params,
        }
        if context is not None:
            prefect_context.update(context)

        task_states = {}
        task_results = {}

        try:
            with self.executor(**prefect_context) as client:
                for task in self.flow.sorted_tasks():

                    upstream_states = {}
                    upstream_inputs = {}

                    # collect the states of tasks immediately upstream from
                    # this task
                    for u_task in self.flow.upstream_tasks(task):
                        upstream_states[u_task.name] = task_states[u_task.name]

                    # collect the results of tasks immediately upstream from
                    # this task, if required
                    for e in self.flow.edges_to(task):

                        if e.key is None:
                            continue

                        # check if the task result has already been deserialized
                        # (we only want to do this once)
                        if e.upstream_task.name not in task_results:
                            task_results[e.upstream_task.name] = client.submit(
                                _deserialize_result,
                                task=e.upstream_task,
                                state=task_states[e.upstream_task.name],
                                pure=False)

                        # get the (indexed) task result and store it under the
                        # appropriate input key
                        upstream_inputs[e.key] = client.submit(
                            _maybe_index_result,
                            edge=e,
                            result=task_results[e.upstream_task.name],
                            pure=False)

                    # run the task
                    task_states[task.name] = client.run_task(
                        task=task,
                        run_id=self.run_id,
                        upstream_states=upstream_states,
                        inputs=upstream_inputs)

                task_states = client.gather(task_states)

            terminal_results = {
                t.name: task_states[t.name]
                for t in self.flow.terminal_tasks()
            }
            if any(r.is_waiting() for r in task_states.values()):
                state.wait(value=task_states)
            elif any(r.is_failed() for r in terminal_results.values()):
                state.fail(value=task_states)
            elif all(r.is_successful() for r in terminal_results.values()):
                state.succeed(value=task_states)
        except Exception as e:
            state.fail(value='{}'.format(e))
            raise

        return state
