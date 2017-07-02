import prefect
import os
import requests
import ujson


class AuthorizationError(Exception):
    pass


class Client:
    """
    Client for the Prefect API.
    """

    def __init__(self, server=None, api_version=1, token=None):
        if server is None:
            server = prefect.config.get('prefect', 'server')
        self._server = server
        self._api_version = api_version
        self._token = token

        self.namespaces = Namespaces(client=self)
        self.flows = Flows(client=self)
        self.flowruns = FlowRuns(client=self)

    # -------------------------------------------------------------------------
    # Utilities

    def _get(self, path, *, _json=True, **params):
        """
        Convenience function for calling the Prefect API with token auth.

        Args:
            path: the path of the API url. For example, to GET
                http://prefect-server/v1/login, path would be 'login'.
            params: GET parameters
        """
        response = self._request(method='GET', path=path, params=params)
        if _json:
            response = response.json()
        return response

    def _post(self, path, *, _json=True, **params):
        """
        Convenience function for calling the Prefect API with token auth.

        Args:
            path: the path of the API url. For example, to POST
                http://prefect-server/v1/login, path would be 'login'.
            params: POST params
        """
        response = self._request(method='POST', path=path, params=params)
        if _json:
            response = response.json()
        return response

    def _delete(self, path, *, _json=True):
        """
        Convenience function for calling the Prefect API with token auth.

        Args:
            path: the path of the API url
        """
        response = self._request(method='delete', path=path)
        if _json:
            response = response.json()
        return response

    def _request(self, method, path, params):
        path = path.lstrip('/')

        def request_fn():
            if self._token is None:
                raise ValueError('Call Client.login() to set the client token.')
            url = os.path.join(self._server, f'v{self._api_version}', path)

            if method.upper() == 'GET':
                response = requests.get(
                    url,
                    headers={'Authorization': self._token},
                    params=params)
            elif method.upper() == 'POST':
                response = requests.post(
                    url,
                    headers={'Authorization': self._token},
                    data=params)
            elif method.upper() == 'DELETE':
                response = requests.delete(
                    url,
                    headers={'Authorization': self._token})
            else:
                raise ValueError(f'Invalid method: {method}')

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

    def login(self, email, password):
        url = os.path.join(
            self._server, f'v{self._api_version}', 'login')
        response = requests.post(url, auth=(email, password))
        if not response.ok:
            raise ValueError('Could not log in.')
        self._token = response.json()['token']

    def refresh_token(self):
        response = self._post(path='refresh_token', token=self._token)
        self._token = response.json()['token']


class ClientModule:

    def __init__(self, client, name=None):
        if name is None:
            name = type(self).__name__
        self._name = name
        self._client = client

    def __repr__(self):
        return f'<Client Module: {self._name}>'

    def _get(self, path, **params):
        return self._client._get(path, **params)

    def _post(self, path, **data):
        return self._client._post(path, **data)

    def _delete(self, path, **params):
        return self._client._delete(path, **params)


class Namespaces(ClientModule):

    def list(self, per_page=100, page=1):
        """
        Lists all available namespaces
        """
        return self._get(
            path='namespaces', per_page=per_page, page=page)

    def get_flows(self, namespace_id):
        """
        Returns the Flows for the specified namespace
        """
        return self._get(path=f'namespaces/{namespace_id}/flows')


class Flows(ClientModule):

    def get(self, flow_id, serialized=False):
        """
        Retrieve information about a Flow.

        Args:
            flow_id (int): the Flow's id
            serialized (bool): if True, the result will include the
                serialized Flow
        """
        return self._get(path=f'flows/{flow_id}', serialized=serialized)

    def get_flowruns(self, flow_id, status=None, per_page=100, page=1):
        """
        Retrieve the Flow's FlowRuns.
        """
        return self._get(
            path=f'flows/{flow_id}/flowruns',
            status=status,
            per_page=per_page,
            page=page)

    def get_tasks(self, flow_id, status=None, per_page=500, page=1):
        """
        Retrieve the Flow's tasks and edges connecting them.
        """
        return self._get(
            path=f'flows/{flow_id}/tasks',
            per_page=per_page,
            page=page)

    def create(self, flow):
        """
        Submit a Flow to the server.
        """
        return self._post(
            path='flows/create',
            serialized_flow=ujson.dumps(flow.serialize()))

    def search(
            self,
            namespace=None,
            name=None,
            version=None,
            per_page=100,
            page=1):
        return self._post(
            path='flows/search',
            namespace=namespace,
            name=name,
            version=version,
            per_page=per_page,
            page=page
        )

    # def run_flow(
    #         self,
    #         flow_id,
    #         scheduled_start=None,
    #         parameters=None,
    #         resume_tasks=None,
    #         generating_taskrun_id=None):
    #     """
    #     Start (or schedule) a FlowRun on the server
    #     """
    #     result = self._post(
    #         path='flows/run',
    #         flow_id=flow_id,
    #         scheduled_start=scheduled_start,
    #         parameters=parameters,
    #         resume_tasks=resume_tasks,
    #         generating_taskrun_id=generating_taskrun_id)
    #     return result


class FlowRuns(ClientModule):

    def get(self, flowrun_id):
        """
        Describe a FlowRun
        """
        return self._get(path=f'flowruns/{flowrun_id}')

    def get_taskruns(self, flowrun_id, status=None, per_page=100, page=1):
        """
        Retrieve the FlowRun's TaskRuns
        """
        return self._get(
            path=f'flowruns/{flowrun_id}/taskruns',
            status=status,
            per_page=per_page,
            page=page)

    def get_state(self, flowrun_id):
        """
        Retrieve a FlowRun's state
        """
        return self._get(path=f'flowruns/{flowrun_id}/state')

    def set_state(self, flowrun_id, state, expected_state=None):
        """
        Retrieve a FlowRun's state
        """
        return self._post(
            path=f'flowruns/{flowrun_id}/state',
            state=state,
            expected_state=expected_state)

    def create(self, flow_id, parameters=None, parent_taskrun_id=None):
        return self._post(
            path='flowruns',
            flow_id=flow_id,
            parameters=parameters,
            parent_taskrun_id=parent_taskrun_id)

    def queue(self, flowrun_id, start_at=None, start_tasks=None):
        """
        Queue a FlowRun to be run
        """
        return self._post(
            path=f'flowruns/{flowrun_id}/queue',
            start_at=start_at,
            start_tasks=start_tasks)


    # def run(self, flow_id, scheduled_start=None):
