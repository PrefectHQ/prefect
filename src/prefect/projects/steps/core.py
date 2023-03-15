"""
Core set of steps for managing Prefect projects.
"""


def run_step(step: dict) -> dict:
    print(step)


def set_working_directory():
    pass


def git_clone_project(repo: str, branch: str = None, repo_url: str = None) -> dict:
    """
    Just a repo name will be assumed GitHub, otherwise provide a full repo_url.
    """
