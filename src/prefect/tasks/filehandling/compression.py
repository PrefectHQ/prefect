"""
The tasks in this module can be used to handle file compression like zipping or
unzipping files.
"""
import os
import zipfile
from pathlib import Path
from typing import Any, List, Union
from zipfile import ZipFile

from prefect.utilities.tasks import defaults_from_attrs
from prefect.tasks.filehandling.base import FileBase


class Unzip(FileBase):
    """
    Task for unzipping data.

    Args:
        - zip_file_path (Union[str, Path], optional): path to the zip file
        - target_directory (Union[str, Path], optional): path to the target directory
        - zip_password (str, optional): password for extraction. This must be utf-8 encoded.
        - create_target_if_not_exists (bool, optional): Create the target directory if it
            doesn't exist (default: False)
        - use_filename_as_target_dir (bool, optional): Extracts data within a folder named
            like the zip archive (without extension). If True, the basename of the zip archive will
            be attached to the target_directory and may create a new folder. (default: False)
        - remove_after_unzip (bool, optional): Removes the zip archive after extraction (default: False)
        - **kwargs (dict, optional): additional keyword arguments to pass to the
            Task constructor
    """

    def __init__(
        self,
        zip_file_path: Union[str, Path] = "",
        target_directory: Union[str, Path] = "",
        zip_password: str = None,
        create_target_if_not_exists: bool = False,
        use_filename_as_target_dir: bool = False,
        remove_after_unzip: bool = False,
        **kwargs: Any,
    ):
        self.zip_file_path = zip_file_path
        self.target_directory = target_directory
        self.zip_password = zip_password
        self.create_target_if_not_exists = create_target_if_not_exists
        self.use_filename_as_target_dir = use_filename_as_target_dir
        self.remove_after_unzip = remove_after_unzip
        super().__init__(**kwargs)

    @defaults_from_attrs(
        "zip_file_path",
        "target_directory",
        "zip_password",
        "create_target_if_not_exists",
        "use_filename_as_target_dir",
        "remove_after_unzip",
    )
    def run(
        self,
        zip_file_path: Union[str, Path] = "",
        target_directory: Union[str, Path] = "",
        zip_password: str = None,
        create_target_if_not_exists: bool = False,
        use_filename_as_target_dir: bool = False,
        remove_after_unzip: bool = False,
    ):
        """
        Task run method.

        Args:
            - zip_file_path (Union[str, Path], optional): path to the zip file
            - target_directory (Union[str, Path], optional): path to the target directory
            - zip_password (str, optional): password for extraction. This must be utf-8 encoded.
            - create_target_if_not_exists (bool, optional): Create the target directory if it
                doesn't exist (default: False)
            - use_filename_as_target_dir (bool, optional): Extracts data within a folder named
                like the zip archive (without extension). If True, the basename of the zip archive will
                be attached to the target_directory and may create a new folder. (default: False)
            - remove_after_unzip (bool, optional): Removes the zip archive after
                extraction (default: False)

        Returns:
            - Target directory as a Path object

        Raises:
            - ValueError: if source_file not found
            - TypeError: if source_file is not a zip file
            - ValueError: if target_directory not found and create_target_if_not_exists = False
        """
        zip_file_path = Path(zip_file_path)
        target_directory = Path(target_directory)
        if not zip_file_path.is_file():
            raise ValueError(f"Source file ({zip_file_path}) not found!")
        elif not zipfile.is_zipfile(zip_file_path):
            raise TypeError(f"Source file ({zip_file_path}) is not a zip file")

        self._check_target_path(target_directory, create_target_if_not_exists)

        if use_filename_as_target_dir:
            target_directory = target_directory.joinpath(zip_file_path.stem)
            target_directory.mkdir(exist_ok=True)

        self.logger.info(f"Extracting {zip_file_path} to {target_directory}")

        if zip_password:
            zip_password = bytes(zip_password, "utf-8")
        with ZipFile(zip_file_path, "r") as zip:
            zip.extractall(target_directory, pwd=zip_password)

        if remove_after_unzip:
            self.logger.info(f"Removing {zip_file_path} after extraction.")
            os.remove(zip_file_path)

        return target_directory


