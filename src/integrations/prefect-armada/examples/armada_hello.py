"""
An example flow that runs as an Armada job on a local dev cluster.

Prerequisites:

  - An Armada server reachable over gRPC, with a queue the worker may submit to
    (`prefect` by default).
  - A Prefect server bound to an address the Armada cluster can route to, since
    the flow runs in a pod inside that cluster.
  - An `armada` work pool with a worker started against it.

Then, with the same environment `start-dev.sh` uses:

    python examples/armada_hello.py

The pod pulls the flow's code from `FLOW_SOURCE` at run time, so this file has
to exist on that branch -- commit and push before running, or point FLOW_SOURCE
and FLOW_ENTRYPOINT somewhere else. Baking the code into `IMAGE` instead and
deploying without `from_source` works too.
"""

from __future__ import annotations

import os

from prefect import flow, get_run_logger, task

# Where the flow-run pod fetches this file from. Any source `from_source`
# accepts works; a public git repository is the least trouble on a dev cluster.
FLOW_SOURCE = os.environ.get("FLOW_SOURCE", "https://github.com/richscott/prefect.git")
FLOW_BRANCH = os.environ.get("FLOW_BRANCH", "richscott/armada-integration")
FLOW_ENTRYPOINT = os.environ.get(
    "FLOW_ENTRYPOINT",
    "src/integrations/prefect-armada/examples/armada_hello.py:hello",
)

WORK_POOL = os.environ.get("WORK_POOL", "my-armada-pool")
ARMADA_QUEUE = os.environ.get("ARMADA_QUEUE", "prefect")
# A development checkout's default image resolves to an unpublished
# `prefecthq/prefect-dev` tag, so name a published one explicitly.
IMAGE = os.environ.get("IMAGE", "prefecthq/prefect:3-latest")


@task
def greet(name: str) -> str:
    return f"Hello, {name}, from Armada!"


@flow(log_prints=True)
def hello(names: list[str] | None = None) -> list[str]:
    """Greet each name, one task run apiece."""
    logger = get_run_logger()
    greetings = [greet(name) for name in names or ["Marvin", "Trillian", "Ford"]]
    for greeting in greetings:
        logger.info(greeting)
    return greetings


if __name__ == "__main__":
    from prefect import Flow
    from prefect.runner.storage import GitRepository

    source = Flow.from_source(
        source=GitRepository(url=FLOW_SOURCE, branch=FLOW_BRANCH),
        entrypoint=FLOW_ENTRYPOINT,
    )

    deployment_id = source.deploy(
        name="armada-smoke",
        work_pool_name=WORK_POOL,
        parameters={"names": ["Marvin", "Trillian", "Ford"]},
        job_variables={
            "image": IMAGE,
            "queue": ARMADA_QUEUE,
            "namespace": "default",
            # Armada rejects containers whose requests differ from their limits,
            # so keep each pair identical.
            "cpu_request": "500m",
            "cpu_limit": "500m",
            "memory_request": "512Mi",
            "memory_limit": "512Mi",
            # Lower values are scheduled first.
            "priority": 1,
        },
        # Nothing to build or push: the pod pulls a published image and fetches
        # the flow's code from FLOW_SOURCE.
        build=False,
        push=False,
    )
    print(f"Deployed {FLOW_ENTRYPOINT} as {deployment_id}")
    print("Run it with: prefect deployment run 'hello/armada-smoke'")
