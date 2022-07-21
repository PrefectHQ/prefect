import json
import re
import subprocess
import sys
from pathlib import Path
from typing import List, Type

import yaml
from pydantic import Field, validate_arguments
from typing_extensions import Self

from prefect.software.base import (
    Requirement,
    pop_requirement_by_name,
    remove_duplicate_requirements,
)
from prefect.software.pip import current_environment_requirements
from prefect.software.python import PythonEnvironment
from prefect.utilities.collections import listrepr

# Capture each component of a conda requirement string.
#
#   <name><version_specifier><version><build_specifier><build>
#
# The specification of these requirements is more relaxed than pip requirements.
# Notably, the version specifier is typically a single equal sign and a build can be
# included after the version.
#
# For example, the requirement "requests=2.25.1=pyhd3eb1b0_0" matches as:
#   name: "requests"
#   version_specifier: "="
#   version: "2.25.1"
#   build_specifier: "="
#   build: "pyhd3eb1b0_0"
#
# Regex components:
#   name (required): any combination of numbers, letters, or dashes
#   version_specifier (optional): one or more of `>`, `<`, and `=`
#   version (optional): any combination of numbers, letters, or periods; not valid
#       unless grouped with a version specifier.
#   build_specifier (optional): just `=`.
#   build (optional): any combination of numbers, letters, or underscores; not valid
#       unless grouped with a build specifier.

CONDA_REQUIREMENT = re.compile(
    r"^(?P<name>[0-9A-Za-z_\-\.]+)"
    r"((?P<version_specifier>[>=<]+)(?P<version>[0-9a-zA-Z\.]+))?"
    r"((?P<build_specifier>=)(?P<build>[0-9A-Za-z\_]+))?$"
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

    Skips any pip requirements included in the export. Only requirements that are
    managed by conda are returned.
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


class CondaEnvironment(PythonEnvironment):
    conda_requirements: List[CondaRequirement] = Field(default_factory=list)

    @classmethod
    def from_environment(cls: Type[Self], exclude_nested: bool = False) -> Self:
        conda_requirements = (
            current_environment_conda_requirements()
            if "conda" in sys.executable
            else []
        )
        pip_requirements = remove_duplicate_requirements(
            conda_requirements,
            current_environment_requirements(
                exclude_nested=exclude_nested, on_uninstallable_requirement="warn"
            ),
        )
        python_requirement = pop_requirement_by_name(conda_requirements, "python")
        python_version = python_requirement.version if python_requirement else None

        return cls(
            pip_requirements=pip_requirements,
            conda_requirements=conda_requirements,
            python_version=python_version,
        )

    @classmethod
    @validate_arguments
    def from_file(cls: Type[Self], path: Path) -> Self:
        parsed = yaml.safe_load(path.read_text())

        # If no dependencies are given, this field will not be present
        dependencies = parsed.get("dependencies", [])

        # The string check will exclude nested objects like the 'pip' subtree
        conda_requirements = [
            CondaRequirement(dep) for dep in dependencies if isinstance(dep, str)
        ]

        python_requirement = pop_requirement_by_name(conda_requirements, "python")
        python_version = python_requirement.version if python_requirement else None

        other_requirements = {}

        # Parse nested requirements. We only support 'pip' for now but we'll check for
        # others
        for subtree in [dep for dep in dependencies if isinstance(dep, dict)]:
            key = list(subtree.keys())[0]

            if key in other_requirements:
                raise ValueError(
                    "Invalid conda requirements specification. "
                    f"Found duplicate key {key!r}."
                )

            other_requirements[key] = subtree[key]

        pip_requirements = other_requirements.pop("pip", [])

        if other_requirements:
            raise ValueError(
                "Found unsupported requirements types in file: "
                f"{listrepr(other_requirements.keys(), ', ')}"
            )

        return cls(
            conda_requirements=conda_requirements,
            pip_requirements=pip_requirements,
            python_version=python_version,
        )

    def install_commands(self) -> List[str]:
        pip_install_commands = super().install_commands()

        if not self.conda_requirements:
            return pip_install_commands

        return [
            ["conda", "install", *(str(req) for req in self.conda_requirements)]
        ] + pip_install_commands
