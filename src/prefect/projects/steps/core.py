"""
Core set of steps for managing Prefect projects.
"""
from prefect.utilities.importtools import import_object


def run_step(step: dict) -> dict:
    """
    Runs a step, returns the step's output.

    Steps are assumed to be in the format {"importable.func.name": {"kwarg1": "value1", ...}}
    """
    path, inputs = step.popitem()

    if step:
        raise ValueError(
            f"Step has unexpected additional keys: {', '.join(step.keys())}"
        )

    step_func = import_object(path)
    return step_func(**inputs)


def set_working_directory():
    pass


def git_clone_project(repo: str, branch: str = None, repo_url: str = None) -> dict:
    """
    Just a repo name will be assumed GitHub, otherwise provide a full repo_url.
    """
    print(f"I am a step that received repo={repo!r} and branch={branch!r} as inputs.")
