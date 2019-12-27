from google.cloud import bigquery
from google.cloud import storage
from google.oauth2.service_account import Credentials


def _get_google_client(submodule, credentials: dict = None, project: str = None):
    Client = getattr(submodule, "Client")
    if credentials is not None:
        credentials = Credentials.from_service_account_info(credentials)
        project = project or credentials.project_id
        client = Client(project=project, credentials=credentials)
    else:
        client = Client(project=project)
    return client


def get_storage_client(credentials: dict = None, project: str = None):
    return _get_google_client(storage, credentials=credentials, project=project)


def get_bigquery_client(credentials: dict = None, project: str = None):
    return _get_google_client(bigquery, credentials=credentials, project=project)
