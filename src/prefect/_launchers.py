from __future__ import annotations

from copy import deepcopy
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from prefect.bundles import (
        BundleLauncher,
        BundleLauncherOverride,
        BundleLauncherSide,
    )


def validate_bundle_step_launcher(
    launcher: Any, *, field_name: str = "launcher"
) -> list[str]:
    if not isinstance(launcher, list) or not launcher:
        raise ValueError(f"{field_name} must be a non-empty list[str]")

    normalized: list[str] = []
    for i, item in enumerate(launcher):
        if not isinstance(item, str) or not item.strip():
            raise ValueError(f"{field_name}[{i}] must be a non-empty string")
        normalized.append(item)

    return normalized


def normalize_launcher(
    launcher: BundleLauncher | None,
) -> BundleLauncherOverride | None:
    if launcher is None:
        return None

    if isinstance(launcher, list):
        normalized_launcher = validate_bundle_step_launcher(
            launcher, field_name="launcher"
        )
        return {
            "upload": normalized_launcher.copy(),
            "execution": normalized_launcher.copy(),
        }

    if not isinstance(launcher, dict):
        raise TypeError(
            "launcher must be a list[str] or a mapping with 'upload'/'execution' keys"
        )

    allowed_keys = {"upload", "execution"}
    invalid_keys = sorted(set(launcher) - allowed_keys)
    if invalid_keys:
        raise ValueError(
            f"launcher may only specify 'upload' and 'execution'; got {invalid_keys!r}"
        )

    if not launcher:
        raise ValueError(
            "launcher must specify at least one of 'upload' or 'execution'"
        )

    normalized: BundleLauncherOverride = {}
    for side in ("upload", "execution"):
        if side in launcher:
            normalized[side] = validate_bundle_step_launcher(
                launcher[side],
                field_name=f"launcher[{side!r}]",
            )

    return normalized


def get_launcher_for_side(
    launcher: BundleLauncher | None,
    side: BundleLauncherSide,
) -> list[str] | None:
    normalized = normalize_launcher(launcher)
    if normalized is None:
        return None

    launcher = normalized.get(side)
    return launcher.copy() if launcher is not None else None


def resolve_bundle_step_with_launcher(
    step: dict[str, Any],
    launcher: BundleLauncher | None,
    side: BundleLauncherSide,
) -> dict[str, Any]:
    resolved_step = deepcopy(step)
    resolved_launcher = get_launcher_for_side(launcher, side)

    if resolved_launcher is None:
        return resolved_step

    step_keys = list(resolved_step.keys())
    if len(step_keys) != 1:
        return resolved_step

    function_args = resolved_step[step_keys[0]]
    if not isinstance(function_args, dict):
        return resolved_step

    function_args["launcher"] = resolved_launcher
    function_args.pop("requires", None)

    return resolved_step
