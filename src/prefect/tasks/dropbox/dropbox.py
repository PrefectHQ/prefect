import dropbox

from prefect.core import Task
from prefect.utilities.tasks import defaults_from_attrs


class DropboxDownload(Task):
    """
    Task for downloading a file from Dropbox. Note that _all_ initialization settings can be
    provided / overwritten at runtime.

    Args:
        - path (str, optional): the path to the file to download. May be provided at runtime.
        - **kwargs (optional): additional kwargs to pass to the `Task` constructor
    """

    def __init__(self, path: str = None, **kwargs):
        self.path = path
        super().__init__(**kwargs)

    @defaults_from_attrs("path")
    def run(
        self,
        path: str = None,
        access_token: str = None,
    ) -> bytes:
        """
        Run method for this Task.  Invoked by _calling_ this Task within a Flow context, after
        initialization.

        Args:
            - path (str, optional): the path to the file to download
            - access_token (str): a Dropbox access token, provided with a Prefect secret.

        Raises:
            - ValueError: if the `path` is `None`

        Returns:
            - bytes: the file contents, as bytes
        """
        # check for any argument inconsistencies
        if path is None:
            raise ValueError("No path provided.")

        dbx = dropbox.Dropbox(access_token)
        response = dbx.files_download(path)[1]
        return response.content
