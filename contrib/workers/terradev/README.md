# prefect-terradev

A Prefect work pool worker that routes flow runs to GPU compute across
17 cloud providers via [Terradev](https://github.com/theoddden/Terradev).

Fills the gap between Prefect's orchestration layer and neocloud GPU
availability — flows that need GPU compute are no longer pinned to a
single provider's capacity.

## Installation

```bash
pip install prefect-terradev
terradev configure --provider runpod   # configure at least one provider
```

## Usage

### Create a work pool

```bash
prefect work-pool create gpu-pool --type terradev
```

### Start a worker

```bash
prefect worker start --pool gpu-pool
```

### Configure via YAML

```yaml
# prefect.yaml
work_pool:
  name: gpu-pool
  work_queue_name: default
  job_variables:
    gpu_type: H100
    max_price_per_hour: 4.00
    spot: true
```

### Example flow

```python
from prefect import flow, task

@task
def train(epochs: int):
    import torch
    # runs on the provisioned GPU instance
    ...

@flow
def training_run(epochs: int = 10):
    train(epochs)

if __name__ == "__main__":
    training_run.deploy(
        name="gpu-training",
        work_pool_name="gpu-pool",
        job_variables={"gpu_type": "H100", "max_price_per_hour": 3.50},
    )
```

When this flow runs, the Terradev worker:
1. Calls `terradev compute provision --gpu H100 --max-price 3.50`
2. Terradev selects the cheapest H100 across all configured providers
3. Flow executes on the provisioned instance via SSH
4. Instance is terminated on completion or failure

## Supported providers

| Provider | GPUs available |
|---|---|
| RunPod | H100, A100, RTX4090, RTX3090 |
| Vast.ai | H100, A100, RTX4090 |
| TensorDock | A100, RTX4090, RTX3090 |
| Crusoe | H100, A100 |
| Hyperstack | H100, A100 |
| Latitude | H100, A100 |
| E2E Networks | A100, V100 |
| Gcore | A100, L40S |
| AWS / GCP / Azure | All major GPU types |
| DigitalOcean, InferX, Baseten, SiliconFlow, HuggingFace, YottaLabs | Various |

## Configuration reference

| Field | Type | Default | Description |
|---|---|---|---|
| `provider` | string | auto | Force a specific provider |
| `gpu_type` | string | A100 | GPU model |
| `region` | string | auto | Provider region |
| `max_price_per_hour` | float | none | Price ceiling in USD |
| `spot` | bool | false | Allow spot instances |
| `ssh_user` | string | ubuntu | SSH user on the instance |
