---
description: Prefect will run your deployment on our infrastructure.
tags:
    - managed infrastructure
search:
  exclude: true
---

# Managed Execution

Prefect Cloud provides a **prefect-managed** work pool that you can use for your workflow execution environment.
Deployments run with this work pool do not require a worker and do not require a cloud provider account.
Prefect handles the infrastructure for you.

Managed execution is a great option for users who want to get started quickly, with no infrastructure setup.

!!! warning "Managed Execution is in alpha"
    Managed Execution is currently in alpha.
    Features are likely to change without warning.

## Usage guide

Run a flow with managed infrastructure in three steps.

### Step 1

Create a new work pool of type **prefect:managed**.

!!! note
    In the alpha period, you must have the managed execution feature enabled for your account to create a work pool of this type.

### Step 2

Create a deployment using the flow `deploy` method or `prefect.yaml`.

Specify the name of your managed work pool, as shown in this example that uses the `deploy` method:

```python hl_lines="9" title="managed-execution.py"
from prefect import flow

if __name__ == "__main__":
    flow.from_source(
    source="https://github.com/desertaxle/demo.git",
    entrypoint="flow.py:my_flow",
    ).deploy(
        name="test-managed-flow",
        work_pool_name="prefect-managed",
    )
```

With your CLI authenticated to your Prefect Cloud workspace, run the script to create your deployment:

<div class="terminal">
```bash
python managed-execution.py
```
</div>

Note that this deployment uses flow code stored in a GitHub repository.
If you would like to use your own flow code, push your code to your repository and specify your own repository URL and entrypoint.

### Step 3

Schedule a deployment run from the UI or from the CLI.

It may take a minute for the flow run to start and the logs to appear in the UI.

That's it! You ran a flow on remote infrastructure without any infrastructure setup, worker, or cloud provider account.

### Adding dependencies

You can install Python package dependencies at runtime by passing `job_variables={"env": {"EXTRA_PIP_PACKAGES": ["pandas", "prefect-aws"] }}` like this:

```python hl_lines="10"
from prefect import flow

if __name__ == "__main__":
    flow.from_source(
    source="https://github.com/desertaxle/demo.git",
    entrypoint="flow.py:my_flow",
    ).deploy(
        name="test-managed-flow",
        work_pool_name="prefect-managed",
        job_variables={"env": {"EXTRA_PIP_PACKAGES": ["pandas", "prefect-aws"] }}
    )
```

## Limitations

Managed execution requires Prefect 2.14.4 or newer.

All limitations listed below may change without warning during the alpha period.
We will update this page as we make changes.

### Concurrency & work pools

- Maximum of 10 concurrent flow runs per workspace.
- Maximum of one managed execution work pool per user.

### Images

Managed execution requires that you run one of the offered Docker images.
You may not use your own Docker image.
One Docker image is supported at this time: `prefecthq/prefect:2-latest`.
We plan to support additional images with common dependencies soon.

However, as noted above, you can install Python package dependencies at runtime.

If you need to use your own image, we recommend using another type of work pool.

### Code storage

Flow code must be stored in an accessible remote location.
This means git-based cloud providers such as GitHub, Bitbucket, or GitLab are supported.
Remote block-based storage is also supported, so S3, GCS, and Azure Blob are additional code storage options.

### Resources

Memory is limited to 1Gb of RAM.

Maximum run time is 1 hour.

## Pricing

Managed execution is free during the alpha period.
We will announce pricing before the beta period begins.

## Next steps

Read more about creating deployments in the [deployment guide](/guides/prefect-deploy/).

If you find that you need more control over your infrastructure, serverless push work pools might be a good option.
Read more [here](/guides/deployment/push-work-pools/).
