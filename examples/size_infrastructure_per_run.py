# ---
# title: Size infrastructure per flow run
# description: Compute CPU and memory requirements before a run starts, then pass them as job variables when launching a deployment.
# icon: server
# dependencies: ["prefect"]
# keywords: ["job variables", "kubernetes", "infrastructure", "deployments"]
# draft: false
# ---
#
# One deployment often processes inputs of very different sizes. A run over a
# small dataset needs a fraction of the CPU and memory that a large one needs,
# but a single deployment has a single set of defaults, so you either
# overprovision every run or hand-edit the run configuration each time.
#
# **The problem:** infrastructure is created *before* your flow code runs. A
# Kubernetes worker builds the Job spec—including `resources.requests` and
# `resources.limits`—from the deployment's [job variables](https://docs.prefect.io/v3/how-to-guides/deployments/customize-job-variables)
# as soon as it picks up the run. Pull steps and flow code execute inside the
# pod that already exists, so they cannot resize it.
#
# **The solution:** decide the size *before* the run is created. A small
# launcher flow inspects the input, computes resource requirements, and passes
# them as job variables to [`run_deployment`](https://docs.prefect.io/v3/api-ref/python/prefect-deployments-flow_runs).
# The worker then builds the pod with those values.
#
# ```
# launcher flow  ->  run_deployment(job_variables=...)  ->  worker builds pod  ->  flow code runs
#     ^ sizing decision happens here                          ^ too late to resize
# ```
#
# ## Setup
#
# This example assumes a Kubernetes work pool and a `process-dataset` deployment
# that does the actual work. The launcher itself is cheap—run it on a small
# process pool, on a schedule, or from an automation.

from typing import Any

from prefect import flow, get_run_logger, task
from prefect.deployments import run_deployment

# ## Estimate the work
#
# Replace this with whatever your system already knows about the input: a row
# count from a metadata table, an object size from S3, a response from an
# internal sizing service, or the runtime of the previous run.


@task(retries=2)
def estimate_dataset_size(dataset: str) -> int:
    """Return the size of a dataset in megabytes."""
    known_sizes = {"clickstream": 240_000, "orders": 12_000, "lookups": 300}
    return known_sizes.get(dataset, 1_000)


# ## Turn the estimate into job variables
#
# Keep this mapping in one place so every launch path uses the same rules. The
# keys below (`cpu_request`, `memory_request`, `cpu_limit`, `memory_limit`) are
# the defaults exposed by the Kubernetes work pool; other work pool types expose
# different variable names, and you can add your own by editing the work pool's
# base job template.


def resources_for(size_mb: int) -> dict[str, Any]:
    """Map an estimated dataset size to Kubernetes job variables."""
    if size_mb < 1_000:
        cpu, memory = "500m", "1Gi"
    elif size_mb < 50_000:
        cpu, memory = "2", "8Gi"
    else:
        cpu, memory = "8", "32Gi"

    return {
        "cpu_request": cpu,
        "cpu_limit": cpu,
        "memory_request": memory,
        "memory_limit": memory,
    }


# ## The launcher flow
#
# The launcher creates the real run with both parameters and job variables. Set
# `timeout=0` to submit the run without waiting for it to finish.


@flow
def launch_dataset_processing(dataset: str = "orders") -> str:
    """Size the infrastructure for a dataset, then launch the processing run."""
    logger = get_run_logger()

    size_mb = estimate_dataset_size(dataset)
    job_variables = resources_for(size_mb)

    logger.info(f"{dataset} is ~{size_mb} MB, launching with {job_variables}")

    flow_run = run_deployment(
        name="process-dataset/kubernetes",
        parameters={"dataset": dataset},
        job_variables=job_variables,
        timeout=0,
    )

    return str(flow_run.id)


# ## Running the example
#
# ### 1. Deploy the flow that does the work
#
# ```bash
# prefect work-pool create data-pool --type kubernetes
# prefect deploy process_dataset.py:process_dataset \
#   --name kubernetes --pool data-pool
# ```
#
# ### 2. Deploy the launcher
#
# The launcher only makes an API call, so a process work pool is enough.
#
# ```bash
# prefect work-pool create launcher-pool --type process
# prefect deploy size_infrastructure_per_run.py:launch_dataset_processing \
#   --name launcher --pool launcher-pool
# ```
#
# ### 3. Launch runs through the launcher
#
# ```bash
# prefect deployment run launch-dataset-processing/launcher \
#   --param dataset=clickstream
# ```
#
# Each launched run shows its own resource values under the `Configuration` tab
# of the flow run in the UI, and the pod is created with those requests and
# limits.
#
# ## Adapting this pattern
#
# The sizing input and the job variables both change with your setup:
#
# - **Sizing input**: row counts, file sizes, the duration of the last run, a
#   customer tier, or a value returned by an internal service.
# - **Job variables**: any variable in the work pool's base job template—image,
#   node selector, service account, GPU count, or environment variables.
#
# Other places the same decision can live:
#
# - **An event-driven automation** that runs the deployment with job variables
#   rendered from a [Jinja template](https://docs.prefect.io/v3/how-to-guides/automations/creating-automations).
# - **An external service** that calls the Prefect API directly, which is a good
#   fit when the service already tracks the sizing information.
#
# If the sizing rules only produce a handful of distinct results, separate
# deployments—`process-dataset/small`, `/medium`, `/large`—are simpler and let
# people pick a size from the UI without typing job variables by hand.
#
# ## Related docs
#
# - [Override job variables](https://docs.prefect.io/v3/how-to-guides/deployments/customize-job-variables)
# - [Run deployments](https://docs.prefect.io/v3/how-to-guides/deployments/run-deployments)
# - [Kubernetes work pools](https://docs.prefect.io/v3/how-to-guides/deployment_infra/kubernetes)

if __name__ == "__main__":
    # print the sizing rules without launching any runs
    for size_mb in (300, 12_000, 240_000):
        print(size_mb, resources_for(size_mb))
