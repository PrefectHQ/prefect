from contextlib import contextmanager
import datetime
import prefect
from prefect.runners.task_runner import TaskRunner
from prefect.state import TaskRunState, FlowRunState
from prefect.runners.results import RunResult
import uuid


class FlowRunner:

    def __init__(self, flow, executor, run_key=None):

        self.flow = flow
        self.executor = executor
        if run_key is None:
            run_key = uuid.uuid4().hex
        self.run_key = run_key

    @contextmanager
    def catch_signals(self, state):
        try:
            yield

        except signals.SUCCESS as s:
            self.logger.info(f'{type(s).__name__}: {s}')
            state.succeed()
        except signals.SKIP as s:
            self.logger.info(f'{type(s).__name__}: {s}')
            state.skip()
        except signals.SHUTDOWN as s:
            self.logger.info(f'{type(s).__name__}: {s}')
            state.shutdown()
        except signals.DONTRUN as s:
            self.logger.info(f'{type(s).__name__}: {s}')
        except (signals.FAIL, Exception) as s:
            self.logger.info(f'{type(s).__name__}: {s}')
            state.fail()

    def run(
            self,
            state=None,
            task_states=None,
            task_results=None,
            start_tasks=None,
            context=None):
        state = prefect.state.FlowRunState(state)

        with prefect.context(**context or {}):
            with self.catch_signals(state):
                self.check_state(state)
                result = self.run_flow(
                    task_states=task_states,
                    task_results=task_results,
                    start_tasks=start_tasks)
                result = self.process_result(result)
        return dict(state=state, result=result)


    def check_state(self, state):

        # -------------------------------------------------------------
        # check this flow
        # -------------------------------------------------------------

        # this task is already finished
        if state.is_finished():
            raise signals.DONTRUN('FlowRun is already finished.')

        # this task is not pending or already running
        # Note: we allow multiple flowruns at the same time (state = RUNNING)
        elif not (state.is_pending() or state.is_running()):
            raise signals.DONTRUN(
                f'FlowRun is not ready to run (state {state}).')

        # -------------------------------------------------------------
        # start!
        # -------------------------------------------------------------

        state.start()

        return state

    def run_flow(
            self,
            task_states=None,
            task_results=None,
            start_tasks=None,
            context=None):
        """
        Arguments

            task_states (dict): a dictionary of { task.name: TaskState } pairs
                representing the initial states of the FlowRun.

            task_results (dict): a dictionary of { task.name: result } pairs
                representing the initial results of the FlowRun.
        """

        task_states = task_states or {}
        task_results = task_results or {}
        deserialized = {}

        with prefect.context(**context or {}):

            with distributed.worker_client() as client:

                for task in self.flow.sorted_tasks(start_tasks=start_tasks):

                    upstream_states = {}
                    upstream_results = {}

                    # iterate over all upstream edges
                    for edge in self.flow.edges_to(task):

                        u_task = edge.upstream_task
                        if u_task not in task_states:
                            raise ValueError(
                                f'State for task "{u_task}" not found')

                        # collect the upstream task's state
                        upstream_states[u_task] = task_states[u_task]

                        # if the edge has no key, then we're done
                        if edge.key is None:
                            continue

                        # deserialize the upstream result (if not cached)
                        if u_task not in deserialized:
                            deserialized[u_task] = client.submit(
                                self.executor.deserialize_result,
                                task=u_task,
                                result=task_results.get(u_task, None),
                                pure=False)
                        upstream_results[edge.key] = deserialized[u_task]

                        # index the deserialized result, if necessary
                        if edge.upstream_index is not None:
                            upstream_results[edge.key] = client.submit(
                                lambda result: result[edge.upstream_index],
                                result=upstream_results[edge.key],
                                pure=False)

                    # run the task
                    task_future = client.submit(
                        self.executor.run_task,
                        task=task,
                        state=task_states.get(task),
                        upstream_states=upstream_states,
                        inputs=upstream_results,
                        context=context,
                        pure=False)

                    # store the task's state
                    task_states[task] = client.submit(
                        lambda task_future: task_future['state'],
                        task_future=task_future,
                        pure=False)

                    # store the task's result
                    task_results[task] = client.submit(
                        lambda task_future: task_future['result'],
                        task_future=task_future,
                        pure=False)

        task_states = client.gather(task_states)
        task_results = client.gather(task_results)

        return dict(states=task_states, results=task_results)


    def process_result(self, result):

        terminal_states, terminal_results = {}, {}
        for t in self.flow.terminal_tasks():
            terminal_states[t.name] = result['states'][t.name]
            terminal_results[t.name] = result['results'][t.name]

        if any(s.is_failed() for s in terminal_states.values()):
            raise signals.FAIL('Terminal tasks failed')
        elif all(s.state.is_successful() for s in terminal_states.values()):
            raise signals.SUCCESS('Terminal tasks were all successful')

        return dict(states=terminal_states, results=terminal_results)



