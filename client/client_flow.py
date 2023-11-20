from prefect import flow, task
from prefect.concurrency import asyncio, common, events, services, sync  # noqa: F401


def skip_remote_run():
    """
    Github Actions will not populate secrets if the workflow is triggered by
    external collaborators (including dependabot). This function checks if
    we're in a CI environment AND if the secret was not populated -- if
    those conditions are true, we won't try to run the flow against the remote
    API
    """
    import os

    in_gha = os.environ.get("CI", False)
    secret_not_set = os.environ.get("PREFECT_API_KEY", "") == ""
    return in_gha and secret_not_set


@task
def smoke_test_task(*args, **kwargs):
    print(args, kwargs)


@flow
def smoke_test_flow():
    smoke_test_task("foo", "bar", baz="qux")


if __name__ == "__main__":
    if not skip_remote_run():
        smoke_test_flow()
