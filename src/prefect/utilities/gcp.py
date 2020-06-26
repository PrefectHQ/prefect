"""
Utility functions for interacting with Google Cloud.
"""
import prefect

from google.oauth2.service_account import Credentials


def get_google_client(submodule, credentials: dict = None, project: str = None):
    """
    Utility function for loading Google Client objects from a given set of credentials.

    Args:
        - submodule: a Python submodule with a Client attribute
        - credentials (dict, optional): a dictionary of Google credentials used to initialize
            the Client; if not provided, will attempt to load the Client using ambient
            environment settings
        - project (str, optional): the Google project to point the Client to; if not provided,
            Client defaults will be used

    Returns:
        - Client: an initialized and authenticated Google Client
    """
    Client = getattr(submodule, "Client")
    credentials = credentials or prefect.context.get("secrets", {}).get(
        "GCP_CREDENTIALS"
    )
    if credentials is not None:
        credentials = Credentials.from_service_account_info(credentials)
        project = project or credentials.project_id
        client = Client(project=project, credentials=credentials)
    else:
        client = Client(project=project)
    return client


def get_storage_client(credentials: dict = None, project: str = None):
    """
    Utility function for instantiating a Google Storage Client from a given set of credentials.

    Args:
        - credentials (dict, optional): a dictionary of Google credentials used to initialize
            the Client; if not provided, will attempt to load the Client using ambient
            environment settings
        - project (str, optional): the Google project to point the Client to; if not provided,
            Client defaults will be used

    Returns:
        - Client: an initialized and authenticated Google Client
    """
    from google.cloud import storage

    return get_google_client(storage, credentials=credentials, project=project)


def get_bigquery_client(credentials: dict = None, project: str = None):
    """
    Utility function for instantiating a Google BigQuery Client from a given set of credentials.

    Args:
        - credentials (dict, optional): a dictionary of Google credentials used to initialize
            the Client; if not provided, will attempt to load the Client using ambient
            environment settings
        - project (str, optional): the Google project to point the Client to; if not provided,
            Client defaults will be used

    Returns:
        - Client: an initialized and authenticated Google Client
    """
    from google.cloud import bigquery

    return get_google_client(bigquery, credentials=credentials, project=project)
