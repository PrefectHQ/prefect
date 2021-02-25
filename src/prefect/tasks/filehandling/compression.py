"""
The tasks in this module can be used to handle file compression like zipping or
unzipping files.
"""
import os
import sys
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
        - source (Union[str, Path], optional): the path to the zip file
        - target_path (Union[str, Path], optional): directory to extract the zip file into.
            If not provided, the current working directory will be used. This directory must
            already exist.
        - **kwargs (dict, optional): additional keyword arguments to pass to the
            Task constructor
    """

    def __init__(
        self,
        source: Union[str, Path] = "",
        target_path: Union[str, Path] = "",
        **kwargs: Any,
    ):
        self.source = source
        self.target_path = target_path
        super().__init__(**kwargs)

    @defaults_from_attrs(
        "source",
        "target_path",
    )
    def run(
        self,
        source: Union[str, Path] = "",
        target_path: Union[str, Path] = "",
        password: str = None,
    ):
        """
        Task run method.

        Args:
            - source (Union[str, Path], optional): the path to the zip file
            - target_path (Union[str, Path], optional): directory to extract the zip file into.
                If not provided, the current working directory will be used. This directory must
                already exist.
            - password (str, optional): password for unzipping a password-protected zip file.
                This must be utf-8 encoded.

        Returns:
            - Target directory as a Path object

        Raises:
            - ValueError: if source not found
            - TypeError: if source is not a zip file
        """
        source = Path(source)
        target_path = Path(target_path or Path.cwd())

        self._check_path_exists(source, "Source")

        if not zipfile.is_zipfile(source):
            raise TypeError(f"Source file ({source}) is not a zip file")

        self.logger.info(f"Extracting {source} to {target_path}")

        if password:
            password = bytes(password, "utf-8")
        with ZipFile(source, "r") as zip:
            zip.extractall(target_path, pwd=password)

        return target_path


class Zip(FileBase):
    """
    Task to create a zip archive.

    Args:
        - source (Union[str, Path, List[str], List[Path]], optional): a path or paths to compress
             into a single zip archive.
        - target_path (Union[str, Path], optional): path to the output archive file. Any parent
            directories of `target` must already exist.
        - compression_method (str, optional): the compression method to use. Options are
            "deflate", "store", "bzip2", and "lzma". Defaults to `"deflate"`.
        - compression_level (int, optional): Compression level to use,
            see https://docs.python.org/3/library/zipfile.html#zipfile.ZipFile for more info.
            !! Python 3.7+ only !!
        - **kwargs (dict, optional): additional keyword arguments to pass to the
            Task constructor
    """

    def __init__(
        self,
        source: Union[str, Path, List[str], List[Path]] = "",
        target_path: Union[str, Path] = "",
        compression_method: str = "deflate",
        compression_level: int = None,
        **kwargs: Any,
    ):
        self.source = source
        self.target_path = target_path

        if compression_method == "store":
            self.compression = zipfile.ZIP_STORED
        elif compression_method == "deflate":
            self.compression = zipfile.ZIP_DEFLATED
        elif compression_method == "bzip2":
            self.compression = zipfile.ZIP_BZIP2
        elif compression_method == "lzma":
            self.compression = zipfile.ZIP_LZMA
        else:
            raise ValueError(
                f"Compression method {compression_method} is not supported!"
            )

        self.compression_level = compression_level
        super().__init__(**kwargs)

    @defaults_from_attrs(
        "source",
        "target_path",
    )
    def run(
        self,
        source: Union[str, Path, List[str], List[Path]] = "",
        target_path: Union[str, Path] = "",
    ):
        """
        Task run method.

        Args:
            - source (Union[str, Path, List[str], List[Path]], optional): a path or paths to compress
                into a single zip archive.
            - target_path (Union[str, Path], optional): path to the output archive file. Any parent
                directories of `target` must already exist.

        Returns:
            - None

        Raises:
            - ValueError: if source not set
            - ValueError: if target is not set
            - TypeError: if target is not a .zip file
        """

        self._check_path_is_set(source, "Source")
        self._check_path_is_set(target_path, "Target")

        if target_path.suffix != ".zip":
            raise TypeError("Archive name don't end with .zip.")
        else:
            target = Path(target_path)

        if not isinstance(source, list):
            source_path = [Path(source)]
        else:
            source_path = [Path(sp) for sp in source]

        if sys.version_info >= (3, 7):
            # compresslevel was added in 3.7
            zip_file = ZipFile(
                target,
                "w",
                compression=self.compression,
                compresslevel=self.compression_level,
            )
        else:
            zip_file = ZipFile(
                target,
                "w",
                compression=self.compression,
            )

        with zip_file as zip:
            self.logger.info(f"Creating zip archive {target}")
            for f in source_path:
                self.logger.info(f"Adding {f.name} to {target}")
                if f.is_file():
                    zip.write(f, arcname=f.name)
                else:
                    for root, dirs, files in os.walk(f):
                        for file in files:
                            fp = Path(root).joinpath(file)
                            zip.write(fp, arcname=fp.relative_to(f.parent))
