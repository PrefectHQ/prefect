import json
import sys

from prefect.utilities.asyncutils import run_coro_as_sync


def execute_bundle_from_file(key: str):
    """
    Loads a bundle from a file and executes it.

    Args:
        key: The key of the bundle to execute.
    """
    with open(key, "r") as f:
        bundle = json.load(f)

    from prefect.runner.runner import Runner

    run_coro_as_sync(Runner().execute_bundle(bundle))


if __name__ == "__main__":
    if len(sys.argv) < 3 and sys.argv[1] != "--key":
        print("Please provide a key representing a path to a bundle")
        sys.exit(1)
    key = sys.argv[2]
    execute_bundle_from_file(key)
