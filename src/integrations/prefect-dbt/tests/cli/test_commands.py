import os
from pathlib import Path
from unittest.mock import MagicMock

import pytest
import yaml
from prefect_dbt.cli.commands import DbtCoreOperation, trigger_dbt_cli_command
from prefect_dbt.cli.credentials import DbtCliProfile

from prefect import flow
from prefect.testing.utilities import AsyncMock


async def mock_shell_run_command_fn(**kwargs):
    return kwargs


@pytest.fixture(autouse=True)
def mock_shell_run_command(monkeypatch):
    _mock_shell_run_command = MagicMock(fn=mock_shell_run_command_fn)
    monkeypatch.setattr(
        "prefect_dbt.cli.commands.shell_run_command", _mock_shell_run_command
    )


@pytest.fixture
def profiles_dir(tmp_path):
    return tmp_path / ".dbt"


def test_trigger_dbt_cli_command_not_dbt():
    @flow
    def test_flow():
        return trigger_dbt_cli_command("ls")

    with pytest.raises(ValueError, match="Command is not a valid dbt sub-command"):
        test_flow()


def test_trigger_dbt_cli_command(profiles_dir, dbt_cli_profile_bare):
    @flow
    def test_flow():
        return trigger_dbt_cli_command(
            "dbt ls", profiles_dir=profiles_dir, dbt_cli_profile=dbt_cli_profile_bare
        )

    result = test_flow()
    assert result == {"command": f"dbt ls --profiles-dir {profiles_dir}"}


def test_trigger_dbt_cli_command_run_twice_overwrite(
    profiles_dir, dbt_cli_profile, dbt_cli_profile_bare
):
    @flow
    def test_flow():
        trigger_dbt_cli_command(
            "dbt ls", profiles_dir=profiles_dir, dbt_cli_profile=dbt_cli_profile
        )
        run_two = trigger_dbt_cli_command(
            "dbt ls",
            profiles_dir=profiles_dir,
            dbt_cli_profile=dbt_cli_profile_bare,
            overwrite_profiles=True,
        )
        return run_two

    result = test_flow()
    assert result == {"command": f"dbt ls --profiles-dir {profiles_dir}"}
    with open(profiles_dir / "profiles.yml", "r") as f:
        actual = yaml.safe_load(f)
    expected = {
        "config": {},
        "prefecto": {
            "target": "testing",
            "outputs": {
                "testing": {
                    "type": "custom",
                    "schema": "my_schema",
                    "threads": 4,
                    "account": "fake",
                }
            },
        },
    }
    assert actual == expected


def test_trigger_dbt_cli_command_run_twice_exists(
    profiles_dir, dbt_cli_profile, dbt_cli_profile_bare
):
    @flow
    def test_flow():
        trigger_dbt_cli_command(
            "dbt ls", profiles_dir=profiles_dir, dbt_cli_profile=dbt_cli_profile
        )
        run_two = trigger_dbt_cli_command(
            "dbt ls",
            profiles_dir=profiles_dir,
            dbt_cli_profile=dbt_cli_profile_bare,
        )
        return run_two

    with pytest.raises(ValueError, match="Since overwrite_profiles is False"):
        test_flow()


def test_trigger_dbt_cli_command_missing_profile(profiles_dir):
    @flow
    def test_flow():
        return trigger_dbt_cli_command(
            "dbt ls",
            profiles_dir=profiles_dir,
        )

    with pytest.raises(
        ValueError, match="Provide `dbt_cli_profile` keyword for writing profiles"
    ):
        test_flow()


def test_trigger_dbt_cli_command_find_home(dbt_cli_profile_bare):
    home_dbt_dir = Path.home() / ".dbt"
    if (home_dbt_dir / "profiles.yml").exists():
        dbt_cli_profile = None
    else:
        dbt_cli_profile = dbt_cli_profile_bare

    @flow
    def test_flow():
        return trigger_dbt_cli_command(
            "dbt ls", dbt_cli_profile=dbt_cli_profile, overwrite_profiles=False
        )

    result = test_flow()
    assert result == {"command": f"dbt ls --profiles-dir {home_dbt_dir}"}


def test_trigger_dbt_cli_command_find_env(profiles_dir, dbt_cli_profile_bare):
    @flow
    def test_flow():
        return trigger_dbt_cli_command("dbt ls", dbt_cli_profile=dbt_cli_profile_bare)

    os.environ["DBT_PROFILES_DIR"] = str(profiles_dir)
    result = test_flow()
    assert result == {"command": f"dbt ls --profiles-dir {profiles_dir}"}


def test_trigger_dbt_cli_command_project_dir(profiles_dir, dbt_cli_profile_bare):
    @flow
    def test_flow():
        return trigger_dbt_cli_command(
            "dbt ls",
            profiles_dir=profiles_dir,
            project_dir="project",
            dbt_cli_profile=dbt_cli_profile_bare,
        )

    result = test_flow()
    assert result == {
        "command": f"dbt ls --profiles-dir {profiles_dir} --project-dir project"
    }


