import subprocess
import sys

from prefect.utilities.processutils import run_process


def install_packages(
    packages: list[str], stream_output: bool = False, upgrade: bool = False
):
    """
    Install packages using uv if available, otherwise use pip.
    """
    base_command = ["pip", "install", *packages]
    if upgrade:
        base_command.append("--upgrade")
    if stream_output:
        stdout = sys.stdout
        stderr = sys.stderr
    else:
        stdout = subprocess.DEVNULL
        stderr = subprocess.DEVNULL
    try:
        import uv

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
    base_command = ["pip", "install", *packages]
    if upgrade:
        base_command.append("--upgrade")
    try:
        import uv

        await run_process(
            [uv.find_uv_bin(), *base_command], stream_output=stream_output
        )
    except (ImportError, ModuleNotFoundError, FileNotFoundError):
        await run_process(
            [sys.executable, "-m", *base_command],
            stream_output=stream_output,
        )
