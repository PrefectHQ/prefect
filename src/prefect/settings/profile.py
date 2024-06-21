from pathlib import Path
from typing import Any, Optional, Union, overload

import toml
from pydantic import BaseModel, ConfigDict, Field
from typing_extensions import Self

from .main import PrefectSettings


class Profile(BaseModel):
    """
    A user profile containing settings.
    """

    name: str
    settings: dict[str, Any] = Field(default_factory=dict)
    source: Optional[Path] = None
    model_config = ConfigDict(extra="ignore", arbitrary_types_allowed=True)

    @overload
    @classmethod
    def load(cls: type[Self], path: Path, name: str) -> Self:
        pass

    @overload
    @classmethod
    def load(
        cls: type[Self],
        path: Path,
    ) -> list[Self]:
        pass

    @classmethod
    def load(
        cls: type[Self],
        path: Path = PrefectSettings().PREFECT_HOME,
        name: Optional[str] = None,
    ) -> Union[Self, list[Self]]:
        return toml.loads(path.read_text())
