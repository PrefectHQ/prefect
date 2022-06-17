import sys
from pathlib import Path
from typing import List, Type

from pydantic import BaseModel, validate_arguments
from typing_extensions import Self

from prefect.software.base import remove_duplicate_requirements
from prefect.software.conda import (
    CondaRequirement,
    current_environment_conda_requirements,
)
from prefect.software.pip import PipRequirement, current_environment_requirements


class PythonRequirements(BaseModel):
    """
    A collection of Python requirements.

    Editable installations:
        Since these requirements are intended to be transportable across machines,
        editable installations are not supported.
    """

    pip_requirements: List[PipRequirement]
    conda_requirements: List[CondaRequirement]

    @classmethod
    @validate_arguments
    def from_requirements_file(cls: Type[Self], path: Path) -> Self:
        """
        Load pip requirements from a requirements file at the given path.
        """
        return cls(pip_requirements=path.read_text().strip().splitlines())

    @classmethod
    def from_environment(cls: Type[Self], include_nested: bool = True) -> Self:
        """
        Generate requirements from the current environment

        Arguments:
            include_nested: If set, include requirements that are required by other
                packages. If unset, only top-level requirements will be included.
                Defaults to including all requirements.
        """
        conda_requirements = (
            current_environment_conda_requirements()
            if "conda" in sys.executable
            else []
        )
        pip_requirements = remove_duplicate_requirements(
            conda_requirements,
            current_environment_requirements(
                include_nested=include_nested, on_uninstallable_requirement="warn"
            ),
        )
        return cls(
            pip_requirements=pip_requirements, conda_requirements=conda_requirements
        )

    @validate_arguments
    def to_requirements_file(self, path: Path, linesep="\n") -> int:
        """
        Write to a requirements file at the given path.

        Note the line seperator defaults to "\n" instead of `os.linesep` to make it
        easy to copy this file into a Docker image.
        """
        # TODO: Rethink the interface here when implementing Conda; we may want to just
        #       return a list of strings for the user to write and join how they please
        return path.write_text(
            linesep.join([str(requirement) for requirement in self.pip_requirements])
        )
