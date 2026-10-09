# prefect-armada

<p align="center">
    <a href="https://pypi.python.org/pypi/prefect-armada/" alt="PyPI version">
        <img alt="PyPI" src="https://img.shields.io/pypi/v/prefect-armada?color=0052FF&labelColor=090422"></a>
    <a href="https://github.com/PrefectHQ/prefect/tree/main/src/integrations/prefect-armada" alt="Stars">
        <img src="https://img.shields.io/github/stars/PrefectHQ/prefect?color=0052FF&labelColor=090422" /></a>
</p>

`prefect-armada` runs Prefect flow runs on [Armada](https://armadaproject.io/), a
multi-cluster batch scheduler for Kubernetes.

## Getting started

### Prerequisites

- An Armada server you can reach over gRPC.
- An Armada queue that your credentials are permitted to submit to.

### Creating a test Armada server with armada-operator

If you do not have access to a full Armada cluster, an Armada test cluster can be quickly set up
by using the [armada-operator](https://github.com/armadaproject/armada-operator/) - a Kubernetes
Operator for quickly setting up an Armada cluster on any Linux or macOS system that has
Docker installed. Typically, you can just clone that repository, then run `make kind-all` to
have it instantiate a basic K8s (`kind`) cluster and deploy Armada on top of it.

### Installation

Install `prefect-armada` with `pip`:

```bash
pip install prefect-armada
```

### Running flow runs as Armada jobs

Create an Armada work pool and start a worker:

```bash
prefect work-pool create --type armada my-armada-pool
prefect worker start --pool my-armada-pool
```

By default the worker connects to `localhost:50051` and submits to the `prefect`
queue. Connection details can be set on the work pool (via an
`ArmadaClusterConfig` or `ArmadaCredentials` block) or in the worker's
environment:

```bash
export PREFECT_INTEGRATIONS_ARMADA_CONNECTION_HOST="armada.example.com"
export PREFECT_INTEGRATIONS_ARMADA_CONNECTION_PORT="50051"
export PREFECT_INTEGRATIONS_ARMADA_CONNECTION_DISABLE_SSL="false"
```

The `ARMADA_SERVER` and `ARMADA_PORT` variables used by Armada's own tooling are
also honored.

Flows can also be sent to an Armada work pool directly, without a deployment:

```python
from prefect import flow
from prefect_armada.decorators import armada


@armada(work_pool="my-armada-pool")
@flow
def my_flow():
    print("Hello from Armada!")


my_flow()
```

### Submitting jobs from a flow

`ArmadaJob` submits an arbitrary Armada job and waits for it to finish:

```python
from prefect import flow
from prefect_armada import ArmadaJob
from prefect_armada.credentials import ArmadaCredentials


@flow
def run_a_job():
    job = ArmadaJob(
        credentials=ArmadaCredentials(),
        queue="prefect",
        job_request={
            "priority": 1,
            "podSpec": {
                "restartPolicy": "Never",
                "containers": [
                    {
                        "name": "prefect-job",
                        "image": "docker.io/library/ubuntu:latest",
                        "args": ["echo", "hello from armada"],
                        "resources": {
                            "requests": {"cpu": "120m", "memory": "510Mi"},
                            "limits": {"cpu": "120m", "memory": "510Mi"},
                        },
                    }
                ],
            },
        },
    )

    job_run = job.trigger()
    job_run.wait_for_completion()
    return job_run.fetch_result()
```

Individual Armada API calls are also available as tasks in
`prefect_armada.jobs`, `prefect_armada.jobsets`, `prefect_armada.queues`,
`prefect_armada.events`, and `prefect_armada.logs`.

## How it works

Armada is asynchronous: the worker submits a job and Armada schedules it onto one
of its Kubernetes clusters later. The worker therefore returns as soon as Armada
accepts the job, and an **observer** thread watches the job set's event stream to

- replicate Armada job events (`prefect.armada.job.*`) into Prefect's event
  system for use in Automations, and
- mark a flow run as `Crashed` when its Armada job fails before the flow run can
  report its own state, forwarding the job's logs to the flow run.

Each flow run is submitted to its own job set by default, so the observer's watch
ends when the flow run's job finishes. The observer can be disabled with
`PREFECT_INTEGRATIONS_ARMADA_OBSERVER_ENABLED=false`, and job sets submitted by
other processes can be watched with
`PREFECT_INTEGRATIONS_ARMADA_OBSERVER_JOB_SETS="my-queue/my-job-set"`.

## Resources

Refer to the [Prefect Armada docs](https://docs.prefect.io/integrations/prefect-armada)
and the [Armada docs](https://armadaproject.io/) for more information.

### Feedback

If you encounter any bugs while using `prefect-armada`, feel free to open an
issue in the [prefect](https://github.com/PrefectHQ/prefect) repository.

### Contributing

If you'd like to help contribute to fix an issue or add a feature to
`prefect-armada`, please
[propose changes through a pull request from a fork of the repository](https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/proposing-changes-to-your-work-with-pull-requests/creating-a-pull-request-from-a-fork).
