from __future__ import annotations

import os
from pathlib import Path
from typing import Any

try:
    from hatchling.builders.hooks.plugin.interface import BuildHookInterface
except ModuleNotFoundError:  # pragma: no cover - only used when testing helpers

    class BuildHookInterface:  # type: ignore[no-redef]
        root: str
        target_name: str


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
        if (
            version != "editable"
            and self.target_name in {"sdist", "wheel"}
            and should_validate_packaged_ui_index_files(self.root)
        ):
            validate_packaged_ui_index_files(self.root)
