import logging
import os
import pendulum
import time

from prefect import config
from prefect.client import Client
from prefect.serialization import state
from prefect.engine.state import Submitted
from prefect.utilities.graphql import with_args


class Agent:
    """
    Base class for Agents.

    This Agent class is a standard point for executing Flows in Prefect Cloud. It is meant
    to have subclasses which inherit functionality from this class. The only piece that
    the subclasses should implement is the `deploy_flows` function, which specifies how to run a Flow on the given platform. It is built in this
    way to keep Prefect Cloud logic standard but allows for platform specific
    customizability.

    In order for this to operate `PREFECT__CLOUD__AGENT__AUTH_TOKEN` must be set as an
    environment variable or in your user configuration file.
    """

    def __init__(self) -> None:
        #  self.auth_token = config.cloud.agent.get("auth_token")
        self.loop_interval = config.cloud.agent.get("loop_interval")

        self.client = Client(token=config.cloud.agent.get("auth_token"))

        logger = logging.getLogger("agent")
        logger.setLevel(logging.DEBUG)
        ch = logging.StreamHandler()
        ch.setLevel(logging.DEBUG)
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        ch.setFormatter(formatter)
        logger.addHandler(ch)

        self.logger = logger

    def start(self) -> None:
        """
        The main entrypoint to the agent. This function loops and constantly polls for
        new flow runs to deploy
        """
        self.logger.info("Starting {}".format(type(self).__name__))
        tenant_id = self.query_tenant_id()

        while True:
            try:
                flow_runs = self.query_flow_runs(tenant_id=tenant_id)
                self.logger.info(
                    "Found {} flow run(s) to submit for execution.".format(
                        len(flow_runs)
                    )
                )

                self.update_states(flow_runs)
                self.deploy_flows(flow_runs)
                self.logger.info(
                    "Submitted {} flow run(s) for execution.".format(len(flow_runs))
                )
            except Exception as exc:
                self.logger.error(exc)
            time.sleep(self.loop_interval)

    def query_tenant_id(self) -> str:
        """
        Query Prefect Cloud for the tenant id that corresponds to the agent's auth token

        Returns:
            - str: The current tenant id
        """
        query = {"query": {"tenant": {"id"}}}
        result = self.client.graphql(query)
        return result.data.tenant[0].id  # type: ignore

    def query_flow_runs(self, tenant_id: str) -> list:
        """
        Query Prefect Cloud for flow runs which need to be deployed and executed

        Args:
            - tenant_id (str): The tenant id to use in the query

        Returns:
            - list: A list of GraphQLResult flow run objects
        """

        # Get scheduled flow runs from queue
        mutation = {
            "mutation($input: getRunsInQueueInput!)": {
                "getRunsInQueue(input: $input)": {"flow_run_ids"}
            }
        }

        result = self.client.graphql(
            mutation, variables={"input": {"tenantId": tenant_id}}
        )
        flow_run_ids = result.data.getRunsInQueue.flow_run_ids  # type: ignore
        now = pendulum.now("UTC")

        # Query metadata fow flow runs found in queue
        query = {
            "query": {
                with_args(
                    "flow_run",
                    {
                        # match flow runs in the flow_run_ids list
                        "where": {
                            "id": {"_in": flow_run_ids},
                            "_or": [
                                # who are EITHER scheduled...
                                {"state": {"_eq": "Scheduled"}},
                                # OR running with task runs scheduled to start more than 3 seconds ago
                                {
                                    "state": {"_eq": "Running"},
                                    "task_runs": {
                                        "state_start_time": {
                                            "_lte": str(now.subtract(seconds=3))
                                        }
                                    },
                                },
                            ],
                        }
                    },
                ): {
                    "id": True,
                    "version": True,
                    "tenant_id": True,
                    "state": True,
                    "serialized_state": True,
                    "parameters": True,
                    "flow": {"id", "name", "environment", "storage"},
                    with_args(
                        "task_runs",
                        {
                            "where": {
                                "state_start_time": {
                                    "_lte": str(now.subtract(seconds=3))
                                }
                            }
                        },
                    ): {"id", "version", "task_id", "serialized_state"},
                }
            }
        }

        result = self.client.graphql(query)
        return result.data.flow_run  # type: ignore

    def update_states(self, flow_runs: list) -> None:
        """
        After a flow run is grabbed this function sets the state to Submitted so it
        won't be picked up by any other processes

        Args:
            - flow_runs (list): A list of GraphQLResult flow run objects
        """
        for flow_run in flow_runs:

            # Set flow run state to `Submitted` if it is currently `Scheduled`
            if state.StateSchema().load(flow_run.serialized_state).is_scheduled():
                self.client.set_flow_run_state(
                    flow_run_id=flow_run.id,
                    version=flow_run.version,
                    state=Submitted(
                        message="Submitted for execution",
                        state=state.StateSchema().load(flow_run.serialized_state),
                    ),
                )

            # Set task run states to `Submitted` if they are currently `Scheduled`
            for task_run in flow_run.task_runs:
                if state.StateSchema().load(task_run.serialized_state).is_scheduled():
                    self.client.set_task_run_state(
                        task_run_id=task_run.id,
                        version=task_run.version,
                        state=Submitted(
                            message="Submitted for execution",
                            state=state.StateSchema().load(task_run.serialized_state),
                        ),
                    )

    def deploy_flows(self, flow_runs: list) -> None:
        """
        Meant to be overridden by a platform specific deployment option

        Args:
            - flow_runs (list): A list of GraphQLResult flow run objects
        """
        pass


if __name__ == "__main__":
    Agent().start()
