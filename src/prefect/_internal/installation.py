import importlib
import subprocess
import sys

import prefect
import prefect.utilities.processutils


def install_packages(
    packages: list[str], stream_output: bool = False, upgrade: bool = False
):
    """
    Install packages using uv if available, otherwise use pip.
    """
    constraint = f"prefect=={prefect.__version__}"
    base_command = ["pip", "install", constraint, *packages]
    if upgrade:
        base_command.append("--upgrade")
    if stream_output:
        stdout = sys.stdout
        stderr = sys.stderr
    else:
        stdout = subprocess.DEVNULL
        stderr = subprocess.DEVNULL
    try:
        uv = importlib.import_module("uv")

        command = [uv.find_uv_bin(), *base_command]
        subprocess.check_call(
            command,
            stdout=stdout,
            stderr=stderr,
        )
    except (ImportError, ModuleNotFoundError, FileNotFoundError):
        command = [sys.executable, "-m", *base_command]
        subprocess.check_call(
            command,
            stdout=stdout,
            stderr=stderr,
        )


async def ainstall_packages(
    packages: list[str], stream_output: bool = False, upgrade: bool = False
):
    """
    Install packages using uv if available, otherwise use pip.
    """
    constraint = f"prefect=={prefect.__version__}"
    base_command = ["pip", "install", constraint, *packages]
    if upgrade:
        base_command.append("--upgrade")
    try:
        uv = importlib.import_module("uv")

        await prefect.utilities.processutils.run_process(
            [uv.find_uv_bin(), *base_command], stream_output=stream_output
        )
    except (ImportError, ModuleNotFoundError, FileNotFoundError):
        await prefect.utilities.processutils.run_process(
            [sys.executable, "-m", *base_command],
            stream_output=stream_output,
        )
