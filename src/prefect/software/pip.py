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


def _reduce_to_top_level_distributions(
    dists: Dict[str, pkg_resources.Distribution]
) -> Dict[str, pkg_resources.Distribution]:
    # Collect all child requirements
    child_requirement_names = {}
    for dist in dists:
        child_requirement_names.update(
            requirement.name for requirement in dist.requires()
        )

    return {dist for dist in dists if dist.project_name not in child_requirement_names}


def current_environment_requirements(
    exclude_nested: bool = False,
) -> List[PipRequirement]:
    dists = _get_installed_distributions()
    if exclude_nested:
        dists = _reduce_to_top_level_distributions(dists)
    return [PipRequirement.validate(dist.as_requirement()) for dist in dists.values()]
