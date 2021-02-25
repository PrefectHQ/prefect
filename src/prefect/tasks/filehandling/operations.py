from pathlib import Path
import sys
from shutil import move
from typing import Union, Any
from prefect.utilities.tasks import defaults_from_attrs
from prefect.tasks.filehandling.base import FileBase


class Move(FileBase):
    """
    Task for moving files or directories within the file system.

    Args:
        - source_path (Union[str, Path], optional): the path to the source directory/file.
        - target_path (Union[str, Path], optional): the path to the target directory/file. Any
            parent directories of `target` must already exist.
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
    ):
        """
        Task run method.

        Args:
            - source_path (Union[str, Path], optional): the path to the source directory/file.
            - target_path (Union[str, Path], optional): the path to the target directory/file. Any
                parent directories of `target` must already exist.

        Returns:
            - Path to the moved file / directory as a Path object

        Raises:
            - ValueError: if source_path doesn't exists
            - ValueError: if target_path is not set
        """
        source_path = Path(source_path)
        target_path = Path(target_path)

        self._check_path_exists(source_path, "Source")
        self._check_path_is_set(target_path, "Target")

        self.logger.info(f"Moving {source_path}...")

        if sys.version_info >= (3, 9):
            target = move(source_path, target_path)
        else:
            # convert to str...Path-like objects are supported 3.9+
            target = move(str(source_path), str(target_path))

        self.logger.info(f"New location: {target}")
        return Path(target)
