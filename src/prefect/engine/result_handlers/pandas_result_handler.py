import pandas as pd
import os
import typing

from prefect.engine.result_handlers.result_handler import ResultHandler


class PandasResultHandler(ResultHandler):
    """
    Hook for storing and retrieving task results in Pandas DataFrames.
    Task results are written/read via the standard Pandas
    ``to_[FILETYPE]``/``read_[FILETYPE]`` methods, and additionally the filename
    can be fully specified at task instantiation.

    Args:
        - path (str): Filepath to be read from or written to, including file name and extension.
        - file_type (str): The type of file to write to, e.g. "csv" or "parquet". Must match the name
            of the appropriate ``to_[FILETYPE]``/``read_[FILETYPE]`` method.
        - read_kwargs (dict, optional): If present, passed as **kwargs to the ``read_[FILETYPE]`` method.
        - write_kwargs (dict, optional): If present, passed as **kwargs to the ``to_[FILETYPE]`` method.

    .. note::
        Because the filepath is fully specified, when using this handler in a ``map``
        can lead to the same file being read to or written from by every iteration of
        the map. To deal with this case this handler allows for Python's ``str.format``
        to be used with the names of arguments to the task instance. For instance, if
        your task has an argument named ``sample_name`` that you intend to map over,
        supplying a ``file_type`` like ``"output_{sample_name}.csv"`` will fill in the
        values of that argument for each iteration of the map.
    """

    def __init__(
        self,
        path: str,
        file_type: str,
        read_kwargs: dict = None,
        write_kwargs: dict = None,
    ):

        # First, check and make sure the file type is supported. We only have to check one
        # of the mappings because they should have identical keys.
        read_ops_mapping, _ = self._generate_pandas_io_methods()
        if file_type.lower() not in read_ops_mapping:
            raise ValueError(
                """
                {file_type} not available.
                Known file extensions are {keys}.
                """.format(
                    file_type=file_type, keys=list(read_ops_mapping.keys())
                )
            )

        self.path = path
        self.file_type = file_type

        self.read_kwargs = read_kwargs if read_kwargs is not None else {}
        self.write_kwargs = write_kwargs if write_kwargs is not None else {}
        super().__init__()

    # This signature is a kludge, because the other result handlers expect the filename
    # to be passed into the function. With this signature any attempts to pass that handler
    # will be ignored, without accidentally being treated as the ``input_mapping`` kwarg
    def read(self, _, *, input_mapping=None) -> pd.DataFrame:
        """
        Read a result from the specified ``path`` using the appropriate ``read_[FILETYPE]`` method.

        Args:
            - input_mapping (dict, optional): If present, passed to ``path.format()`` to set the final
            filename. This is necessary for mapped tasks, to prevent the same file from being read
            from for each map sub-step.

        Returns:
            - the read result from the provided file
        """
        read_ops_mapping, _ = self._generate_pandas_io_methods()
        input_mapping = {} if input_mapping is None else input_mapping
        formatted_path = self.path.format(**input_mapping)
        self.logger.debug("Starting to read result from {}...".format(formatted_path))
        data = read_ops_mapping[self.file_type.lower()](
            formatted_path, **self.read_kwargs
        )
        self.logger.debug("Finished reading result from {}...".format(formatted_path))
        return data

    def write(self, result: pd.DataFrame, **kwargs: typing.Any) -> str:
        """
        Serialize the provided result to local disk using the appropriate ``to_[FILETYPE]`` method.

        Args:
            - result (pd.DataFrame): the result to write and store.
            - kwargs (Any): If present, passed to ``path.format()`` to set the final
            filename. This is necessary for mapped tasks, to prevent the same file from being read
            from for each map sub-step.

        Returns:
            - str: the _absolute_ path to the written result on disk. For compatibility purposes,
                since the full path is saved as an instance method and does not need to be provided to
                the ``read`` method.
        """
        _, write_ops_mapping = self._generate_pandas_io_methods()
        formatted_path = self.path.format(**kwargs)
        self.logger.debug("Starting to write result to {}...".format(formatted_path))
        write_function = getattr(result, self.write_ops_mapping[self.file_type.lower()])
        write_function(formatted_path, **self.write_kwargs)
        self.logger.debug("Finished writing result to {}...".format(formatted_path))

        return os.path.abspath(formatted_path)

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