class Zip(FileBase):
    """
    Task to create a zip archive.

    Args:
        - source_path (Union[str, Path, List[str], List[Path]], optional): a single path or a list of
            multiple paths for compression into a single zip archive.
        - target_directory (Union[str, Path], optional): path to the target directory
        - zip_file_name (str, optional): name of the zip archive. If not set the name will be generated
            by the following rules:
                1. if the first object in the source_path is a single file
                    => basename of the source file without extension
                2. if the first object in the source_path is a directory
                    => parent name of the directory
        - create_target_if_not_exists (bool, optional): Create the target directory if it
            doesn't exist (default: False)
        - compression: (int, optional): pass in a supported compression method
            https://docs.python.org/3/library/zipfile.html?highlight=zipfile#zipfile-objects
        - compression_level(int, optional): pass in a supported compression level
            https://docs.python.org/3/library/zipfile.html?highlight=zipfile#zipfile-objects
        - **kwargs (dict, optional): additional keyword arguments to pass to the
            Task constructor
    """

    def __init__(
        self,
        source_path: Union[str, Path, List[str], List[Path]] = "",
        target_directory: Union[str, Path] = "",
        zip_file_name: str = "",
        zip_password: str = None,
        create_target_if_not_exists: bool = False,
        compression: int = None,
        compression_level: int = None,
        **kwargs: Any,
    ):
        self.source_path = source_path
        self.target_directory = target_directory
        self.zip_file_name = zip_file_name
        self.zip_password = zip_password
        self.create_target_if_not_exists = create_target_if_not_exists
        self.compression = compression
        self.compression_level = compression_level
        super().__init__(**kwargs)

    @defaults_from_attrs(
        "source_path",
        "target_directory",
        "zip_file_name",
        "zip_password",
        "create_target_if_not_exists",
    )
    def run(
        self,
        source_path: Union[str, Path, List[str], List[Path]] = "",
        target_directory: Union[str, Path] = "",
        zip_file_name: str = "",
        zip_password: str = None,
        create_target_if_not_exists: bool = False,
    ):
        """
        Task run method.

        Args:
            - source_path (Union[str, Path, List[str], List[Path]], optional): a single path or a list of
                multiple paths for compression into a single zip archive.
            - target_directory (Union[str, Path], optional): path to the target directory
            - zip_file_name (str, optional): name of the zip archive. If not set the name will be
                generated by the following rules:
                    1. if the first object in the source_path is a single file
                        => basename of the source file without extension
                    2. if the first object in the source_path is a directory
                        => parent name of the directory
            - create_target_if_not_exists (bool, optional): Create the target directory if it
                doesn't exist (default: False)

        Returns:
            - Path object of the created zip archive

        Raises:
            - ValueError: if source_path not set
            - ValueError: if target_directory not found and create_target_if_not_exists = False
        """
        if not source_path:
            raise ValueError("Source path is not defined.")

        target_directory = Path(target_directory)
        self._check_target_path(target_directory, create_target_if_not_exists)

        if not isinstance(source_path, list):
            source_path = [Path(source_path)]
        else:
            source_path = [Path(sp) for sp in source_path]

        if not zip_file_name:
            if source_path[0].is_file():
                zip_file_name = f"{source_path[0].stem}.zip"
            else:
                zip_file_name = f"{source_path[0].name}.zip"
        else:
            if not zip_file_name.endswith(".zip"):
                zip_file_name += ".zip"

        target_zip = target_directory.joinpath(zip_file_name)

        with ZipFile(
            target_zip,
            "w",
            compression=self.compression,
            compresslevel=self.compression_level,
        ) as zip:
            self.logger.info(f"Creating zip archive {target_zip}")
            print(zip)
            print(type(zip.write()), dir(zip), dir(zip.write()))
            for f in source_path:
                self.logger.info(f"Adding {f.name} to {zip_file_name}")
                if f.is_file():
                    zip.write(f, arcname=f.name)
                else:
                    for root, dirs, files in os.walk(f):
                        for file in files:
                            fp = Path(root).joinpath(file)
                            zip.write(fp, arcname=fp.relative_to(f.parent))

        return target_zip