# ============================================================================
# ============================================================================
# ============================================================================
# ============================================================================
# ============================================================================
# ============================================================================
# ============================================================================
# ============================================================================
# ============================================================================
# ============================================================================
# ============================================================================
# ============================================================================
# ============================================================================
# ============================================================================
# ============================================================================
# ============================================================================
# ============================================================================
# def deserialize_result(token, task_id, task_result):
#     client = prefect.Client(token=token)
#     serialized_task = client.tasks.get(task_id, serialized=True)['serialized']
#     task = prefect.Task.deserialize(serialized_task)
#     return task.serializer.decode(task_result['result'])
#
#
# class FlowRunner:
#
#     def __init__(self, flowrun_id, token):
#         self.flowrun_id = flowrun_id
#         self.token = token
#
#     def run(self, start_tasks=None):
#         prefect_client = prefect.Client(token=self.token)
#         flowrun_info = prefect_client.flowruns.get(self.flowrun_id)
#
#         taskrun_info = prefect_client.flowruns.get_taskruns(
#             flowrun_id=self.flowrun_id,
#             per_page=None)
#         taskrun_info = {tr['task_name']: tr for tr in taskrun_info}
#
#         flow_info = prefect_client.flows.get(
#             flowrun_info['flow_id'], serialized=True)
#         flow = prefect.Flow.safe_deserialize(flow_info['serialized'])
#
#         prefect_context = {
#             'dt': None,  #TODO
#             'as_of_dt': None,  # TODO
#             'last_dt': None,  # TODO
#             'flow_namespace': flow.namespace,
#             'flow_name': flow.name,
#             'flow_id': flowrun_info['flow_id'],
#             'flow_version': flow.version,
#             'flowrun_id': self.flowrun_id,
#             'parameters': flowrun_info['parameters'],
#             'token': self.token,
#         }
#
#         task_results = {
#             tr['name']: {
#                 'state': tr['state'], 'result': tr['result']
#                 }
#             for tr in taskrun_info.values()
#         }
#
#         with distributed.worker_client() as dask_client:
#
#             for task in flow.sorted_tasks(root_tasks=start_tasks):
#
#                     upstream_results = {}
#                     upstream_inputs = {}
#
#                     # collect upstream results
#                     for t in flow.upstream_tasks(task):
#                         upstream_results[t.name] = task_results[t.name]
#
#                     # check incoming edges to see if we need to deserialize
#                     # any upstream inputs
#                     for e in flow.edges_to(task):
#
#                         # if the edge has no key, it's not an input
#                         if e.key is None:
#                             continue
#
#                         # deserialize the task result
#                         # rely on Dask for caching
#                         upstream_task = flow.get_task(e.upstream_task)
#                         upstream_inputs[e.key] = dask_client.submit(
#                             deserialize_result,
#                             task_id=taskrun_info[e.upstream_task]['task_id'],
#                             task_result=upstream_results[e.upstream_task],
#                             pure=True)
#
#                         # index the deserialized result if necessary
#                         # rely on Dask for caching
#                         if e.upstream_index is not None:
#                             upstream_inputs[e.key] = dask_client.submit(
#                                 lambda result, index: result[index],
#                                 result=upstream_inputs[e.key],
#                                 index=e.upstream_index,
#                                 pure=True)
#
#                     # run the task -- this returns a RunResult(state, result)
#                     task_runner = prefect.runners.TaskRunner(
#                         taskrun_id=taskrun_info[task.name]['id'],
#                         token=self.token)
#
#                     task_results[task.name] = dask_client.submit(
#                         task_runner.run,
#                         upstream_states=upstream_states,
#                         inputs=upstream_inputs)
#
#                 # gather all task results from the cluster
#                 task_results = dask_client.gather(task_results)
#
#             terminal_results = {
#                 t.name: task_results[t.name]
#                 for t in flow.terminal_tasks()
#             }
#
#             if any(s.state.is_waiting() for s in task_results.values()):
#                 state.wait()
#             elif any(s.state.is_failed() for s in terminal_results.values()):
#                 state.fail()
#             elif all(s.state.is_successful() for s in terminal_results.values()):
#                 state.succeed()
#
#         except Exception as e:
#             state.fail()
#
#         return RunResult(state=state, result=task_results)
#
#
#
#
#
#
#
#
#
#
#
#
#
# def _deserialize_result(task, result, index):
#     """
#     Given a task and corresponding state, returns the state's
#     deserialized result. If the state is anything but successful,
#     None is returned.
#     """
#     try:
#         deserialized_result = task.serializer.decode(result.result)
#     except Exception as e:
#         raise prefect.signals.FAIL(
#             f'Could not deserialize result of {task}: {e}')
#
#
# class FlowRunner:
#     """
#     The FlowRunner class takes a Flow and executes a FlowRun with a specific
#     id.
#
#     The FlowRunner is responsible for creating TaskRunners for each task in
#     the flow and waits for them to complete. It returns the flow's state.
#     """
#
#     def __init__(self, flowrun_id, token):
#
#         for req in flow.required_parameters:
#             if req not in params:
#                 raise ValueError(
#                     'A required parameter was not provided: {}'.format(req))
#
#         self.flow = flow
#         self.token = token
#         self.id = id
#         self.params = params
#
#         if executor is None:
#             executor = prefect.runners.executors.default_executor()
#         self.executor = executor
#
#     def load_flowrun(self):
#         prefect_client = prefect.client.Client(token=self.token)
#
#         if self.id:
#             flowrun_info = prefect_client.flowruns.get(self.id)
#             flowrun_info['task_results'] = {
#                 t['task_name']: RunResult(state=t['state'], result=t['result'])
#                 for t in flowrun_info['taskruns']
#             }
#         else:
#             id = prefect_client.flowruns.create(
#                 flow_id=self.i
#             )
#             flowrun_info = {
#                 'state': FlowRunState(),
#                 'task_results': {},
#                 'flow_id': None,
#             }
#         return flowrun_info
#
#     def run(
#             self,
#             token=None,
#             start_tasks=None,
#             context=None,
#             ignore_upstream_dependencies=False):
#         """
#
#         Args
#             start_tasks (seq of task names): a sequence of tasks that will be
#                 the root tasks of the flow. Only these tasks and their
#                 downstream dependencies will be run. This can be used, for
#                 example, to resume a FlowRun from a task that should be retried.
#         """
#
#         info = self.flowrun_info()
#         state = state or info['state']
#         task_results = task_results or info['task_results']
#
#         prefect_context = {
#             'dt': None,  #TODO
#             'as_of_dt': None,  # TODO
#             'last_dt': None,  # TODO
#             'flow_namespace': self.flow.namespace,
#             'flow_name': self.flow.name,
#             'flow_id': info['flow_id'],
#             'flow_version': self.flow.version,
#             'flowrun_id': self.id,
#             'params': params,
#             'token': self.token,
#         }
#
#         if context is not None:
#             prefect_context.update(context)
#
#         # deserialized holds futures representing deserialized task results
#         # (to avoid deserializing the same result multiple times)
#         deserialized = {}
#
#         try:
#
#             with prefect.utilities.cluster.client() as client:
#
#                 #     executor = self.executor(cluster_client=cluster_client)
#                 #
#                 # with self.executor(cluster_client) as client:
#
#                 for task in self.flow.sorted_tasks(root_tasks=start_tasks):
#
#                     upstream_results = {}
#                     upstream_inputs = {}
#
#                     # collect upstream results
#                     for t in self.flow.upstream_tasks(task):
#                         if t.name not in task_results:
#                             raise ValueError(
#                                 f'The result of task {t.name} was not found!')
#                         upstream_results[t.name] = task_results[t.name]
#
#                     # check incoming edges to see if we need to deserialize
#                     # any upstream inputs
#                     for e in self.flow.edges_to(task):
#
#                         # if the edge has no key, it's not an input
#                         if e.key is None:
#                             continue
#
#                         # deserialize the task result
#                         # rely on Dask for caching
#                         upstream_task = self.flow.get_task(e.upstream_task)
#                         upstream_inputs[e.key] = client.submit(
#                             upstream_task.serializer.decode,
#                             upstream_results[e.upstream_task].result,
#                             pure=True)
#
#                         # index the deserialized result if necessary
#                         # rely on Dask for caching
#                         if e.upstream_index is not None:
#                             upstream_inputs[e.key] = client.submit(
#                                 lambda result, index: result[index],
#                                 result=upstream_inputs[e.key],
#                                 index=e.upstream_index,
#                                 pure=True)
#
#                     # run the task -- this returns a RunResult(state, result)
#                     task_runner = prefect.runners.TaskRunner(
#                         task=task,
#                         taskrun_id=flowrun_info.get('taskrun_id')
#
#                     )
#                     task_results[task.name] = client.run_task(
#                         task=task,
#                         flowrun_id=self.id,
#                         upstream_results=upstream_results,
#                         inputs=upstream_inputs)
#
#                 # gather all task results from the cluster
#                 task_results = client.gather(task_results)
#
#             terminal_results = {
#                 t.name: task_results[t.name]
#                 for t in self.flow.terminal_tasks()
#             }
#
#             if any(s.state.is_waiting() for s in task_results.values()):
#                 state.wait()
#             elif any(s.state.is_failed() for s in terminal_results.values()):
#                 state.fail()
#             elif all(s.state.is_successful() for s in terminal_results.values()):
#                 state.succeed()
#
#         except Exception as e:
#             state.fail()
#
#         return RunResult(state=state, result=task_results)
