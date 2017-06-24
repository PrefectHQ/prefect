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

    def _get(self, path, **params):
        """
        Convenience function for calling the Prefect API with token auth.

        Args:
            path: the path of the API url. For example, to GET
                http://prefect-server/v1/login, path would be 'login'.
            params: GET parameters
        """
        return self._request(method='GET', path=path, params=params)

    def _post(self, path, **data):
        """
        Convenience function for calling the Prefect API with token auth.

        Args:
            path: the path of the API url. For example, to POST
                http://prefect-server/v1/login, path would be 'login'.
            data: POST data
        """
        return self._request(method='POST', path=path, params=data)

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
            else:
                raise ValueError(f'Invalid method: {method}')

            if not response.ok:
                err = f'ERROR {response.status_code}: {response.content}'
                if int(response.status_code) == 401:
                    raise AuthorizationError(err)
                else:
                    raise ValueError(err)

            return response

        try:
            return request_fn()
        except AuthorizationError:
            self.refresh_token()
            return request_fn()

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
        response = self._get(path='refresh_token', token=self._token)
        self._token = response.json()['token']


class ClientModule:

    def __init__(self, client, name=None):
        if name is None:
            name = type(self).__name__
        self._name = name
        self._client = client

    def __repr__(self):
        return f'<Client Module: {self.name}>'



class Namespaces(ClientModule):

    def list(self):
        """
        Lists all available namespaces
        """
        return self._client._get(path='namespaces').json()

    def get(self, namespace_id):
        """
        Returns a JSON object describing the specified Namespace
        """
        return self._client._get(path=f'namespaces/{namespace_id}').json()


class Flows(ClientModule):

    def get(self, flow_id):
        """
        Returns a JSON object describing the specified Flow
        """
        return self._client._get(path=f'flows/{flow_id}').json()

    def submit(self, flow):
        """
        Submit a Flow to the server.
        """
        return self._client._post(
            path='flows/submit',
            serialized_flow=ujson.dumps(flow.serialize()))

    def search_flows(
            self,
            namespace=None,
            name=None,
            version=None,
            per_page=100,
            page=1):
        return self._client._post(
            path='flows/search',
            namespace=namespace,
            name=name,
            version=version,
            per_page=per_page,
            page=page
        ).json()

    def run_flow(
            self,
            flow_id,
            scheduled_start=None,
            parameters=None,
            resume_tasks=None,
            generating_taskrun_id=None):
        """
        Start (or schedule) a FlowRun on the server
        """
        return self._client._post(
            path='flows/run',
            flow_id=flow_id,
            scheduled_start=scheduled_start,
            parameters=parameters,
            resume_tasks=resume_tasks,
            generating_taskrun_id=generating_taskrun_id)

class FlowRuns(ClientModule):

    def get(self, flowrun_id):
        return self._client._get(path=f'flowruns/{flowrun_id}').json()
