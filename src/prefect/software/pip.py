import warnings
from typing import TYPE_CHECKING, Dict, List, Type

import packaging.requirements
import packaging.version
from typing_extensions import Literal, Self

from prefect.software.base import Requirement
from prefect.utilities.importtools import lazy_import

if TYPE_CHECKING:
    import pkg_resources
else:
    pkg_resources = lazy_import("pkg_resources")


class PipRequirement(Requirement, packaging.requirements.Requirement):
    """
    A parsed Python requirement.

    An extension for `packaging.version.Requirement` with Pydantic support.
    """

    @classmethod
    def from_distribution(cls: Type[Self], dist: "pkg_resources.Distribution") -> Self:
        """
        Convert a Python distribution object into a requirement
        """
        if not dist.location.endswith("site-packages"):
            raise ValueError(
                f"Distribution {dist!r} is an editable installation and cannot be "
                "used as a requirement."
            )
        return cls.validate(dist.as_requirement())


def _get_installed_distributions() -> Dict[str, "pkg_resources.Distribution"]:
    return {dist.project_name: dist for dist in pkg_resources.working_set}


def _remove_distributions_required_by_others(
    dists: Dict[str, "pkg_resources.Distribution"]
) -> Dict[str, "pkg_resources.Distribution"]:
    # Collect all child requirements
    child_requirement_names = set()
    for dist in dists.values():
        child_requirement_names.update(
            {requirement.name for requirement in dist.requires()}
        )

    return {
        name: dist
        for name, dist in dists.items()
        if name not in child_requirement_names
    }


def current_environment_requirements(
    exclude_nested: bool = False,
    on_uninstallable_requirement: Literal["ignore", "warn", "raise"] = "warn",
) -> List[PipRequirement]:
    dists = _get_installed_distributions()
    if exclude_nested:
        dists = _remove_distributions_required_by_others(dists)

    requirements = []
    uninstallable_msgs = []
    for dist in dists.values():
        if not dist.location.endswith("site-packages"):
            uninstallable_msgs.append(
                f"- {dist.project_name}: This distribution is located at "
                f"{dist.location!r}, it looks like an editable installation."
            )
        else:
            requirements.append(PipRequirement.from_distribution(dist))

    if uninstallable_msgs:
        message = (
            "The following requirements will not be installable on another machine:\n"
            + "\n".join(uninstallable_msgs)
        )
        if on_uninstallable_requirement == "ignore":
            pass
        elif on_uninstallable_requirement == "warn":
            # When warning, include a note that these distributions are excluded
            warnings.warn(message + "\nThese requirements will be ignored.")
        elif on_uninstallable_requirement == "raise":
            raise ValueError(message)
        else:
            raise ValueError(
                "Unknown mode for `on_uninstallable_requirement`: "
                f"{on_uninstallable_requirement!r}. "
                "Expected one of: 'ignore', 'warn', 'raise'."
            )

    return requirements
