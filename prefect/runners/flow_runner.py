import datetime
import prefect
from prefect.runners.task_runner import TaskRunner
from prefect.state import TaskRunState, FlowRunState
from prefect.runners.results import RunResult
import uuid


def _deserialize_result(task, result, index):
    """
    Given a task and corresponding state, returns the state's
    deserialized result. If the state is anything but successful,
    None is returned.
    """
    deserialized_result = task.serializer.decode(result.result)
    except Exception as e:
        raise prefect.signals.FAIL(
            f'Could not deserialize result of {task}: {e}')


class FlowRunner:
    """
    The FlowRunner class takes a Flow and executes a FlowRun with a specific
    id.

    The FlowRunner is responsible for creating TaskRunners for each task in
    the flow and waits for them to complete. It returns the flow's state.
    """

    def __init__(self, flowrun_id, token):

        for req in flow.required_params:
            if req not in params:
                raise ValueError(
                    'A required parameter was not provided: {}'.format(req))

        self.flow = flow
        self.token = token
        self.id = id
        self.params = params

        if executor is None:
            executor = prefect.runners.executors.default_executor()
        self.executor = executor

    def load_flowrun(self):
        prefect_client = prefect.client.Client(token=self.token)

        if self.id:
            flowrun_info = prefect_client.flowruns.get(self.id)
            flowrun_info['task_results'] = {
                t['task_name']: RunResult(state=t['state'], result=t['result'])
                for t in flowrun_info['taskruns']
            }
        else:
            id = prefect_client.flowruns.create(
                flow_id=self.i
            )
            flowrun_info = {
                'state': FlowRunState(),
                'task_results': {},
                'flow_id': None,
            }
        return flowrun_info

    def run(
            self,
            token=None,
            start_tasks=None,
            context=None,
            task_results=None,
            state=None):

        info = self.flowrun_info()
        state = state or info['state']
        task_results = task_results or info['task_results']

        prefect_context = {
            'dt': None,  #TODO
            'as_of_dt': None,  # TODO
            'last_dt': None,  # TODO
            'flow_namespace': self.flow.namespace,
            'flow_name': self.flow.name,
            'flow_id': info['flow_id'],
            'flow_version': self.flow.version,
            'flowrun_id': self.id,
            'params': params,
            'token': self.token,
        }

        if context is not None:
            prefect_context.update(context)

        # deserialized holds futures representing deserialized task results
        # (to avoid deserializing the same result multiple times)
        deserialized = {}

        try:

            with prefect.utilities.cluster.client() as client:

                #     executor = self.executor(cluster_client=cluster_client)
                #
                # with self.executor(cluster_client) as client:

                for task in self.flow.sorted_tasks(root_tasks=start_tasks):

                    upstream_results = {}
                    upstream_inputs = {}

                    # collect upstream results
                    for t in self.flow.upstream_tasks(task):
                        if t.name not in task_results:
                            raise ValueError(
                                f'The result of task {t.name} was not found!')
                        upstream_results[t.name] = task_results[t.name]

                    # check incoming edges to see if we need to deserialize
                    # any upstream inputs
                    for e in self.flow.edges_to(task):

                        # if the edge has no key, it's not an input
                        if e.key is None:
                            continue

                        # deserialize the task result
                        # rely on Dask for caching
                        upstream_task = self.flow.get_task(e.upstream_task)
                        upstream_inputs[e.key] = client.submit(
                            upstream_task.serializer.decode,
                            upstream_results[e.upstream_task].result,
                            pure=True)

                        # index the deserialized result if necessary
                        # rely on Dask for caching
                        if e.upstream_index is not None:
                            upstream_inputs[e.key] = client.submit(
                                lambda result, index: result[index]
                                result=upstream_inputs[e.key]
                                index=e.upstream_index
                                pure=True)

                    # run the task -- this returns a RunResult(state, result)
                    task_runner = prefect.runners.TaskRunner(
                        task=task,
                        taskrun_id=flowrun_info.get('taskrun_id')

                    )
                    task_results[task.name] = client.run_task(
                        task=task,
                        flowrun_id=self.id,
                        upstream_results=upstream_results,
                        inputs=upstream_inputs)

                # gather all task results from the cluster
                task_results = client.gather(task_results)

            terminal_results = {
                t.name: task_results[t.name]
                for t in self.flow.terminal_tasks()
            }

            if any(s.state.is_waiting() for s in task_results.values()):
                state.wait()
            elif any(s.state.is_failed() for s in terminal_results.values()):
                state.fail()
            elif all(s.state.is_successful() for s in terminal_results.values()):
                state.succeed()

        except Exception as e:
            state.fail()

        return RunResult(state=state, result=task_results)
