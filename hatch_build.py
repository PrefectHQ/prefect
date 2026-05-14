from __future__ import annotations

import os
import textwrap
from datetime import datetime, timezone
from pathlib import Path
from subprocess import CalledProcessError, check_output
from typing import Any

try:
    from hatchling.builders.hooks.plugin.interface import BuildHookInterface
except ModuleNotFoundError:  # pragma: no cover - only used when testing helpers

    class BuildHookInterface:  # type: ignore[no-redef]
        root: str
        target_name: str


def _write_analytics_config(project_dir: Path) -> None:
    """Write analytics config with Amplitude API key from environment."""
    config_path = project_dir / "src/prefect/_internal/analytics/_config.py"
    api_key = os.environ.get("AMPLITUDE_API_KEY", "YOUR_AMPLITUDE_API_KEY_HERE")

    config_content = textwrap.dedent(f"""\
        # Generated at build time - DO NOT EDIT
        AMPLITUDE_API_KEY = "{api_key}"
    """)

    config_path.parent.mkdir(parents=True, exist_ok=True)
    with open(config_path, "w") as f:
        f.write(config_content)


def _write_build_info_py(project_dir: Path, package_version: str) -> None:
    path = project_dir / "src/prefect/_build_info.py"
    try:
        git_hash = check_output(
            ["git", "rev-parse", "HEAD"], cwd=project_dir
        ).decode().strip()
    except CalledProcessError:
        git_hash = "unknown"
    try:
        check_output(["git", "diff-index", "--quiet", "HEAD", "--"], cwd=project_dir)
        dirty = False
    except CalledProcessError:
        dirty = True

    build_dt_str = datetime.now(timezone.utc).isoformat()
    build_info = textwrap.dedent(
        f"""\
            # Generated at package build time - DO NOT EDIT
            __version__ = "{package_version}"
            __build_date__ = "{build_dt_str}"
            __git_commit__ = "{git_hash}"
            __dirty__ = {dirty}
            """
    )

    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        f.write(build_info)

    _write_analytics_config(project_dir)
PACKAGED_UI_INDEX_FILES = (
    Path("src/prefect/server/ui/index.html"),
    Path("src/prefect/server/ui-v2/index.html"),
)
REQUIRE_PACKAGED_UI_ENV_VAR = "PREFECT_REQUIRE_PACKAGED_UI_BUNDLES"


def _truthy_env_var(name: str) -> bool:
    return os.environ.get(name, "").lower() not in {"", "0", "false", "no", "off"}


def should_validate_packaged_ui_index_files(root: str | Path) -> bool:
    if _truthy_env_var(REQUIRE_PACKAGED_UI_ENV_VAR):
        return True

    root_path = Path(root)
    return any(
        (root_path / index_file.parent).exists()
        for index_file in PACKAGED_UI_INDEX_FILES
    )


def validate_packaged_ui_index_files(root: str | Path) -> None:
    root_path = Path(root)
    missing_index_files = [
        str(index_file)
        for index_file in PACKAGED_UI_INDEX_FILES
        if not (root_path / index_file).is_file()
    ]

    if missing_index_files:
        raise RuntimeError(
            "Prefect package builds require both UI bundles to be built. "
            "Missing index.html files: "
            f"{', '.join(missing_index_files)}"
        )


class CustomBuildHook(BuildHookInterface):
    def initialize(self, version: str, build_data: dict[str, Any]) -> None:
        if version != "editable" and self.target_name in {"sdist", "wheel"}:
            _write_build_info_py(Path(self.root), version)
        if (
            version != "editable"
            and self.target_name in {"sdist", "wheel"}
            and should_validate_packaged_ui_index_files(self.root)
        ):
            validate_packaged_ui_index_files(self.root)
