"""
Result Handlers provide the hooks that Prefect uses to store task results in production; a
`ResultHandler` can be provided to a `Flow` at creation.

Anytime a task needs its output or inputs stored, a result handler is used to determine where
this data should be stored (and how it can be retrieved).
"""
import os
from typing import Any

import cloudpickle
import pendulum
from slugify import slugify

import prefect
from prefect.engine.result_handlers import ResultHandler


class LocalResultHandler(ResultHandler):
    """
    Hook for storing and retrieving task results from local file storage.
    Task results are written using `cloudpickle` and stored in the
    provided location for use in future runs.

    Args:
        - dir (str, optional): the _absolute_ path to a directory for storing
            all results; defaults to `${prefect.config.home_dir}/results`
        - validate (bool, optional): a boolean specifying whether to validate the
            provided directory path; if `True`, the directory will be converted to an
            absolute path and created.  Defaults to `True`
    """

    def __init__(self, dir: str = None, validate: bool = True):
        full_prefect_path = os.path.abspath(prefect.config.home_dir)
        if (
            dir is None
            or os.path.commonpath([full_prefect_path, os.path.abspath(dir)])
            == full_prefect_path
        ):
            directory = os.path.join(prefect.config.home_dir, "results")
        else:
            directory = dir

        if validate:
            abs_directory = os.path.abspath(os.path.expanduser(directory))
            if not os.path.exists(abs_directory):
                os.makedirs(abs_directory)
        else:
            abs_directory = directory
        self.dir = abs_directory
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
        fname = "prefect-result-" + slugify(pendulum.now("utc").isoformat())
        loc = os.path.join(self.dir, fname)
        self.logger.debug("Starting to upload result to {}...".format(loc))
        with open(loc, "wb") as f:
            f.write(cloudpickle.dumps(result))
        self.logger.debug("Finished uploading result to {}...".format(loc))
        return loc
