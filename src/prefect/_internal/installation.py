import importlib
import subprocess
import sys
import warnings

import prefect.utilities.processutils

_DEPRECATION_WARNING_EMITTED = False


def _emit_pip_fallback_warning():
    """Emit a deprecation warning when falling back to pip because uv is not available."""
    global _DEPRECATION_WARNING_EMITTED
    if _DEPRECATION_WARNING_EMITTED:
        return
    _DEPRECATION_WARNING_EMITTED = True
    warnings.warn(
        "The 'uv' package is not installed. Falling back to pip for package "
        "installation. In a future version of Prefect, you will need to install "
        "'prefect[uv]' to use uv-powered features. "
        "Install with: pip install 'prefect[uv]'",
        DeprecationWarning,
        stacklevel=4,
    )


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
        uv = importlib.import_module("uv")

        command = [uv.find_uv_bin(), *base_command]
        subprocess.check_call(
            command,
            stdout=stdout,
            stderr=stderr,
        )
    except (ImportError, ModuleNotFoundError, FileNotFoundError):
        _emit_pip_fallback_warning()
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
        uv = importlib.import_module("uv")

        await prefect.utilities.processutils.run_process(
            [uv.find_uv_bin(), *base_command], stream_output=stream_output
        )
    except (ImportError, ModuleNotFoundError, FileNotFoundError):
        _emit_pip_fallback_warning()
        await prefect.utilities.processutils.run_process(
            [sys.executable, "-m", *base_command],
            stream_output=stream_output,
        )
