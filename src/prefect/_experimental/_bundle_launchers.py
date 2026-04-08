from __future__ import annotations

from copy import deepcopy
from typing import Any, TypedDict

from typing_extensions import Literal, TypeAlias

BundleLauncherSide = Literal["upload", "execution"]


class BundleLauncherOverride(TypedDict, total=False):
    upload: list[str]
    execution: list[str]


BundleLauncher: TypeAlias = list[str] | BundleLauncherOverride


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


def normalize_bundle_launcher(
    bundle_launcher: BundleLauncher | None,
) -> BundleLauncherOverride | None:
    if bundle_launcher is None:
        return None

    if isinstance(bundle_launcher, list):
        launcher = validate_bundle_step_launcher(
            bundle_launcher, field_name="bundle_launcher"
        )
        return {"upload": launcher.copy(), "execution": launcher.copy()}

    if not isinstance(bundle_launcher, dict):
        raise TypeError(
            "bundle_launcher must be a list[str] or a mapping with "
            "'upload'/'execution' keys"
        )

    allowed_keys = {"upload", "execution"}
    invalid_keys = sorted(set(bundle_launcher) - allowed_keys)
    if invalid_keys:
        raise ValueError(
            "bundle_launcher may only specify 'upload' and 'execution'; got "
            f"{invalid_keys!r}"
        )

    if not bundle_launcher:
        raise ValueError(
            "bundle_launcher must specify at least one of 'upload' or 'execution'"
        )

    normalized: BundleLauncherOverride = {}
    for side in ("upload", "execution"):
        if side in bundle_launcher:
            normalized[side] = validate_bundle_step_launcher(
                bundle_launcher[side],
                field_name=f"bundle_launcher[{side!r}]",
            )

    return normalized


def get_bundle_launcher_for_side(
    bundle_launcher: BundleLauncher | None,
    side: BundleLauncherSide,
) -> list[str] | None:
    normalized = normalize_bundle_launcher(bundle_launcher)
    if normalized is None:
        return None

    launcher = normalized.get(side)
    return launcher.copy() if launcher is not None else None


def resolve_bundle_step_with_launcher(
    step: dict[str, Any],
    bundle_launcher: BundleLauncher | None,
    side: BundleLauncherSide,
) -> dict[str, Any]:
    resolved_step = deepcopy(step)
    launcher = get_bundle_launcher_for_side(bundle_launcher, side)

    if launcher is None:
        return resolved_step

    step_keys = list(resolved_step.keys())
    if len(step_keys) != 1:
        return resolved_step

    function_args = resolved_step[step_keys[0]]
    if not isinstance(function_args, dict):
        return resolved_step

    function_args["launcher"] = launcher
    function_args.pop("requires", None)

    return resolved_step
