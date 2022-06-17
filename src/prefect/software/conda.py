import re

from prefect.software.base import Requirement

CONDA_REQUIREMENT = re.compile(
    r"^(?P<name>[0-9A-Za-z\-]+)"
    r"(?P<version_specifier>[>=<]+(?P<version>[0-9a-zA-Z\.]+))?"
    r"(?P<build_specifier>=(?P<build>[0-9A-Za-z\_]+))?$"
)


class CondaRequirement(Requirement):
    """
    A parsed requirement for installation with conda.
    """

    def __init__(self, requirement_string: str):
        self._requirement_string = requirement_string

        parsed = CONDA_REQUIREMENT.match(requirement_string)
        if parsed is None:
            raise ValueError(
                f"Invalid requirement {requirement_string!r}: could not be parsed."
            )
        self._parts = parsed.groupdict()

        self.name = self._parts["name"]
        self.version_specifier = self._parts["version_specifier"]
        self.version = self._parts["version"]
        self.build_specifier = self._parts["build_specifier"]
        self.build = self._parts["build"]

    def __str__(self) -> str:
        return self._requirement_string
