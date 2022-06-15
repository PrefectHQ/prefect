from typing import Dict, List

import packaging.requirements
import packaging.version
import pkg_resources


class PipRequirement(packaging.requirements.Requirement):
    """
    A parsed Python requirement.

    An extension for `packaging.version.Requirement` with Pydantic support.
    """

    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, value):
        if not isinstance(value, cls):
            # Attempt to parse the string representation of the input type
            return cls(str(value))
        return value

    def __eq__(self, __o: object) -> bool:
        """
        Requirements are equal if their string specification matches.
        """
        if not isinstance(__o, PipRequirement):
            raise NotImplementedError()

        return str(self) == str(__o)


def _get_installed_distributions() -> Dict[str, pkg_resources.Distribution]:
    return {dist.project_name: dist for dist in pkg_resources.working_set}


def _remove_distributions_required_by_others(
    dists: Dict[str, pkg_resources.Distribution]
) -> Dict[str, pkg_resources.Distribution]:
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
) -> List[PipRequirement]:
    dists = _get_installed_distributions()
    if exclude_nested:
        dists = _remove_distributions_required_by_others(dists)
    return [PipRequirement.validate(dist.as_requirement()) for dist in dists.values()]
