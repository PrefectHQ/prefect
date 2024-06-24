from enum import Enum


class EntrypointType(Enum):
    """
    Enum representing a entrypoint type.

    File path entrypoints are in the format: `path/to/file.py:function_name`.
    Module path entrypoints are in the format: `path.to.module.function_name`.
    """

    FILE_PATH = "file_path"
    MODULE_PATH = "module_path"
