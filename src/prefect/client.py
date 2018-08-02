import datetime
import os

import prefect
from prefect.utilities.collections import to_dotdict


__all__ = ["Client", "TaskRuns", "FlowRuns"]


class AuthorizationError(Exception):
    pass


class Client:
    """
    Client for the Prefect API.
    """

    def __init__(self, api_server=None, graphql_server=None, token=None):
        if api_server is None:
            api_server = prefect.config.get("prefect", "api_server")
            if not api_server:
                api_server = prefect.context.Context.get("api_server", None)
                if not api_server:
                    raise ValueError("Could not determine API server.")
        self._api_server = api_server

        if graphql_server is None:
            graphql_server = prefect.config.get("prefect", "graphql_server")
            if not graphql_server:
                graphql_server = prefect.context.Context.get("graphql_server", None)
                if not graphql_server:
                    graphql_server = api_server
        self._graphql_server = graphql_server

        if token is None:
            token = prefect.context.Context.get("token", None)
        self._token = token

        self.projects = Projects(client=self)
        self.flows = Flows(client=self)
        self.flow_runs = FlowRuns(client=self)
        self.task_runs = TaskRuns(client=self)

    # -------------------------------------------------------------------------
    # Utilities

    def _get(self, path, *, _json=True, _server=None, **params):
        """
        Convenience function for calling the Prefect API with token auth.

        Args:
            path: the path of the API url. For example, to GET
                http://prefect-server/v1/auth/login, path would be 'auth/login'.
            params: GET parameters
        """
        response = self._request(method="GET", path=path, params=params, server=_server)
        if _json:
            if response.text:
                response = response.json()
            else:
                response = {}
        return response

    def _post(self, path, *, _json=True, _server=None, **params):
        """
        Convenience function for calling the Prefect API with token auth.

        Args:
            path: the path of the API url. For example, to POST
                http://prefect-server/v1/auth/login, path would be 'auth/login'.
            params: POST params
        """
        response = self._request(
            method="POST", path=path, params=params, server=_server
        )
        if _json:
            if response.text:
                return response.json()
        else:
            return response

    def _delete(self, path, *, _server=None, _json=True):
        """
        Convenience function for calling the Prefect API with token auth.

        Args:
            path: the path of the API url
        """
        response = self._request(method="delete", path=path, server=_server)
        if _json:
            if response.text:
                response = response.json()
            else:
                response = {}
        return response

    def graphql(self, query, **variables):
        """
        Convenience function for running queries against the Prefect GraphQL
        API
        """
        result = self._post(
            path="",
            query=query,
            variables=json.dumps(variables),
            _server=self._graphql_server,
        )
        if "errors" in result:
            raise ValueError(result["errors"])
        else:
            return to_dotdict(result).data

    def _request(self, method, path, params, server=None):

        # lazy import for performance
        import requests

        if server is None:
            server = self._api_server

        if self._token is None:
            raise ValueError("Call Client.login() to set the client token.")

        url = os.path.join(server, path.lstrip("/")).rstrip("/")

        params = params or {}

        # write this as a function to allow reuse in next try/except block
        def request_fn():
            headers = {"Authorization": "Bearer " + self._token}
            if method == "GET":
                response = requests.get(url, headers=headers, params=params)
            elif method == "POST":
                response = requests.post(url, headers=headers, json=params)
            elif method == "DELETE":
                response = requests.delete(url, headers=headers)
            else:
                raise ValueError("Invalid method: {}".format(method))

            response.raise_for_status()

            return response

        try:
            return request_fn()
        except requests.HTTPError as err:
            if err.response.status_code == 401:
                self.refresh_token()
                return request_fn()
            raise

    # -------------------------------------------------------------------------
    # Auth
    # -------------------------------------------------------------------------

    def login(self, email, password, account_slug=None, account_id=None):

        # lazy import for performance
        import requests

        url = os.path.join(self._api_server, "auth/login")
        response = requests.post(
            url,
            auth=(email, password),
            json=dict(account_id=account_id, account_slug=account_slug),
        )
        if not response.ok:
            raise ValueError("Could not log in.")
        self._token = response.json().get("token")

        if not (account_id or account_slug):
            print("No account provided; returning available accounts.")
            accounts = self._get("auth/accounts")
            return accounts

    def refresh_token(self):
        url = os.path.join(self._api_server, "auth/refresh")
        response = requests.post(
            url, headers={"Authorization": "Bearer " + self._token}
        )
        self._token = response.json().get("token")


class ClientModule:

    _path = ""

    def __init__(self, client, name=None):
        if name is None:
            name = type(self).__name__
        self._name = name
        self._client = client

    def __repr__(self):
        return "<Client Module: {name}>".format(name=self._name)

    def _get(self, path, **params):
        path = path.lstrip("/")
        return self._client._get(os.path.join(self._path, path), **params)

    def _post(self, path, **data):
        path = path.lstrip("/")
        return self._client._post(os.path.join(self._path, path), **data)

    def _delete(self, path, **params):
        path = path.lstrip("/")
        return self._client._delete(os.path.join(self._path, path), **params)

    def _graphql(self, query, **variables):
        return self._client.graphql(query=query, **variables)


