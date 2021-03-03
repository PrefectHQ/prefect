import shutil
from pathlib import Path
from typing import Any, Union

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


class Copy(Task):
    """
    Task for copying files or directories within the file system.

    Args:
        - source_path (Union[str, Path], optional): the path to the source directory/file.
        - target_path (Union[str, Path], optional): the path to the target directory/file.
            If copying a directory: directory content will be copied directly into the
            target directory, no extra directory will be added!
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
            - target_path (Union[str, Path], optional): the path to the target directory/file.
                If copying a whole directory: directory content will be copied directly into the
                target directory, no extra directory will be added!

        Returns:
            - Path: resulting path of the copied file / directory
        """
        if not source_path:
            raise ValueError("No `source_path` provided.")
        if not target_path:
            raise ValueError("No `target_path` provided.")

        source_path = Path(source_path)
        target_path = Path(target_path)

        if not source_path.exists():
            raise ValueError(f"Source path ({source_path}) not found")

        self.logger.info(f"Copying {source_path} to {target_path}...")

        if source_path.is_file():
            out = shutil.copy(source_path, target_path)
        else:
            out = shutil.copytree(source_path, target_path, dirs_exist_ok=True)
        return Path(out)


class Remove(Task):
    """
    Task for removing files or directories within the file system.

    Args:
        - remove_path (Union[str, Path], optional): file or directory to be removed
            If deleting a directory, the directory must be empty.
        - **kwargs (dict, optional): additional keyword arguments to pass to the
            Task constructor
    """

    def __init__(
        self,
        remove_path: Union[str, Path] = "",
        **kwargs: Any,
    ):
        self.remove_path = remove_path
        super().__init__(**kwargs)

    @defaults_from_attrs(
        "remove_path",
    )
    def run(self, remove_path: Union[str, Path] = "") -> None:
        """
        Task run method.

        Args:
            - remove_path (Union[str, Path], optional): file or directory to be removed
        """
        if not remove_path:
            raise ValueError("No `remove_path` provided.")

        remove_path = Path(remove_path)

        if not remove_path.exists():
            raise ValueError(f"Path ({remove_path}) not found")

        self.logger.info(f"Removing {remove_path}...")

        if remove_path.is_file():
            remove_path.unlink()
        else:
            remove_path.rmdir()
