import os
from slugify import slugify
from typing import Any

import pendulum

from prefect import config
from prefect.engine.result import Result


class LocalResult(Result):
    """
    Result that is written to and retrieved from the local file system.

    **Note**: "local" refers to where the flow's tasks execute, which is not
    necessarily the same as the place that `flow.run()` runs from. So, for
    example, if you use a `LocalEnvironment` with a `DaskExecutor` pointed at
    a remote Dask cluster, `LocalResult` files will be written to the Dask
    workers' file system.

    **Note**: If this result raises a `PermissionError` that could mean it is attempting
    to write results to a directory that it is not permissioned for. In that case it may be
    helpful to specify a specific `dir` for that result instance.

    Args:
        - dir (str, optional): the _absolute_ path to a directory for storing
            all results; defaults to `${prefect.config.home_dir}/results`
        - validate_dir (bool, optional): a boolean specifying whether to validate the
            provided directory path; if `True`, the directory will be converted to an
            absolute path and created.  Defaults to `True`
        - **kwargs (Any, optional): any additional `Result` initialization options
    """

    def __init__(
        self, dir: str = None, validate_dir: bool = True, **kwargs: Any
    ) -> None:
        full_prefect_path = os.path.abspath(config.home_dir)
        common_path = ""
        try:
            if dir is not None:
                common_path = os.path.commonpath(
                    [full_prefect_path, os.path.abspath(dir)]
                )
        except ValueError:
            # ValueError is raised if comparing two paths in Windows from different drives,
            # e.g., E:/ and C:/
            pass
        if dir is None or common_path == full_prefect_path:
            directory = os.path.join(config.home_dir, "results")
        else:
            directory = dir

        if validate_dir:
            abs_directory = os.path.abspath(os.path.expanduser(directory))
            if not os.path.exists(abs_directory):
                os.makedirs(abs_directory)
        else:
            abs_directory = directory
        self.dir = abs_directory

        super().__init__(**kwargs)

    @property
    def default_location(self) -> str:
        fname = "prefect-result-" + slugify(pendulum.now("utc").isoformat())
        location = os.path.join(self.dir, fname)
        return location

    def read(self, location: str) -> Result:
        """
        Reads a result from the local file system and returns the corresponding `Result` instance.

        Args:
            - location (str): the location to read from

        Returns:
            - Result: a new result instance with the data represented by the location
        """
        new = self.copy()
        new.location = location

        self.logger.debug("Starting to read result from {}...".format(location))

        with open(os.path.join(self.dir, location), "rb") as f:
            value = f.read()

        new.value = self.serializer.deserialize(value)

        self.logger.debug("Finished reading result from {}...".format(location))

        return new

    def write(self, value_: Any, **kwargs: Any) -> Result:
        """
        Writes the result to a location in the local file system and returns a new `Result`
        object with the result's location.

        Args:
            - value_ (Any): the value to write; will then be stored as the `value` attribute
                of the returned `Result` instance
            - **kwargs (optional): if provided, will be used to format the location template
                to determine the location to write to

        Returns:
            - Result: returns a new `Result` with both `value` and `location` attributes
        """
        new = self.format(**kwargs)
        new.value = value_
        assert new.location is not None

        self.logger.debug("Starting to upload result to {}...".format(new.location))

        full_path = os.path.join(self.dir, new.location)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)

        value = self.serializer.serialize(new.value)

        with open(full_path, "wb") as f:
            f.write(value)

        new.location = full_path
        self.logger.debug("Finished uploading result to {}...".format(new.location))

        return new

    def exists(self, location: str, **kwargs: Any) -> bool:
        """
        Checks whether the target result exists in the file system.

        Does not validate whether the result is `valid`, only that it is present.

        Args:
            - location (str): Location of the result in the specific result target.
                Will check whether the provided location exists
            - **kwargs (Any): string format arguments for `location`

        Returns:
            - bool: whether or not the target result exists
        """
        return os.path.exists(os.path.join(self.dir, location.format(**kwargs)))