# -------------------------------------------------------------------------
# Projects


class Projects(ClientModule):

    _path = "/projects"

    def create(self, name):
        return self._post(path="/", name=name)

    def list(self, per_page=100, page=1):
        """
        Lists all available projects
        """
        data = self._graphql(
            """
             query ($perPage: Int!, $page: Int!){
                projects(perPage: $perPage, page: $page){
                    id
                    name
                }
             }
             """,
            perPage=per_page,
            page=page,
        )
        return data["projects"]

    def flows(self, project_id):
        """
        Returns the Flows for the specified project
        """

        data = self._graphql(
            """
             query ($projectId: String!){
                projects(filter: {id: $projectId}) {
                    id
                    name
                    flows {
                        id
                        name
                    }
                }
             }
             """,
            projectId=project_id,
        )
        return data["projects"]


# -------------------------------------------------------------------------
# Flows


class Flows(ClientModule):

    _path = "/flows"

    def load(self, flow_id, safe=True):
        """
        Retrieve information about a Flow.

        Args:
            flow_id (str): the Flow's id
        """
        if safe:
            data = self._graphql(
                """
                query($flowId: String!) {
                    flow(id: $flowId) {
                        safe_serialized
                    }
                }
                """,
                flowId=flow_id,
            )

            return prefect.Flow.safe_deserialize(data["flow"]["safe_serialized"])
        else:
            data = self._graphql(
                """
                query($flowId: String!) {
                    flow(id: $flowId) {
                        serialized
                        tasks {
                            serialized
                        }
                        edges {
                            serialized
                        }
                    }
                }
                """,
                flowId=flow_id,
            )
            return prefect.Flow.deserialize(data["flow"])

    def set_state(self, flow_id, state):
        """
        Update a Flow's state
        """
        return self._post(path="/{id}/state".format(id=flow_id), state=state)

    def create(self, flow):
        """
        Submit a Flow to the server.
        """
        return self._post(path="/", serialized_flow=flow.serialize())


# -------------------------------------------------------------------------
# FlowRuns


class FlowRuns(ClientModule):

    _path = "/flow_runs"

    def get_state(self, flow_run_id):
        """
        Retrieve a flow run's state
        """

        data = self._graphql(
            """
             query ($flowRunId: String!){
                flow_runs(filter: {id: $flowRunId}) {
                    state {
                        state
                        result
                    }
                }
             }
             """,
            flowRunId=flow_run_id,
        )
        state = data.flow_runs[0].get("state", {})
        return prefect.engine.state.FlowState(
            state=state.get("state", None), result=state.get("result", None)
        )

    def set_state(self, flow_run_id, state, result=None, expected_state=None):
        """
        Retrieve a flow run's state
        """
        return self._post(
            path="/{id}/state".format(id=flow_run_id),
            state=state,
            result=dict(result=result),
            expected_state=expected_state,
        )

    def create(self, flow_id, parameters=None, parent_taskrun_id=None):
        return self._post(
            path="/",
            flow_id=flow_id,
            parameters=parameters,
            parent_taskrun_id=parent_taskrun_id,
        )

    def run(self, flow_run_id, start_tasks=None, inputs=None):
        """
        Queue a flow run to be run
        """
        if start_tasks is None:
            start_tasks = []
        if inputs is None:
            inputs = {}

        return self._post(
            path="/{id}/run".format(id=flow_run_id),
            start_tasks=start_tasks,
            inputs=inputs,
        )

    # def get_resume_url(
    #         self,
    #         flow_run_id=None,
    #         start_tasks=None,
    #         expires_in=datetime.timedelta(hours=1)):
    #     """
    #     If flow_run_id is None, it will attempt to infer it from the
    #     current context.
    #     """
    #     if flow_run_id is None:
    #         flow_run_id = prefect.context.Context.get('flow_run_id')
    #     data = self._post(
    #         path='/{id}/get_resume_url'.format(id=flow_run_id),
    #         start_tasks=start_tasks,
    #         expires_in=expires_in)
    #     return data['url']


# -------------------------------------------------------------------------
# TaskRuns


class TaskRuns(ClientModule):

    _path = "/task_runs"

    def get_state(self, task_run_id):
        """
        Retrieve a flow run's state
        """
        data = self._graphql(
            """
             query ($taskRunId: String!){
                task_runs(filter: {id: $taskRunId}) {
                    state {
                        state
                        result
                    }
                }
             }
             """,
            taskRunId=task_run_id,
        )
        state = data.task_runs[0].get("state", {})
        return prefect.engine.state.TaskState(
            state=state.get("state", None), result=state.get("result", None)
        )

    def set_state(self, task_run_id, state, result=None, expected_state=None):
        """
        Retrieve a task run's state
        """
        return self._post(
            path="/{id}/state".format(id=task_run_id),
            state=state,
            result=dict(result=result),
            expected_state=expected_state,
        )
