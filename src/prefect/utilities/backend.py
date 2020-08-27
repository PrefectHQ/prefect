import toml
from pathlib import Path
import os


def load_backend() -> dict:
    """
    Loads
    """
    if backend_path().exists():
        with backend_path().open("r") as f:
            return toml.load(f)  # type: ignore
    return {}


def save_backend(backend: str) -> None:
    """
    Saves
    """
    backend_path().parent.mkdir(exist_ok=True, parents=True)
    with backend_path().open("w+") as f:
        toml.dump({"backend": backend}, f)


def backend_path() -> Path:
    from prefect import context

    path = "{home}/".format(home=context.config.home_dir)
    return Path(os.path.expanduser(path)) / "backend.toml"
