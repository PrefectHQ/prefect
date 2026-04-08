from __future__ import annotations

from typing import TypedDict

from typing_extensions import Literal, TypeAlias

BundleLauncherSide = Literal["upload", "execution"]


class BundleLauncherOverride(TypedDict, total=False):
    upload: list[str]
    execution: list[str]


BundleLauncher: TypeAlias = list[str] | BundleLauncherOverride
