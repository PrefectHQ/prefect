import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import List
from unittest.mock import ANY, MagicMock

import anyio
import anyio.abc
import coolname
import pytest

import prefect
from prefect.flow_runners import SubprocessFlowRunner, base_flow_run_environment
from prefect.settings import SETTING_VARIABLES
from prefect.testing.utilities import AsyncMock


@pytest.fixture
def venv_environment_path(tmp_path):
    """
    Generates a temporary venv environment with development dependencies installed
    """

    environment_path = tmp_path / "test"

    # Create the virtual environment, include system site packages to avoid reinstalling
    # prefect which takes ~40 seconds instead of ~4 seconds.
    subprocess.check_output(
        [sys.executable, "-m", "venv", str(environment_path), "--system-site-packages"]
    )

    install_prefect_if_necessary(python=[str(environment_path / "bin" / "python")])

    return environment_path


@pytest.fixture
def virtualenv_environment_path(tmp_path):
    """
    Generates a temporary virtualenv environment with development dependencies installed
    """
    pytest.importorskip("virtualenv")

    environment_path = tmp_path / "test"

    # Create the virtual environment, include system site packages to avoid reinstalling
    # prefect which takes ~40 seconds instead of ~4 seconds.
    subprocess.check_output(
        ["virtualenv", str(environment_path), "--system-site-packages"]
    )

    install_prefect_if_necessary(python=[str(environment_path / "bin" / "python")])

    return environment_path


@pytest.fixture
def conda_environment_path(tmp_path):
    """
    Generates a temporary anaconda environment with development dependencies installed

    Will not be usable by `--name`, only `--prefix`.
    """
    if not shutil.which("conda"):
        pytest.skip("`conda` is not installed.")

    # Generate base creation command with the temporary path as the prefix for
    # automatic cleanup
    environment_path: Path = tmp_path / f"test-{coolname.generate_slug(2)}"
    create_env_command = [
        "conda",
        "create",
        "-y",
        "--prefix",
        str(environment_path),
    ]

    # Get the current conda environment so we can clone it for speedup
    current_conda_env = os.environ.get("CONDA_PREFIX")
    if current_conda_env:
        create_env_command.extend(["--clone", current_conda_env])

    else:
        # Otherwise, specify a matching python version up to `minor`
        # We cannot match up to `micro` because it is not always available in conda
        v = sys.version_info
        python_version = f"{v.major}.{v.minor}"
        create_env_command.append(f"python={python_version}")

    print(f"Creating conda environment at {environment_path}")
    subprocess.check_output(create_env_command)

    # Install prefect within the virtual environment
    # Developers using conda should have a matching environment from `--clone`.
    if not current_conda_env:

        # Link packages from the current installation instead of reinstalling
        conda_site_packages = (
            environment_path / "lib" / f"python{python_version}" / "site-packages"
        )
        local_site_packages = (
            Path(sys.prefix) / "lib" / f"python{python_version}" / "site-packages"
        )
        print(f"Linking packages from {local_site_packages} -> {conda_site_packages}")
        for local_pkg in local_site_packages.iterdir():
            conda_pkg = conda_site_packages / local_pkg.name
            if not conda_pkg.exists():
                conda_pkg.symlink_to(local_pkg, target_is_directory=local_pkg.is_dir())

        install_prefect_if_necessary(
            python=["conda", "run", "--prefix", str(environment_path), "python"]
        )

    return environment_path


def install_prefect_if_necessary(python: List[str]):
    version = None
    try:
        # Attempt to import `prefect`, which should be there via site-packages on
        # CI and systems where folks have installed an editable prefect globally
        version = subprocess.check_output(
            python + ["-c", "import prefect; print(prefect.__version__)"],
            stderr=subprocess.STDOUT,
        )
        version = version.decode().strip()
        print(f"Found `prefect` version {version!r} in environment")
    except subprocess.CalledProcessError as exc:
        if b"ModuleNotFoundError" in exc.stdout:
            print("`prefect` module not found in environment")
        else:
            raise

    if version == prefect.__version__:
        return

    # If it wasn't found or the version wasn't right, then --system-site-packages didn't
    # get us an installation of prefect so we'll need to do the slower version of
    # installing it into the virtual environment
    print(f"Installing `prefect` editably into environment")
    subprocess.check_output(
        python + ["-m", "pip", "install", "-e", f"{prefect.__root_path__}"]
    )


