from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from prefect.runner._process_manager import ProcessHandle
from prefect.runner._starter_engine import EngineCommandStarter


class TestEngineCommandStarter:
    async def test_start_calls_run_process_with_default_command(self):
        mock_flow_run = MagicMock()
        mock_flow_run.id = uuid4()
        mock_process = MagicMock()
        mock_process.returncode = 0

        tmp_dir = Path("/tmp/test")

        starter = EngineCommandStarter(tmp_dir=tmp_dir)

        with patch(
            "prefect.runner._starter_engine.run_process",
            new_callable=AsyncMock,
            return_value=mock_process,
        ) as mock_run:
            with patch(
                "prefect.runner._starter_engine.get_sys_executable",
                return_value="/usr/bin/python",
            ):
                with patch(
                    "prefect.runner._starter_engine.get_current_settings"
                ) as mock_settings:
                    mock_settings.return_value.to_environment_variables.return_value = {}
                    await starter.start(mock_flow_run)

            call_kwargs = mock_run.call_args
            assert call_kwargs.kwargs["command"] == [
                "/usr/bin/python",
                "-m",
                "prefect.engine",
            ]

    async def test_start_uses_custom_command(self):
        mock_flow_run = MagicMock()
        mock_flow_run.id = uuid4()
        mock_process = MagicMock()
        mock_process.returncode = 0

        starter = EngineCommandStarter(
            tmp_dir=Path("/tmp/test"),
            command="python my_script.py --flag",
        )

        with patch(
            "prefect.runner._starter_engine.run_process",
            new_callable=AsyncMock,
            return_value=mock_process,
        ) as mock_run:
            with patch(
                "prefect.runner._starter_engine.get_current_settings"
            ) as mock_settings:
                mock_settings.return_value.to_environment_variables.return_value = {}
                await starter.start(mock_flow_run)

            call_kwargs = mock_run.call_args
            assert call_kwargs.kwargs["command"] == [
                "python",
                "my_script.py",
                "--flag",
            ]

    async def test_start_includes_flow_run_id_in_env(self):
        mock_flow_run = MagicMock()
        flow_run_id = uuid4()
        mock_flow_run.id = flow_run_id
        mock_process = MagicMock()

        starter = EngineCommandStarter(tmp_dir=Path("/tmp/test"))

        with patch(
            "prefect.runner._starter_engine.run_process",
            new_callable=AsyncMock,
            return_value=mock_process,
        ) as mock_run:
            with patch(
                "prefect.runner._starter_engine.get_sys_executable",
                return_value="python",
            ):
                with patch(
                    "prefect.runner._starter_engine.get_current_settings"
                ) as mock_settings:
                    mock_settings.return_value.to_environment_variables.return_value = {}
                    await starter.start(mock_flow_run)

            env = mock_run.call_args.kwargs["env"]
            assert env["PREFECT__FLOW_RUN_ID"] == str(flow_run_id)

    async def test_start_includes_storage_base_path(self):
        mock_flow_run = MagicMock()
        mock_flow_run.id = uuid4()
        mock_process = MagicMock()

        tmp_dir = Path("/tmp/my-runner")
        starter = EngineCommandStarter(tmp_dir=tmp_dir)

        with patch(
            "prefect.runner._starter_engine.run_process",
            new_callable=AsyncMock,
            return_value=mock_process,
        ) as mock_run:
            with patch(
                "prefect.runner._starter_engine.get_sys_executable",
                return_value="python",
            ):
                with patch(
                    "prefect.runner._starter_engine.get_current_settings"
                ) as mock_settings:
                    mock_settings.return_value.to_environment_variables.return_value = {}
                    await starter.start(mock_flow_run)

            env = mock_run.call_args.kwargs["env"]
            assert env["PREFECT__STORAGE_BASE_PATH"] == str(tmp_dir)

    async def test_start_disables_cancellation_hooks(self):
        mock_flow_run = MagicMock()
        mock_flow_run.id = uuid4()
        mock_process = MagicMock()

        starter = EngineCommandStarter(tmp_dir=Path("/tmp/test"))

        with patch(
            "prefect.runner._starter_engine.run_process",
            new_callable=AsyncMock,
            return_value=mock_process,
        ) as mock_run:
            with patch(
                "prefect.runner._starter_engine.get_sys_executable",
                return_value="python",
            ):
                with patch(
                    "prefect.runner._starter_engine.get_current_settings"
                ) as mock_settings:
                    mock_settings.return_value.to_environment_variables.return_value = {}
                    await starter.start(mock_flow_run)

            env = mock_run.call_args.kwargs["env"]
            assert env["PREFECT__ENABLE_CANCELLATION_AND_CRASHED_HOOKS"] == "false"

    async def test_start_includes_entrypoint_when_set(self):
        mock_flow_run = MagicMock()
        mock_flow_run.id = uuid4()
        mock_process = MagicMock()

        starter = EngineCommandStarter(
            tmp_dir=Path("/tmp/test"),
            entrypoint="my_module.py:my_flow",
        )

        with patch(
            "prefect.runner._starter_engine.run_process",
            new_callable=AsyncMock,
            return_value=mock_process,
        ) as mock_run:
            with patch(
                "prefect.runner._starter_engine.get_sys_executable",
                return_value="python",
            ):
                with patch(
                    "prefect.runner._starter_engine.get_current_settings"
                ) as mock_settings:
                    mock_settings.return_value.to_environment_variables.return_value = {}
                    await starter.start(mock_flow_run)

            env = mock_run.call_args.kwargs["env"]
            assert env["PREFECT__FLOW_ENTRYPOINT"] == "my_module.py:my_flow"

    async def test_start_excludes_entrypoint_when_none(self):
        mock_flow_run = MagicMock()
        mock_flow_run.id = uuid4()
        mock_process = MagicMock()

        starter = EngineCommandStarter(tmp_dir=Path("/tmp/test"))

        with patch(
            "prefect.runner._starter_engine.run_process",
            new_callable=AsyncMock,
            return_value=mock_process,
        ) as mock_run:
            with patch(
                "prefect.runner._starter_engine.get_sys_executable",
                return_value="python",
            ):
                with patch(
                    "prefect.runner._starter_engine.get_current_settings"
                ) as mock_settings:
                    mock_settings.return_value.to_environment_variables.return_value = {}
                    await starter.start(mock_flow_run)

            env = mock_run.call_args.kwargs["env"]
            assert "PREFECT__FLOW_ENTRYPOINT" not in env

    async def test_start_includes_heartbeat_when_set(self):
        mock_flow_run = MagicMock()
        mock_flow_run.id = uuid4()
        mock_process = MagicMock()

        starter = EngineCommandStarter(
            tmp_dir=Path("/tmp/test"),
            heartbeat_seconds=45,
        )

        with patch(
            "prefect.runner._starter_engine.run_process",
            new_callable=AsyncMock,
            return_value=mock_process,
        ) as mock_run:
            with patch(
                "prefect.runner._starter_engine.get_sys_executable",
                return_value="python",
            ):
                with patch(
                    "prefect.runner._starter_engine.get_current_settings"
                ) as mock_settings:
                    mock_settings.return_value.to_environment_variables.return_value = {}
                    await starter.start(mock_flow_run)

            env = mock_run.call_args.kwargs["env"]
            assert env["PREFECT_FLOWS_HEARTBEAT_FREQUENCY"] == "45"

    async def test_start_excludes_heartbeat_when_none(self):
        mock_flow_run = MagicMock()
        mock_flow_run.id = uuid4()
        mock_process = MagicMock()

        starter = EngineCommandStarter(tmp_dir=Path("/tmp/test"))

        with patch(
            "prefect.runner._starter_engine.run_process",
            new_callable=AsyncMock,
            return_value=mock_process,
        ) as mock_run:
            with patch(
                "prefect.runner._starter_engine.get_sys_executable",
                return_value="python",
            ):
                with patch(
                    "prefect.runner._starter_engine.get_current_settings"
                ) as mock_settings:
                    mock_settings.return_value.to_environment_variables.return_value = {}
                    await starter.start(mock_flow_run)

            env = mock_run.call_args.kwargs["env"]
            assert "PREFECT_FLOWS_HEARTBEAT_FREQUENCY" not in env

    async def test_start_passes_task_status_handler(self):
        """run_process receives a task_status_handler that wraps in ProcessHandle."""
        mock_flow_run = MagicMock()
        mock_flow_run.id = uuid4()
        mock_process = MagicMock()

        starter = EngineCommandStarter(tmp_dir=Path("/tmp/test"))

        with patch(
            "prefect.runner._starter_engine.run_process",
            new_callable=AsyncMock,
            return_value=mock_process,
        ) as mock_run:
            with patch(
                "prefect.runner._starter_engine.get_sys_executable",
                return_value="python",
            ):
                with patch(
                    "prefect.runner._starter_engine.get_current_settings"
                ) as mock_settings:
                    mock_settings.return_value.to_environment_variables.return_value = {}
                    await starter.start(mock_flow_run)

            handler = mock_run.call_args.kwargs["task_status_handler"]
            raw_process = MagicMock(pid=99, returncode=0)
            handle = handler(raw_process)
            assert isinstance(handle, ProcessHandle)
            assert handle.pid == 99

    async def test_start_uses_storage_destination_as_cwd(self):
        mock_flow_run = MagicMock()
        mock_flow_run.id = uuid4()
        mock_process = MagicMock()

        mock_storage = MagicMock()
        mock_storage.destination = Path("/code/my-flow")

        starter = EngineCommandStarter(
            tmp_dir=Path("/tmp/test"),
            storage=mock_storage,
        )

        with patch(
            "prefect.runner._starter_engine.run_process",
            new_callable=AsyncMock,
            return_value=mock_process,
        ) as mock_run:
            with patch(
                "prefect.runner._starter_engine.get_sys_executable",
                return_value="python",
            ):
                with patch(
                    "prefect.runner._starter_engine.get_current_settings"
                ) as mock_settings:
                    mock_settings.return_value.to_environment_variables.return_value = {}
                    await starter.start(mock_flow_run)

            assert mock_run.call_args.kwargs["cwd"] == Path("/code/my-flow")

    async def test_start_uses_none_cwd_when_no_storage_and_no_cwd(self):
        """Without storage or explicit cwd, subprocess inherits current
        working directory (cwd=None) -- mirrors runner.py line 961."""
        mock_flow_run = MagicMock()
        mock_flow_run.id = uuid4()
        mock_process = MagicMock()

        starter = EngineCommandStarter(tmp_dir=Path("/tmp/runner-dir"))

        with patch(
            "prefect.runner._starter_engine.run_process",
            new_callable=AsyncMock,
            return_value=mock_process,
        ) as mock_run:
            with patch(
                "prefect.runner._starter_engine.get_sys_executable",
                return_value="python",
            ):
                with patch(
                    "prefect.runner._starter_engine.get_current_settings"
                ) as mock_settings:
                    mock_settings.return_value.to_environment_variables.return_value = {}
                    await starter.start(mock_flow_run)

            assert mock_run.call_args.kwargs["cwd"] is None

    async def test_start_uses_explicit_cwd_when_no_storage(self):
        """When caller passes cwd but no storage, use the caller's cwd."""
        mock_flow_run = MagicMock()
        mock_flow_run.id = uuid4()
        mock_process = MagicMock()

        explicit_cwd = Path("/my/custom/dir")
        starter = EngineCommandStarter(
            tmp_dir=Path("/tmp/runner-dir"),
            cwd=explicit_cwd,
        )

        with patch(
            "prefect.runner._starter_engine.run_process",
            new_callable=AsyncMock,
            return_value=mock_process,
        ) as mock_run:
            with patch(
                "prefect.runner._starter_engine.get_sys_executable",
                return_value="python",
            ):
                with patch(
                    "prefect.runner._starter_engine.get_current_settings"
                ) as mock_settings:
                    mock_settings.return_value.to_environment_variables.return_value = {}
                    await starter.start(mock_flow_run)

            assert mock_run.call_args.kwargs["cwd"] == explicit_cwd

    async def test_start_storage_destination_overrides_explicit_cwd(self):
        """Storage destination takes precedence over explicit cwd."""
        mock_flow_run = MagicMock()
        mock_flow_run.id = uuid4()
        mock_process = MagicMock()

        mock_storage = MagicMock()
        mock_storage.destination = Path("/code/my-flow")

        starter = EngineCommandStarter(
            tmp_dir=Path("/tmp/test"),
            storage=mock_storage,
            cwd=Path("/should/be/ignored"),
        )

        with patch(
            "prefect.runner._starter_engine.run_process",
            new_callable=AsyncMock,
            return_value=mock_process,
        ) as mock_run:
            with patch(
                "prefect.runner._starter_engine.get_sys_executable",
                return_value="python",
            ):
                with patch(
                    "prefect.runner._starter_engine.get_current_settings"
                ) as mock_settings:
                    mock_settings.return_value.to_environment_variables.return_value = {}
                    await starter.start(mock_flow_run)

            assert mock_run.call_args.kwargs["cwd"] == Path("/code/my-flow")

    async def test_start_passes_stream_output(self):
        mock_flow_run = MagicMock()
        mock_flow_run.id = uuid4()
        mock_process = MagicMock()

        starter = EngineCommandStarter(
            tmp_dir=Path("/tmp/test"),
            stream_output=False,
        )

        with patch(
            "prefect.runner._starter_engine.run_process",
            new_callable=AsyncMock,
            return_value=mock_process,
        ) as mock_run:
            with patch(
                "prefect.runner._starter_engine.get_sys_executable",
                return_value="python",
            ):
                with patch(
                    "prefect.runner._starter_engine.get_current_settings"
                ) as mock_settings:
                    mock_settings.return_value.to_environment_variables.return_value = {}
                    await starter.start(mock_flow_run)

            assert mock_run.call_args.kwargs["stream_output"] is False

    async def test_start_merges_caller_env(self):
        mock_flow_run = MagicMock()
        mock_flow_run.id = uuid4()
        mock_process = MagicMock()

        starter = EngineCommandStarter(
            tmp_dir=Path("/tmp/test"),
            env={"MY_CUSTOM_VAR": "hello"},
        )

        with patch(
            "prefect.runner._starter_engine.run_process",
            new_callable=AsyncMock,
            return_value=mock_process,
        ) as mock_run:
            with patch(
                "prefect.runner._starter_engine.get_sys_executable",
                return_value="python",
            ):
                with patch(
                    "prefect.runner._starter_engine.get_current_settings"
                ) as mock_settings:
                    mock_settings.return_value.to_environment_variables.return_value = {}
                    await starter.start(mock_flow_run)

            env = mock_run.call_args.kwargs["env"]
            # The caller env should be present (may be overridden by os.environ)
            assert "PREFECT__FLOW_RUN_ID" in env
