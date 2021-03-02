import shutil
from pathlib import Path
from typing import Union, Any

from prefect import Task
from prefect.utilities.tasks import defaults_from_attrs


class Move(Task):
    """
    Task for moving files or directories within the file system.

    Args:
        - source_path (Union[str, Path], optional): the path to the source directory/file.
        - target_path (Union[str, Path], optional): the path to the target directory/file. Any
            parent directories of `target_path` must already exist.
        - **kwargs (dict, optional): additional keyword arguments to pass to the
            Task constructor
    """

    def __init__(
        self,
        source_path: Union[str, Path] = "",
        target_path: Union[str, Path] = "",
        **kwargs: Any,
    ):
        self.source_path = source_path
        self.target_path = target_path
        super().__init__(**kwargs)

    @defaults_from_attrs(
        "source_path",
        "target_path",
    )
    def run(
        self,
        source_path: Union[str, Path] = "",
        target_path: Union[str, Path] = "",
    ) -> Path:
        """
        Task run method.

        Args:
            - source_path (Union[str, Path], optional): the path to the source directory/file.
            - target_path (Union[str, Path], optional): the path to the target directory/file. Any
                parent directories of `target_path` must already exist.

        Returns:
            - Path: resulting path of the moved file / directory
        """
        if not source_path:
            raise ValueError("No `source_path` provided.")
        if not target_path:
            raise ValueError("No `target_path` provided.")

        source_path = Path(source_path)
        target_path = Path(target_path)

        if not source_path.exists():
            raise ValueError(f"Source path ({source_path}) not found")

        self.logger.info(f"Moving {source_path} to {target_path}...")

        # convert args to str...Path-like objects are supported 3.9+
        out = shutil.move(str(source_path), str(target_path))
        return Path(out)
