from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import TypeVar
from uuid import UUID

from pydantic import BaseModel

ModelT = TypeVar("ModelT", bound=BaseModel)


class WorkspaceSupervisorConfig(BaseModel):
    flow_run_id: UUID
    workspace_root: Path
    manifest_path: Path
    command: str | None = None


class PreparedWorkspaceManifest(BaseModel):
    working_directory: Path
    project_root: Path | None = None
    runtime_entrypoint: str
    hook_command: list[str] | None
    environment: dict[str, str]


def write_private_model(path: Path, model: BaseModel) -> None:
    """Atomically write a runtime model readable only by the current user."""
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_path = tempfile.mkstemp(
        dir=path.parent,
        prefix=f".{path.name}.",
    )
    try:
        if hasattr(os, "fchmod"):
            os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as file:
            descriptor = -1
            file.write(model.model_dump_json())
        os.replace(temporary_path, path)
    finally:
        if descriptor != -1:
            os.close(descriptor)
        try:
            os.unlink(temporary_path)
        except FileNotFoundError:
            pass


def read_model(path: Path, model: type[ModelT]) -> ModelT:
    return model.model_validate_json(path.read_text(encoding="utf-8"))
