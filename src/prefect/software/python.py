from pathlib import Path
from typing import List, Type

from prefect._internal.pydantic import HAS_PYDANTIC_V2
from prefect._internal.schemas.validators import infer_python_version

if HAS_PYDANTIC_V2:
    from pydantic.v1 import BaseModel, Field, validate_arguments, validator
else:
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
    def validate_python_version(cls, value):
        return infer_python_version(value)

    @classmethod
    def from_environment(cls: Type[Self], exclude_nested: bool = False) -> Self:
        """
        Generate requirements from the current environment

        Arguments:
            exclude_nested: If True, only top-level requirements will be included.
                Defaults to including all requirements.
        """
        pip_requirements = current_environment_requirements(
            exclude_nested=exclude_nested, on_uninstallable_requirement="warn"
        )
        return cls(pip_requirements=pip_requirements)

    @classmethod
    @validate_arguments
    def from_file(cls: Type[Self], path: Path) -> Self:
        return PythonEnvironment(pip_requirements=path.read_text().strip().splitlines())

    def install_commands(self) -> List[List[str]]:
        if not self.pip_requirements:
            return []

        return [["pip", "install", *(str(req) for req in self.pip_requirements)]]
