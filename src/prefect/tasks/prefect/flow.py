import time
from typing import Union, Optional

from prefect import Task, Flow, task, Client
from prefect.utilities.graphql import with_args, EnumValue
from prefect.api import FlowRun
from prefect.engine.signals import FAIL

FlowLike = Union["Flow", str]
TaskLike = Union["Task", str]


class RunFlow(Task):
    POLL_TIME = 5

    def __init__(
        self,
        flow_obj: "Flow" = None,
        flow_id: str = None,
        flow_name: str = None,
        project_name: str = None,
        run_inline: bool = True,
        wait: bool = True,
        **kwargs,
    ):
        self.flow_obj_default = flow_obj
        self.flow_id_default = flow_id
        self.flow_name_default = flow_name
        self.project_name_default = project_name
        self.run_inline_default = run_inline
        self.wait_default = wait

        # Will store a `FlowRun` tracking the flow run
        self._flow_run: Optional[FlowRun] = None

        super().__init__(**kwargs)

    def run(
        self,
        flow_obj: "Flow" = None,
        flow_id: str = None,
        flow_name: str = None,
        project_name: str = None,
        run_inline: bool = None,
        wait: bool = True,
    ) -> "FlowRun":
        flow = flow_obj or self.flow_obj_default
        flow_id = flow_id or self.flow_id_default
        flow_name = flow_name or self.flow_name_default
        project_name = project_name or self.project_name_default
        run_inline = run_inline if run_inline is not None else self.run_inline_default
        wait = wait if wait is not None else self.wait_default

        if flow and (flow_id or flow_name):
            raise ValueError(
                "`flow_obj` cannot be provided with `flow_id` or `flow_name`; "
                "these values will be inferred from the `flow_obj` and collide."
            )

        if run_inline and not flow:
            # In the future, we could consider pulling the flow object from cloud
            # and deserializing it to attempt the run
            raise ValueError("`flow_obj` must be set if using `run_inline`")
        elif run_inline and flow:
            # We can run inline just using the flow object
            self._run_inline(flow, project_name)
            return self._flow_run

        # Otherwise, we'll need to lookup the flow to run

        # Pull any information from the flow object
        if flow:
            flow_id = flow.flow_id
            flow_name = flow.name

        flow_id = self._lookup_flow(
            flow_id=flow_id, flow_name=flow_name, project_name=project_name
        )

        self._run_with_agent(flow_id=flow_id, wait=wait)
        return self._flow_run

    def _run_inline(self, flow: "Flow", project_name: str = None):
        self.logger.debug(
            "Running flow in-process... Set `run_inline=False` to run the flow using "
            "an agent instead."
        )
        self._flow_run = flow.cloud_run(project_name=project_name)

    def _run_with_agent(self, flow_id: str, wait: bool):
        self.logger.debug(
            "Running flow with an agent... Set `run_inline=True` to run the flow "
            "inline instead."
        )

        client = Client()
        flow_run_id = client.create_flow_run(
            flow_id=flow_id,
        )

        self._flow_run = FlowRun.from_flow_run_id(flow_run_id=flow_run_id)

        if not wait:
            self.logger.debug(
                "Returning without waiting for flow to finish. Set `wait=True` to "
                "hang downstream tasks until this flow has reached a terminal state."
            )

        self.logger.debug(
            "Waiting for flow run to finish... Set `wait=False` to return immediately "
            "after flow run creation."
        )

        last_state = self._flow_run.state
        total_wait_time = 0
        warning_wait_time = 0
        while True:
            time.sleep(self.POLL_TIME)
            warning_wait_time += self.POLL_TIME
            total_wait_time += warning_wait_time

            self._flow_run = FlowRun.from_flow_run_id(flow_run_id=flow_run_id)

            if (
                total_wait_time > 20
                and warning_wait_time > 20
                and not self._flow_run.state.is_running()
            ):
                self.logger.warning(
                    f"It has been {total_wait_time} seconds and your flow run "
                    f"is not started. Do you have an agent running?"
                )
                warning_wait_time = 0

            if self._flow_run.state != last_state:
                self.logger.info(f"Flow run entered new state: {self._flow_run.state}")
                last_state = self._flow_run.state

            if self._flow_run.state.is_finished():
                break

    @staticmethod
    def _lookup_flow(
        flow_id: str = None, flow_name: str = None, project_name: str = None
    ) -> str:
        # Construct a where clause
        where = {"archived": {"_eq": False}}
        if flow_id:
            where["id"] = {"_eq": flow_id}
        if flow_name:
            where["name"] = {"_eq": flow_name}
        if project_name:
            where["project"] = {"name": {"_eq": project_name}}

        # Get the flow id, this will also verify flow name / project name / flow id
        # are compatible since it will return nothing if there's a mismatch
        query = {
            "query": {
                with_args(
                    "flow",
                    {
                        "where": where,
                        "order_by": {"version": EnumValue("desc")},
                        "limit": 1,
                    },
                ): {"id"}
            }
        }

        client = Client()
        result = client.graphql(query).get("data", {}).get("flow", None)
        if result is None:
            raise ValueError(
                f"Received bad result while querying for task runs where {where}: "
                f"{result}"
            )

        if not result:
            raise ValueError(f"Found no flows with query where {where}")

        flow_id = result[0].id
        return flow_id

    def get_result(
        self, task_obj: "Task" = None, task_slug: str = None, task_run_id: str = None
    ):
        # Generate a 'from_task' obj for display and query
        from_task = {}
        if task_obj:
            from_task["task"] = task_obj
        if task_slug:
            from_task["task_slug"] = task_slug
        if task_run_id:
            from_task["task_run_id"] = task_run_id

        # Create a Task to return that will query for the task result from the flow run
        @task
        def get_result_task():
            while not self._flow_run:
                self.logger.debug("Waiting for flow result to be populated...")
                time.sleep(self.POLL_TIME)

            task_run = self._flow_run.get(**from_task)
            while not task_run.state.is_finished():
                if self._flow_run.state.is_failed():
                    self.logger.error(
                        f"Flow run failed with {self._flow_run.state}, "
                        f"before task {from_task} finished, cannot retrieve task "
                        f"result."
                    )
                    raise FAIL(
                        "Flow run failed before task finished, cannot retrieve task "
                        "result."
                    )

                self.logger.debug(
                    f"Waiting for task {from_task} to enter finished state..."
                )
                time.sleep(self.POLL_TIME)
                task_run = self._flow_run.get(**from_task)

            return task_run.result

        return get_result_task()


run_flow = RunFlow()
