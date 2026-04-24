from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def write_marker(filename: str) -> dict[str, str]:
    marker = Path(filename)
    marker.write_text(str(Path.cwd()))
    return {"marker": str(marker.resolve())}


def change_directory(directory: str) -> dict[str, str]:
    os.chdir(directory)
    return {}


def make_directory_and_change_directory(
    directory: str, return_directory: str | None = None
) -> dict[str, str]:
    Path(directory).mkdir(parents=True, exist_ok=True)
    os.chdir(directory)
    if return_directory is None:
        return {}
    return {"directory": return_directory}


def emit_inherited_stdout(message: str) -> dict[str, str]:
    subprocess.run(
        [sys.executable, "-c", f"print({message!r})"],
        check=True,
    )
    return {}


def set_environment_variable(name: str, value: str) -> dict[str, str]:
    os.environ[name] = value
    return {}


def prepend_to_sys_path(path: str) -> dict[str, str]:
    sys.path.insert(0, str(Path(path).resolve()))
    return {}


def remove_current_directory(return_directory: str | None = None) -> dict[str, str]:
    current_directory = Path.cwd()

    if return_directory is not None:
        Path(return_directory).mkdir(parents=True, exist_ok=True)

    subprocess.run(
        [
            sys.executable,
            "-c",
            "import shutil, sys; shutil.rmtree(sys.argv[1])",
            str(current_directory),
        ],
        cwd=current_directory.parent,
        check=True,
    )

    if return_directory is None:
        return {}
    return {"directory": return_directory}


def raise_error(message: str) -> dict[str, str]:
    raise RuntimeError(message)
