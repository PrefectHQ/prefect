import sys
from pathlib import Path
from typing import List, Type

from pydantic import BaseModel, Field, validate_arguments, validator
from typing_extensions import Self

from prefect.software.pip import PipRequirement, current_environment_requirements


class PythonEnvironment(BaseModel):
    """
    A specification for a Python environment.
    """

    python_version: str = None
    pip_requirements: List[PipRequirement] = Field(default_factory=list)

    @validator("python_version", pre=True, always=True)
    def infer_python_version(cls, value):
        if value is None:
            return f"{sys.version_info.major}.{sys.version_info.minor}"
        return value

    @classmethod
    def from_environment(cls: Type[Self], include_nested: bool = True) -> Self:
        """
        Generate requirements from the current environment

        Arguments:
            include_nested: If set, include requirements that are required by other
                packages. If unset, only top-level requirements will be included.
                Defaults to including all requirements.
        """
        pip_requirements = current_environment_requirements(
            include_nested=include_nested, on_uninstallable_requirement="warn"
        )
        return cls(pip_requirements=pip_requirements)

    @classmethod
    @validate_arguments
    def from_file(cls: Type[Self], path: Path) -> Self:
        return PythonEnvironment(pip_requirements=path.read_text().splitlines())

    def install_commands(self, multiline: bool = False) -> List[str]:
        if multiline:
            requires = "\\\n\t"  # Start on a newline
            requires += "\\\n\t".join(f"'{req}'" for req in self.pip_requirements)
        else:
            requires = " ".join(f"'{req}'" for req in self.pip_requirements)

        return [f"pip install {requires}"]