class TestSubprocessFlowRunner:
    def test_runner_type(self):
        assert SubprocessFlowRunner().typename == "subprocess"

    async def test_creates_subprocess_then_marks_as_started(
        self, monkeypatch, flow_run
    ):
        monkeypatch.setattr("anyio.open_process", AsyncMock())
        fake_status = MagicMock(spec=anyio.abc.TaskStatus)
        # By raising an exception when started is called we can assert the process
        # is opened before this time
        fake_status.started.side_effect = RuntimeError("Started called!")

        with pytest.raises(RuntimeError, match="Started called!"):
            await SubprocessFlowRunner().submit_flow_run(flow_run, fake_status)

        fake_status.started.assert_called_once()
        anyio.open_process.assert_awaited_once()

    async def test_creates_subprocess_with_current_python_executable(
        self, monkeypatch, flow_run
    ):
        monkeypatch.setattr(
            "anyio.open_process",
            # TODO: Consider more robust mocking for opened processes
            AsyncMock(side_effect=RuntimeError("Exit without streaming from process.")),
        )
        with pytest.raises(RuntimeError, match="Exit without streaming"):
            await SubprocessFlowRunner().submit_flow_run(flow_run, MagicMock())

        command = [sys.executable, "-m", "prefect.engine", flow_run.id.hex]
        if sys.platform == "win32":
            command = " ".join(command)
        anyio.open_process.assert_awaited_once_with(
            command,
            stderr=subprocess.STDOUT,
            env=ANY,
        )

    @pytest.mark.parametrize(
        "condaenv",
        ["test", Path("/test"), Path("~/test")],
        ids=["by name", "by abs path", "by home path"],
    )
    async def test_creates_subprocess_with_conda_command(
        self, monkeypatch, flow_run, condaenv
    ):
        monkeypatch.setattr(
            "anyio.open_process",
            # TODO: Consider more robust mocking for opened processes
            AsyncMock(side_effect=RuntimeError("Exit without streaming from process.")),
        )

        with pytest.raises(RuntimeError, match="Exit without streaming"):
            await SubprocessFlowRunner(condaenv=condaenv).submit_flow_run(
                flow_run, MagicMock()
            )

        name_or_prefix = (
            ["--name", condaenv]
            if not isinstance(condaenv, Path)
            else ["--prefix", str(condaenv.expanduser().resolve())]
        )

        command = [
            "conda",
            "run",
            *name_or_prefix,
            "python",
            "-m",
            "prefect.engine",
            flow_run.id.hex,
        ]
        if sys.platform == "win32":
            command = " ".join(command)
        anyio.open_process.assert_awaited_once_with(
            command,
            stderr=subprocess.STDOUT,
            env=ANY,
        )

    async def test_creates_subprocess_with_virtualenv_command_and_env(
        self, monkeypatch, flow_run
    ):
        # PYTHONHOME must be unset in the subprocess
        monkeypatch.setenv("PYTHONHOME", "FOO")

        monkeypatch.setattr(
            "anyio.open_process",
            # TODO: Consider more robust mocking for opened processes
            AsyncMock(side_effect=RuntimeError("Exit without streaming from process.")),
        )
        with pytest.raises(RuntimeError, match="Exit without streaming"):
            await SubprocessFlowRunner(virtualenv="~/fakevenv").submit_flow_run(
                flow_run, MagicMock()
            )

        # Replicate expected generation of virtual environment call
        virtualenv_path = Path("~/fakevenv").expanduser()
        python_executable = str(virtualenv_path / "bin" / "python")
        expected_env = {
            **base_flow_run_environment(),
            **{k: v for k, v in os.environ.items() if k not in SETTING_VARIABLES},
        }
        expected_env["PATH"] = (
            str(virtualenv_path / "bin") + os.pathsep + expected_env["PATH"]
        )
        expected_env.pop("PYTHONHOME")
        expected_env["VIRTUAL_ENV"] = str(virtualenv_path)

        command = [
            python_executable,
            "-m",
            "prefect.engine",
            flow_run.id.hex,
        ]
        if sys.platform == "win32":
            command = " ".join(command)
        anyio.open_process.assert_awaited_once_with(
            command,
            stderr=subprocess.STDOUT,
            env=expected_env,
        )

    async def test_executes_flow_run_with_system_python(
        self, python_executable_test_deployment, orion_client
    ):
        fake_status = MagicMock(spec=anyio.abc.TaskStatus)

        flow_run = await orion_client.create_flow_run_from_deployment(
            python_executable_test_deployment
        )

        print("In test process:", await orion_client.read_flow_runs())

        happy_exit = await SubprocessFlowRunner().submit_flow_run(flow_run, fake_status)

        assert happy_exit
        fake_status.started.assert_called_once()
        state = (await orion_client.read_flow_run(flow_run.id)).state
        runtime_python = await orion_client.resolve_datadoc(state.data)
        assert runtime_python == sys.executable

    @pytest.mark.service("environment")
    async def test_executes_flow_run_in_virtualenv(
        self,
        flow_run,
        orion_client,
        virtualenv_environment_path,
        python_executable_test_deployment,
    ):
        flow_run = await orion_client.create_flow_run_from_deployment(
            python_executable_test_deployment
        )

        happy_exit = await SubprocessFlowRunner(
            virtualenv=virtualenv_environment_path
        ).submit_flow_run(flow_run, MagicMock(spec=anyio.abc.TaskStatus))

        assert happy_exit
        state = (await orion_client.read_flow_run(flow_run.id)).state
        runtime_python = await orion_client.resolve_datadoc(state.result())
        assert runtime_python == str(virtualenv_environment_path / "bin" / "python")

    @pytest.mark.service("environment")
    async def test_executes_flow_run_in_venv(
        self,
        flow_run,
        orion_client,
        venv_environment_path,
        python_executable_test_deployment,
    ):
        flow_run = await orion_client.create_flow_run_from_deployment(
            python_executable_test_deployment
        )

        happy_exit = await SubprocessFlowRunner(
            virtualenv=venv_environment_path
        ).submit_flow_run(flow_run, MagicMock(spec=anyio.abc.TaskStatus))

        assert happy_exit
        state = (await orion_client.read_flow_run(flow_run.id)).state
        runtime_python = await orion_client.resolve_datadoc(state.result())
        assert runtime_python == str(venv_environment_path / "bin" / "python")

    @pytest.mark.service("environment")
    async def test_executes_flow_run_in_conda_environment(
        self,
        flow_run,
        orion_client,
        conda_environment_path,
        python_executable_test_deployment,
    ):
        flow_run = await orion_client.create_flow_run_from_deployment(
            python_executable_test_deployment
        )

        happy_exit = await SubprocessFlowRunner(
            condaenv=conda_environment_path,
            stream_output=True,
        ).submit_flow_run(flow_run, MagicMock(spec=anyio.abc.TaskStatus))

        assert happy_exit
        state = (await orion_client.read_flow_run(flow_run.id)).state
        runtime_python = await orion_client.resolve_datadoc(state.result())
        assert runtime_python == str(conda_environment_path / "bin" / "python")

    @pytest.mark.parametrize("stream_output", [True, False])
    async def test_stream_output_controls_local_printing(
        self, deployment, capsys, orion_client, stream_output
    ):
        flow_run = await orion_client.create_flow_run_from_deployment(deployment.id)

        assert await SubprocessFlowRunner(stream_output=stream_output).submit_flow_run(
            flow_run, MagicMock(spec=anyio.abc.TaskStatus)
        )

        output = capsys.readouterr()
        assert output.err == "", "stderr is never populated"

        if not stream_output:
            assert output.out == ""
        else:
            assert "Finished in state" in output.out, "Log from the engine is present"
            assert "\n\n" not in output.out, "Line endings are not double terminated"
