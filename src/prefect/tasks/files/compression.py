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

from prefect import Task
from prefect.utilities.tasks import defaults_from_attrs


class Unzip(Task):
    """
    Task for unzipping data.

    Args:
        - zip_path (Union[str, Path], optional): the path to the zip file
        - extract_dir (Union[str, Path], optional): directory to extract the zip file into.
            If not provided, the current working directory will be used. This directory must
            already exist.
        - **kwargs (dict, optional): additional keyword arguments to pass to the
            Task constructor
    """

    def __init__(
        self,
        zip_path: Union[str, Path] = "",
        extract_dir: Union[str, Path] = "",
        **kwargs: Any,
    ):
        self.zip_path = zip_path
        self.extract_dir = extract_dir
        super().__init__(**kwargs)

    @defaults_from_attrs(
        "zip_path",
        "extract_dir",
    )
    def run(
        self,
        zip_path: Union[str, Path] = "",
        extract_dir: Union[str, Path] = "",
        password: Union[bytes, str] = None,
    ) -> Path:
        """
        Task run method.

        Args:
            - zip_path (Union[str, Path], optional): the path to the zip file
            - extract_dir (Union[str, Path], optional): directory to extract the zip file into.
                If not provided, the current working directory will be used. This directory must
                already exist.
            - password (Union[bytes, str], optional): password for unzipping a password-protected
                zip file. If a `str`, will be utf-8 encoded.

        Returns:
            - Path: path to the extracted directory.
        """
        if not zip_path:
            raise ValueError("No `zip_path` provided")

        zip_path = Path(zip_path)
        extract_dir = Path(extract_dir or Path.cwd())

        if not zip_path.exists():
            raise ValueError(f"`zip_path` '{zip_path}' not found")

        if not zipfile.is_zipfile(zip_path):
            raise TypeError(f"`zip_path` '{zip_path}' is not a zip file")

        self.logger.info(f"Extracting '{zip_path}' to '{extract_dir}'")

        if password and isinstance(password, str):
            password = password.encode("utf-8")
        with ZipFile(zip_path, "r") as zip:
            zip.extractall(extract_dir, pwd=password)

        return extract_dir


class Zip(Task):
    """
    Task to create a zip archive.

    Args:
        - source_path (Union[str, Path, List[str], List[Path]], optional): path or paths to compress
             into a single zip archive.
        - zip_path (Union[str, Path], optional): path to the output archive file. Any parent
            directories of `zip_path` must already exist.
        - compression_method (str, optional): the compression method to use. Options are
            "deflate", "store", "bzip2", and "lzma". Defaults to `"deflate"`.
        - compression_level (int, optional): Compression level to use,
            see https://docs.python.org/3/library/zipfile.html#zipfile.ZipFile for more info.
            Python 3.7+ only.
        - **kwargs (dict, optional): additional keyword arguments to pass to the
            Task constructor.
    """

    def __init__(
        self,
        source_path: Union[str, Path, List[str], List[Path]] = "",
        zip_path: Union[str, Path] = "",
        compression_method: str = "deflate",
        compression_level: int = None,
        **kwargs: Any,
    ):
        self.source_path = source_path
        self.zip_path = zip_path

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
        "source_path",
        "zip_path",
    )
    def run(
        self,
        source_path: Union[str, Path, List[str], List[Path]] = "",
        zip_path: Union[str, Path] = "",
    ) -> None:
        """
        Task run method.

        Args:
            - source_path (Union[str, Path, List[str], List[Path]], optional): path or paths to compress
                into a single zip archive.
            - zip_path (Union[str, Path], optional): path to the output archive file. Any parent
                directories of `zip_path` must already exist.
        """

        if not source_path:
            raise ValueError("No `source_path` provided.")
        if not zip_path:
            raise ValueError("No `zip_path` provided.")

        zip_path = Path(zip_path)

        if not isinstance(source_path, list):
            source_path = [Path(source_path)]
        else:
            source_path = [Path(sp) for sp in source_path]

        if sys.version_info >= (3, 7):
            # compresslevel was added in 3.7
            zip_file = ZipFile(
                zip_path,
                "w",
                compression=self.compression,
                compresslevel=self.compression_level,
            )
        else:
            zip_file = ZipFile(
                zip_path,
                "w",
                compression=self.compression,
            )

        with zip_file:
            self.logger.info(f"Creating zip archive {zip_path}")
            for f in source_path:
                self.logger.info(f"Adding {f.name} to archive")
                if f.is_file():
                    zip_file.write(f, arcname=f.name)
                else:
                    for root, dirs, files in os.walk(f):
                        root_path = Path(root)
                        for file in files:
                            fp = root_path.joinpath(file)
                            zip_file.write(fp, arcname=fp.relative_to(f.parent))
