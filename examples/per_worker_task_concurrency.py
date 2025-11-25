# ---
# title: Per-worker task concurrency
# description: Use Global Concurrency Limits to control how many tasks can use a worker's local resources simultaneously.
# icon: layer-group
# dependencies: ["prefect"]
# keywords: ["concurrency", "workers", "advanced"]
# draft: false
# ---
#
# When a worker runs multiple flow runs concurrently, those flow runs share the
# worker machine's resources—CPU, memory, GPU, local software. Some tasks may
# need to limit how many can run at once to avoid overloading these resources.
#
# **The problem:** Using `--limit 1` on the worker forces entire flow runs to be
# sequential. But often only specific tasks need limits—other tasks could overlap.
#
# **The solution:** Use [Global Concurrency Limits](https://docs.prefect.io/v3/develop/global-concurrency-limits)
# with worker-specific names. GCLs are coordinated by the Prefect server, so they
# work across the separate subprocesses that each flow run executes in.
#
# ## Example: Image processing with ML inference
#
# Consider a pipeline that processes images through an ML model:
#
# 1. **Download image** — network-bound, can run many in parallel
# 2. **Run ML model** — uses GPU memory, need to limit concurrent runs
# 3. **Save results** — disk I/O, can run many in parallel
#
# Without limits, if 5 flow runs hit the ML step simultaneously, they'd all try
# to load the model into GPU memory and crash. With per-worker limits, only 1-2
# run at a time while others wait.
#
# ## Setup

import os
import time

from prefect import flow, get_run_logger, task
from prefect.concurrency.sync import concurrency


def get_worker_id() -> str:
    """
    Get worker identity from environment.

    Set this when starting the worker:
        WORKER_ID=gpu-1 prefect worker start --pool ml-pool
    """
    return os.getenv("WORKER_ID", "default")


# ## Tasks without limits
#
# These tasks don't contend for limited resources, so they run freely.


@task
def download_image(image_id: int) -> dict:
    """Download an image from storage. Network-bound, no local resource contention."""
    logger = get_run_logger()
    logger.info(f"Image {image_id}: downloading...")
    time.sleep(1)  # simulate download
    return {"image_id": image_id, "path": f"/tmp/image_{image_id}.jpg"}


@task
def save_results(data: dict) -> str:
    """Save processed results. Fast operation, no limits needed."""
    logger = get_run_logger()
    logger.info(f"Image {data['image_id']}: saving results...")
    time.sleep(0.5)
    return f"processed-{data['image_id']}"


# ## Task with per-worker limit
#
# This task uses a local resource (GPU) that can only handle limited concurrent
# usage. The limit is scoped to this worker so each machine has independent limits.


@task
def run_ml_model(data: dict) -> dict:
    """
    Run image through ML model.

    GPU memory is limited—only 1-2 can run at once per worker machine.
    Uses a Global Concurrency Limit scoped to this worker's identity.
    """
    logger = get_run_logger()
    worker_id = get_worker_id()
    image_id = data["image_id"]

    # Limit key includes worker ID: each worker has its own limit
    with concurrency(f"gpu:{worker_id}", occupy=1):
        logger.info(f"Image {image_id}: running ML inference (GPU)...")
        time.sleep(3)  # simulate model inference

    return {**data, "predictions": [0.9, 0.1]}


# ## The flow


@flow(log_prints=True)
def process_image(image_id: int = 1) -> str:
    """
    Process an image through the ML pipeline.

    When multiple instances run concurrently on the same worker:
    - download and save tasks overlap freely
    - run_ml_model tasks are limited by the per-worker GPU concurrency limit
    """
    logger = get_run_logger()
    logger.info(f"Processing image {image_id} on worker '{get_worker_id()}'")

    image = download_image(image_id)
    predictions = run_ml_model(image)
    result = save_results(predictions)

    return result


# ## Running the example
#
# ### 1. Create a Global Concurrency Limit for each worker
#
# Each worker machine needs its own limit. The limit value controls how many
# ML tasks can run simultaneously on that machine.
#
# ```bash
# # GPU machine 1: allow 2 concurrent ML tasks
# prefect gcl create gpu:gpu-1 --limit 2
#
# # GPU machine 2: allow 2 concurrent ML tasks
# prefect gcl create gpu:gpu-2 --limit 2
# ```
#
# ### 2. Create work pool and deploy
#
# ```bash
# prefect work-pool create ml-pool --type process
# prefect deploy --all
# ```
#
# ### 3. Start workers with unique IDs
#
# Each worker needs a unique ID that matches its GCL name:
#
# ```bash
# # Machine 1
# WORKER_ID=gpu-1 prefect worker start --pool ml-pool --limit 10
#
# # Machine 2
# WORKER_ID=gpu-2 prefect worker start --pool ml-pool --limit 10
# ```
#
# The `--limit 10` allows up to 10 concurrent flow runs, but the GCL ensures
# only 2 are in the ML step at any time.
#
# ### 4. Submit jobs
#
# ```bash
# for i in {1..20}; do
#   prefect deployment run process-image/process-image --param image_id=$i --timeout 0
# done
# ```
#
# ## What you'll see
#
# With 10 concurrent flow runs on a worker:
#
# - **Download tasks** from all 10 start immediately and overlap
# - **ML tasks** queue up—only 2 run at a time (per the GCL limit)
# - **Save tasks** run as soon as their ML task completes
#
# Flow runs aren't blocked entirely—just the resource-intensive step is limited.
# This maximizes throughput while protecting the GPU from overload.
#
# ## Why this works
#
# 1. **GCLs are server-coordinated** — The Prefect server tracks who holds what
#    limit. It doesn't matter that flow runs are separate processes.
#
# 2. **Worker-specific names** — By including `worker_id` in the limit name,
#    each worker machine has independent limits. GPU-1's limit doesn't affect GPU-2.
#
# 3. **Selective application** — Only the tasks that need limits acquire them.
#    Everything else runs at full concurrency.
#
# ## Adapting this pattern
#
# The same pattern works for any local resource constraint:
#
# - **Software licenses**: A tool that only allows N concurrent instances
# - **Memory-intensive processing**: Limit concurrent jobs to avoid OOM
# - **Disk I/O**: Limit concurrent writes to a local SSD
# - **Local services**: A sidecar database with connection limits
#
# Just change the limit name and value to match your constraint.
#
# ## Related docs
#
# - [Global Concurrency Limits](https://docs.prefect.io/v3/develop/global-concurrency-limits)
# - [Workers](https://docs.prefect.io/v3/deploy/infrastructure-concepts/workers)

if __name__ == "__main__":
    process_image(image_id=1)