def test_trigger_dbt_cli_command_shell_kwargs(profiles_dir, dbt_cli_profile_bare):
    @flow
    def test_flow():
        return trigger_dbt_cli_command(
            "dbt ls",
            return_all=True,
            profiles_dir=profiles_dir,
            dbt_cli_profile=dbt_cli_profile_bare,
        )

    result = test_flow()
    assert result == {
        "command": f"dbt ls --profiles-dir {profiles_dir}",
        "return_all": True,
    }


class TestDbtCoreOperation:
    @pytest.fixture
    def mock_open_process(self, monkeypatch):
        open_process = MagicMock(name="open_process")
        open_process.return_value = AsyncMock(name="returned open_process")
        monkeypatch.setattr("prefect_shell.commands.open_process", open_process)
        return open_process

    @pytest.fixture
    def mock_shell_process(self, monkeypatch):
        shell_process = MagicMock()
        opened_shell_process = AsyncMock()
        shell_process.return_value = opened_shell_process
        monkeypatch.setattr("prefect_shell.commands.ShellProcess", shell_process)
        return shell_process

    @pytest.fixture
    def dbt_cli_profile(self):
        return DbtCliProfile(
            name="my_name",
            target="my_target",
            target_configs={"type": "my_type", "threads": 4, "schema": "my_schema"},
        )

    def test_find_valid_profiles_dir_default_env(
        self, tmp_path, mock_open_process, mock_shell_process
    ):
        os.environ["DBT_PROFILES_DIR"] = str(tmp_path)
        (tmp_path / "profiles.yml").write_text("test")
        DbtCoreOperation(commands=["dbt debug"]).run()
        actual = str(mock_open_process.call_args_list[0][1]["env"]["DBT_PROFILES_DIR"])
        expected = str(tmp_path)
        assert actual == expected

    def test_find_valid_profiles_dir_input_env(
        self, tmp_path, mock_open_process, mock_shell_process
    ):
        (tmp_path / "profiles.yml").write_text("test")
        DbtCoreOperation(
            commands=["dbt debug"], env={"DBT_PROFILES_DIR": str(tmp_path)}
        ).run()
        actual = str(mock_open_process.call_args_list[0][1]["env"]["DBT_PROFILES_DIR"])
        expected = str(tmp_path)
        assert actual == expected

    def test_find_valid_profiles_dir_overwrite_without_profile(
        self, tmp_path, mock_open_process, mock_shell_process
    ):
        with pytest.raises(ValueError, match="Since overwrite_profiles is True"):
            DbtCoreOperation(
                commands=["dbt debug"], profiles_dir=tmp_path, overwrite_profiles=True
            ).run()

    def test_find_valid_profiles_dir_overwrite_with_profile(
        self, tmp_path, dbt_cli_profile, mock_open_process, mock_shell_process
    ):
        DbtCoreOperation(
            commands=["dbt debug"],
            profiles_dir=tmp_path,
            overwrite_profiles=True,
            dbt_cli_profile=dbt_cli_profile,
        ).run()
        assert (tmp_path / "profiles.yml").exists()

    def test_find_valid_profiles_dir_not_overwrite_with_profile(
        self, tmp_path, dbt_cli_profile, mock_open_process, mock_shell_process
    ):
        (tmp_path / "profiles.yml").write_text("test")
        with pytest.raises(ValueError, match="Since overwrite_profiles is False"):
            DbtCoreOperation(
                commands=["dbt debug"],
                profiles_dir=tmp_path,
                overwrite_profiles=False,
                dbt_cli_profile=dbt_cli_profile,
            ).run()

    def test_find_valid_profiles_dir_path_without_profile(self):
        with pytest.raises(ValueError, match="Since overwrite_profiles is True"):
            DbtCoreOperation(commands=["dbt debug"], profiles_dir=Path("fake")).run()

    def test_process_commands_not_dbt(self):
        with pytest.raises(ValueError, match="None of the commands"):
            assert DbtCoreOperation(commands=["ls"])

    def test_append_dirs_to_commands(
        self,
        tmp_path,
        dbt_cli_profile,
        mock_open_process,
        mock_shell_process,
        monkeypatch,
    ):
        mock_named_temporary_file = MagicMock(name="tempfile")
        monkeypatch.setattr("tempfile.NamedTemporaryFile", mock_named_temporary_file)
        try:
            with DbtCoreOperation(
                commands=["dbt debug"],
                profiles_dir=tmp_path,
                project_dir=tmp_path,
                dbt_cli_profile=dbt_cli_profile,
            ) as op:
                op.run()
        except (FileNotFoundError, TypeError):  # py37 raises TypeError
            pass  # we're mocking the tempfile; this is expected

        mock_write = mock_named_temporary_file.return_value.write
        assert (
            mock_write.call_args_list[0][0][0]
            == f"dbt debug --profiles-dir {tmp_path} --project-dir {tmp_path}".encode()
        )
