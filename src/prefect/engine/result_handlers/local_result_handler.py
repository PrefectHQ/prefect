"""
Result Handlers provide the hooks that Prefect uses to store task results in production; a `ResultHandler` can be provided to a `Flow` at creation.

Anytime a task needs its output or inputs stored, a result handler is used to determine where this data should be stored (and how it can be retrieved).
"""
import base64
import tempfile
from typing import Any

import cloudpickle

from prefect.engine.result_handlers import ResultHandler


class LocalResultHandler(ResultHandler):
    """
    Hook for storing and retrieving task results from local file storage. Only intended to be used
    for local testing and development. Task results are written using `cloudpickle` and stored in the
    provided location for use in future runs.

    **NOTE**: Stored results will _not_ be automatically cleaned up after execution.

    Args:
        - dir (str, optional): the _absolute_ path to a directory for storing
            all results; defaults to `$TMPDIR`
    """

    def __init__(self, dir: str = None):
        self.dir = dir
        super().__init__()

    def read(self, fpath: str) -> Any:
        """
        Read a result from the given file location.

        Args:
            - fpath (str): the _absolute_ path to the location of a written result

        Returns:
            - the read result from the provided file
        """
        self.logger.debug("Starting to read result from {}...".format(fpath))
        with open(fpath, "rb") as f:
            val = cloudpickle.loads(f.read())
        self.logger.debug("Finished reading result from {}...".format(fpath))
        return val

    def write(self, result: Any) -> str:
        """
        Serialize the provided result to local disk.

        Args:
            - result (Any): the result to write and store

        Returns:
            - str: the _absolute_ path to the written result on disk
        """
        fd, loc = tempfile.mkstemp(prefix="prefect-", dir=self.dir)
        self.logger.debug("Starting to upload result to {}...".format(loc))
        with open(fd, "wb") as f:
            f.write(cloudpickle.dumps(result))
        self.logger.debug("Finished uploading result to {}...".format(loc))
        return loc
