from prefect import Task
from pathlib import Path


class FileBase(Task):
    """ This is just a base class to reduce duplicate code. """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def _check_path_is_set(self, path: Path, name: str):
        """Checks if a path is set. Otherwise raise an exception."""
        if not path:
            raise ValueError(f"{name.capitalize()} path is not set!")

    def _check_path_exists(self, path: Path, name: str):
        """Checks if a source path exists. Otherwise raise an exception."""
        if not path.exists():
            raise ValueError(f"{name.capitalize()} path ({path}) not found!")
