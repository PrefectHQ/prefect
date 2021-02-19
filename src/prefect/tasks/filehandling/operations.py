from pathlib import Path
from typing import Union, Any
from prefect.utilities.tasks import defaults_from_attrs
from prefect.tasks.filehandling.base import FileBase


class Move(FileBase):
    """
    Task for moving files or directories within the file system.

    Args:
        - source_path (Union[str, Path], optional): the path to a directory or file
        - target_path (Union[str, Path], optional): path to the target directory
        - target_filename (str, optional): target file name (only relevant if source_path is a file)
            if not set: same as source (default)
        - create_target_if_not_exists (bool, optional): Create the target directory if it
            doesn't exist (default: False)
        - **kwargs (dict, optional): additional keyword arguments to pass to the
            Task constructor
    """

    def __init__(
        self,
        source_path: Union[str, Path] = "",
        target_path: Union[str, Path] = "",
        target_filename: str = "",
        create_target_if_not_exists: bool = False,
        **kwargs: Any,
    ):
        self.source_path = source_path
        self.target_path = target_path
        self.target_filename = target_filename
        self.create_target_if_not_exists = create_target_if_not_exists
        super().__init__(**kwargs)

    @defaults_from_attrs(
        "source_path",
        "target_path",
        "target_filename",
        "create_target_if_not_exists",
    )
    def run(
        self,
        source_path: Union[str, Path] = "",
        target_path: Union[str, Path] = "",
        target_filename: str = None,
        create_target_if_not_exists: bool = False,
    ):
        """
        Task run method.

        Args:
            - source_path (Union[str, Path], optional): the path to a directory or file
            - target_path (Union[str, Path], optional): path to the target directory
            - target_filename (str, optional): target file name (only relevant if source_path is a file)
                if not set: same as source (default)
            - create_target_if_not_exists (bool, optional): Create the target directory if it
                doesn't exist (default: False)

        Returns:
            - Path object of target path

        Raises:
            - ValueError: if source_path not set
            - ValueError: if target_directory not found and create_target_if_not_exists = False
        """
        source_path = Path(source_path)
        target_path = Path(target_path)

        if not source_path.exists():
            raise ValueError(f"Source path ({source_path}) not found!")

        self._check_target_path(target_path, create_target_if_not_exists)

        if not target_filename and source_path.is_file():
            # add filename to target path:
            target_path = target_path.joinpath(source_path.name)
        elif target_filename and source_path.is_file():
            target_path = target_path.joinpath(target_filename)

        self.logger.info(f"Moving {source_path} to {target_path}")
        source_path.rename(target_path)

        return target_path
