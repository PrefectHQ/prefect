from pathlib import Path

import pytest

import prefect
import prefect.cli.dev
from prefect.testing.cli import invoke_and_assert

pytestmark = pytest.mark.clear_db


def _setup_ui_build_paths(monkeypatch, tmp_path: Path) -> tuple[Path, Path]:
    development_base_path = tmp_path / "repo"
    development_base_path.mkdir()
    (development_base_path / "pyproject.toml").write_text("", encoding="utf-8")

    for ui_dir in ("ui", "ui-v2"):
        dist_dir = development_base_path / ui_dir / "dist"
        dist_dir.mkdir(parents=True)
        (dist_dir / "index.html").write_text(ui_dir, encoding="utf-8")

    ui_static_path = tmp_path / "package" / "server" / "ui"
    ui_v2_static_path = tmp_path / "package" / "server" / "ui-v2"

    monkeypatch.setattr(prefect, "__development_base_path__", development_base_path)
    monkeypatch.setattr(prefect, "__ui_static_path__", ui_static_path)
    monkeypatch.setattr(prefect, "__ui_v2_static_path__", ui_v2_static_path)

    return ui_static_path, ui_v2_static_path


def test_dev_build_ui_builds_v1_bundle_by_default(monkeypatch, tmp_path):
    ui_static_path, ui_v2_static_path = _setup_ui_build_paths(monkeypatch, tmp_path)

    calls = []

    def mock_check_output(command, **kwargs):
        calls.append((Path.cwd().name, command, "env" in kwargs))

    monkeypatch.setattr(prefect.cli.dev.subprocess, "check_output", mock_check_output)

    invoke_and_assert(["dev", "build-ui"], expected_code=0)

    assert calls == [
        ("ui", ["npm", "ci"], False),
        ("ui", ["npm", "run", "build"], True),
    ]
    assert (ui_static_path / "index.html").read_text(encoding="utf-8") == "ui"
    assert not ui_v2_static_path.exists()


def test_dev_build_ui_include_v2_builds_both_bundles_without_install(
    monkeypatch, tmp_path
):
    ui_static_path, ui_v2_static_path = _setup_ui_build_paths(monkeypatch, tmp_path)

    calls = []

    def mock_check_output(command, **kwargs):
        calls.append((Path.cwd().name, command, "env" in kwargs))

    monkeypatch.setattr(prefect.cli.dev.subprocess, "check_output", mock_check_output)

    invoke_and_assert(
        ["dev", "build-ui", "--include-v2", "--no-install"], expected_code=0
    )

    assert calls == [
        ("ui", ["npm", "run", "build"], True),
        ("ui-v2", ["npm", "run", "build"], True),
    ]
    assert (ui_static_path / "index.html").read_text(encoding="utf-8") == "ui"
    assert (ui_v2_static_path / "index.html").read_text(encoding="utf-8") == "ui-v2"
