import pandas as pd
import typing


def _generate_pandas_io_methods() -> typing.Tuple[typing.Dict[str, typing.Callable], typing.Dict[str, str]]:
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
    all_read_ops = [method for method in dir(pd) if method.lower().startswith("read_")]
    all_write_ops = [method for method in dir(pd.DataFrame) if method.lower().startswith("to_")]

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
