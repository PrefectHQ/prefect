"""
Script to run all "generation" scripts that require a python environment in sequence using
the same environment. This avoids multiple virtual environment creations in pre-commit hooks.
"""

import importlib.util
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from types import ModuleType


def import_script(script_path: Path) -> ModuleType:
    """Import a Python file as a module."""
    spec = importlib.util.spec_from_file_location("module.name", str(script_path))
    if spec is None:
        raise ImportError(f"Could not load spec for {script_path}")

    module = importlib.util.module_from_spec(spec)
    if spec.loader is None:
        raise ImportError(f"Could not load module for {script_path}")

    spec.loader.exec_module(module)
    return module


def run_generator(script_name: str) -> None:
    print(f"Running {script_name}...")

    script_path = Path(__file__).parent / script_name

    module = import_script(script_path)

    if not hasattr(module, "main"):
        raise AttributeError(f"Script {script_name} does not have a main function")
    module.main()

    print(f"Completed {script_name}")


def main() -> None:
    with ProcessPoolExecutor() as executor:
        executor.map(
            run_generator,
            [
                "generate_mintlify_openapi_docs.py",
                "generate_settings_schema.py",
                "generate_settings_ref.py",
                "generate_api_ref.py",
            ],
        )

    print("All generators completed successfully!")


if __name__ == "__main__":
    main()
