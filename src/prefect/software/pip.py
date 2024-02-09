import site
import warnings
from pathlib import Path
from typing import Dict, List, Type, Union

import packaging.requirements
import packaging.version
from typing_extensions import Literal, Self

from prefect.software.base import Requirement
from prefect.utilities.compat import importlib_metadata


class PipRequirement(Requirement, packaging.requirements.Requirement):
    """
    A parsed Python requirement.

    An extension for `packaging.version.Requirement` with Pydantic support.
    """

    @classmethod
    def from_distribution(
        cls: Type[Self], dist: "importlib_metadata.Distribution"
    ) -> Self:
        """
        Convert a Python distribution object into a requirement
        """
        if _is_editable_install(dist):
            raise ValueError(
                f"Distribution {dist!r} is an editable installation and cannot be "
                "used as a requirement."
            )

        return cls.validate(
            packaging.requirements.Requirement(
                f"{dist.metadata['name']}=={dist.version}"
            )
        )


def _get_installed_distributions() -> Dict[str, "importlib_metadata.Distribution"]:
    return {dist.name: dist for dist in importlib_metadata.distributions()}


def _is_child_path(path: Union[Path, str], parent: Union[Path, str]) -> bool:
    return Path(parent).resolve() in Path(path).resolve().parents


def _is_same_path(path: Union[Path, str], other: Union[Path, str]) -> bool:
    return Path(path).resolve() == Path(other).resolve()


def _is_editable_install(dist: "importlib_metadata.Distribution") -> bool:
    """
    Determine if a distribution is an 'editable' install by scanning if it is present
    in a site-packages directory or not; if not, we presume it is editable.
    """
    site_packages = site.getsitepackages() + [site.getusersitepackages()]

    dist_location = dist.locate_file("")
    for site_package_dir in site_packages:
        if _is_same_path(dist_location, site_package_dir) or _is_child_path(
            dist_location, site_package_dir
        ):
            return False

    return True


def _remove_distributions_required_by_others(
    dists: Dict[str, "importlib_metadata.Distribution"],
) -> Dict[str, "importlib_metadata.Distribution"]:
    # Collect all child requirements
    child_requirement_names = set()
    for dist in dists.values():
        child_requirement_names.update(dist.requires or [])

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
        if _is_editable_install(dist):
            uninstallable_msgs.append(
                f"- {dist.name}: This distribution is an editable installation."
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
