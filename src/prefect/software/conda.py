import json
import re
import subprocess
from typing import List

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


class CondaError(RuntimeError):
    """
    Raised if an error occurs in conda.
    """


def current_environment_conda_requirements(
    include_builds: bool = False, explicit_only: bool = True
) -> List[CondaRequirement]:
    """
    Return conda requirements by exporting the current environment.
    """
    command = ["conda", "env", "export", "--json"]

    if not include_builds:
        command.append("--no-builds")
    if explicit_only:
        command.append("--from-history")

    process = subprocess.run(command, capture_output=True)
    parsed = json.loads(process.stdout)
    if "error" in parsed:
        raise CondaError(
            "Encountered an exception while exporting the conda environment: "
            + parsed["error"]
        )

    # If no dependencies are given, this field will not be present
    dependencies = parsed.get("dependencies", [])

    # The string check will exclude nested objects like the 'pip' subtree
    return [CondaRequirement(dep) for dep in dependencies if isinstance(dep, str)]
