import os
import pendulum
import typing

try:
    import pandas as pd
except ImportError:
    pass  # Allows other tests

from slugify import slugify

from prefect.engine.result import Result
from prefect.engine.results import LocalResult


class PandasResult(LocalResult):
    """
    Result that is written to and retrieved from the local file system using Pandas I/O methods.

    **Note**: If this result raises a `PermissionError` that could mean it is attempting
    to write results to a directory that it is not permissioned for. In that case it may be
    helpful to specify a specific `dir` for that result instance.

    Args:
        - file_type (str, optional): The type of file to write to, e.g. "csv" or "parquet". Must match the name
            of the appropriate ``to_[FILETYPE]``/``read_[FILETYPE]`` method; defaults to "csv"
        - read_kwargs (dict, optional): If present, passed as **kwargs to the ``read_[FILETYPE]`` method.
        - write_kwargs (dict, optional): If present, passed as **kwargs to the ``to_[FILETYPE]`` method.
        - dir (str, optional): the _absolute_ path to a directory for storing
            all results; defaults to `${prefect.config.home_dir}/results`
        - validate_dir (bool, optional): a boolean specifying whether to validate the
            provided directory path; if `True`, the directory will be converted to an
            absolute path and created.  Defaults to `True`
        - **kwargs (Any, optional): any additional `Result` initialization options
    """

    def __init__(
        self,
        file_type: str = "csv",
        read_kwargs: dict = None,
        write_kwargs: dict = None,
        dir: str = None,
        validate_dir: bool = True,
        **kwargs: typing.Any
    ) -> None:

        self.file_type = file_type
        self.read_kwargs = read_kwargs if read_kwargs is not None else {}
        self.write_kwargs = write_kwargs if write_kwargs is not None else {}

        super().__init__(dir=dir, validate_dir=validate_dir, **kwargs)

    @property
    def default_location(self) -> str:
        fname = (
            "prefect-result-"
            + slugify(pendulum.now("utc").isoformat())
            + "."
            + self.file_type
        )
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
        read_ops_mapping, _ = self._generate_pandas_io_methods()
        read_function = read_ops_mapping[self.file_type.lower()]

        self.logger.debug("Starting to read result from {}...".format(location))

        new.value = read_function(os.path.join(self.dir, location), **self.read_kwargs)

        self.logger.debug("Finished reading result from {}...".format(location))

        return new

    def write(self, value: typing.Any, **kwargs: typing.Any) -> Result:
        """
        Writes the result to a location in the local file system and returns a new `Result`
        object with the result's location.

        Args:
            - value (Any): the value to write; will then be stored as the `value` attribute
                of the returned `Result` instance
            - **kwargs (optional): if provided, will be used to format the location template
                to determine the location to write to

        Returns:
            - Result: returns a new `Result` with both `value` and `location` attributes
        """
        new = self.format(**kwargs)
        new.value = value
        assert new.location is not None

        _, write_ops_mapping = self._generate_pandas_io_methods()
        write_function = getattr(value, write_ops_mapping[self.file_type.lower()])

        self.logger.debug("Starting to upload result to {}...".format(new.location))

        full_path = os.path.join(self.dir, new.location)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        write_function(full_path, **self.write_kwargs)

        self.logger.debug("Finished uploading result to {}...".format(new.location))

        return new

    @staticmethod
    def _generate_pandas_io_methods() -> typing.Tuple[
        typing.Dict[str, typing.Callable], typing.Dict[str, str]
    ]:
        """
        Helper function to automatically identify possible file types to read to and write from.
        Returns:
            - tuple: each element is a dictionary of ``{file_extension: method}`` (e.g. ``{"csv": pd.read_csv}``).
            The first element is for read operations (``pd.read_csv``, ``pd.read_parquet``, etc),
            the second element is for write operations, which must be represented as strings because they are
            bound to individual DataFrames.

        """
        # Get all methods/attributes in the pandas module that start with "read_", and all
        # methods/attributes in the pandas.DataFrame class that start with "to_"
        all_read_ops = [
            method for method in dir(pd) if method.lower().startswith("read_")
        ]
        all_write_ops = [
            method for method in dir(pd.DataFrame) if method.lower().startswith("to_")
        ]

        # Split out the file suffixes from the "read_"/"to_" methods
        read_suffixes = [method.lower().split("_")[1] for method in all_read_ops]
        write_suffixes = [method.lower().split("_")[1] for method in all_write_ops]

        # Take all suffixes that appear in both read and write methods, then map into a
        # convenient dictionary
        read_io_ops = {
            read_method.split("_")[1].lower(): getattr(pd, read_method)
            for read_method in all_read_ops
            if read_method.split("_")[1].lower() in write_suffixes
        }
        write_io_ops = {
            write_method.split("_")[1].lower(): write_method
            for write_method in all_write_ops
            if write_method.split("_")[1].lower() in read_suffixes
        }

        return read_io_ops, write_io_ops
