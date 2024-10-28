from pathlib import Path
from typing import Tuple, Type

from pydantic import Secret, SecretStr

DEFAULT_PREFECT_HOME = Path.home() / ".prefect"
DEFAULT_PROFILES_PATH = Path(__file__).parent.joinpath("profiles.toml")
_SECRET_TYPES: Tuple[Type, ...] = (Secret, SecretStr)
