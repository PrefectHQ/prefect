import logging
from typing import Union

import pendulum
import time

from prefect import config
from prefect.client import Client
from prefect.serialization import state
from prefect.engine.state import Submitted
from prefect.utilities.graphql import with_args


ascii_name = r"""
 ____            __           _        _                    _
|  _ \ _ __ ___ / _| ___  ___| |_     / \   __ _  ___ _ __ | |_
| |_) | '__/ _ \ |_ / _ \/ __| __|   / _ \ / _` |/ _ \ '_ \| __|
|  __/| | |  __/  _|  __/ (__| |_   / ___ \ (_| |  __/ | | | |_
|_|   |_|  \___|_|  \___|\___|\__| /_/   \_\__, |\___|_| |_|\__|
                                           |___/
"""


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
        self.client = Client(api_token=config.cloud.agent.get("auth_token"))

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
        tenant_id = self.agent_connect()

        # Loop intervals for query sleep backoff
        loop_intervals = {0: 0.25, 1: 0.5, 2: 1.0, 3: 2.0, 4: 4.0, 5: 8.0, 6: 10.0}

        index = 0
        while True:
            runs = self.agent_process(tenant_id)
            if runs:
                index = 0
            elif index < max(loop_intervals.keys()):
                index += 1
            time.sleep(loop_intervals[index])

    def agent_connect(self) -> str:
        """
        Verify agent connection to Prefect Cloud by finding and returning a tenant id

        Returns:
            - str: The current tenant id
        """
        print(ascii_name)
        self.logger.info("Starting {}".format(type(self).__name__))
        self.logger.info(
            "Agent documentation can be found at https://docs.prefect.io/cloud/"
        )
        tenant_id = self.query_tenant_id()

        if not tenant_id:
            raise ConnectionError(
                "Tenant ID not found. Verify that you are using the proper API token."
            )

        self.logger.info("Agent successfully connected to Prefect Cloud")
        self.logger.info("Waiting for flow runs...")

        return tenant_id

    def agent_process(self, tenant_id: str) -> bool:
        """
        Full process for finding flow runs, updating states, and deploying.

        Args:
            - tenant_id (str): The tenant id to use in the query

        Returns:
            - bool: whether or not flow runs were found
        """
        flow_runs = None
        try:
            flow_runs = self.query_flow_runs(tenant_id=tenant_id)

            if flow_runs:
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

        return bool(flow_runs)

    def query_tenant_id(self) -> Union[str, None]:
        """
        Query Prefect Cloud for the tenant id that corresponds to the agent's auth token

        Returns:
            - Union[str, None]: The current tenant id if found, None otherwise
        """
        query = {"query": {"tenant": {"id"}}}
        result = self.client.graphql(query)

        if result.data.tenant:  # type: ignore
            return result.data.tenant[0].id  # type: ignore

        return None

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
