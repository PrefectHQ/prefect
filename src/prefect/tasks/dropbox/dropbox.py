import warnings

import dropbox

from prefect.client import Secret
from prefect.core import Task
from prefect.utilities.tasks import defaults_from_attrs


class DropboxDownload(Task):
    """
    Task for downloading a file from Dropbox. Note that _all_ initialization settings can be
    provided / overwritten at runtime.

    Args:
        - path (str, optional): the path to the file to download. May be provided at runtime.
        - access_token_secret (str, optional, DEPRECATED): the name of the Prefect Secret
            containing a Dropbox access token
        - **kwargs (optional): additional kwargs to pass to the `Task` constructor
    """

    def __init__(self, path: str = None, access_token_secret: str = None, **kwargs):
        self.path = path
        self.access_token_secret = access_token_secret
        super().__init__(**kwargs)

    @defaults_from_attrs("path", "access_token_secret")
    def run(
        self,
        path: str = None,
        access_token: str = None,
        access_token_secret: str = None,
    ) -> bytes:
        """
        Run method for this Task.  Invoked by _calling_ this Task within a Flow context, after
        initialization.

        Args:
            - path (str, optional): the path to the file to download
            - access_token (str): a Dropbox access token, provided with a Prefect secret.
            - access_token_secret (str, optional, DEPRECATED): the name of the Prefect Secret
                containing a Dropbox access token

        Raises:
            - ValueError: if the `path` is `None`

        Returns:
            - bytes: the file contents, as bytes
        """
        # check for any argument inconsistencies
        if path is None:
            raise ValueError("No path provided.")

        if access_token_secret is not None:
            warnings.warn(
                "The `access_token_secret` argument is deprecated. Use a `Secret` task "
                "to pass the credentials value at runtime instead.",
                UserWarning,
                stacklevel=2,
            )
            access_token = Secret(access_token_secret).get()
        dbx = dropbox.Dropbox(access_token)
        response = dbx.files_download(path)[1]
        return response.content
