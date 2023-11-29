---
description: Prefect will run your deployment on our infrastructure.
tags:
    - managed infrastructure
search:
  boost: 2
---

# TK no index, no show in search results

# Managed Execution

Prefect Cloud provides a **prefect-managed** work pool that you can use for your workflow execution environment.
Deployments run with this work pool do not require a worker and do not require a cloud provider account.
Prefect handles the infrastructure.
You just tell Prefect where to find your flow code.
Options for storing your flow code include git-based cloud storage with GitHub, Bitbucket, or GitLab.
Managed execution is a great option for users who want to get started quickly and who don't want to manage their own infrastructure.

!!! warning "Managed Execution is in alpha"
    Managed Execution is currently in alpha.
    Features are likely to change without warning.
    If you are interested in using this feature, please contact us at []()

## Steps

### Step 1

Create a new work pool of type **prefect-managed**.
TK screenshot of UI

### Step 2

Create a deployment using the code below.

Here is code that you can run to deploy a flow to the managed work pool.

=== "Python"

    ```python
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

### Step 3

Run the deployment from the UI or from the CLI.

You can install dependencies at runtime by passing `job_variables={"env": {"EXTRA_PIP_PACKAGES": ["pandas", "prefect-aws"] }}` to the `deploy` call in the example.

## Limitations

Managed execution requires Prefect 2.14.4 or newer.

All limitations listed below may change without warning during the alpha period.
We will update this page as we make changes.

### Concurrency & work pools

Maximum of 10 concurrent flow runs per workspace.

Maximum one managed execution work pool per user.

### Images

One Docker image is supported at this time: prefecthq/prefect:2-latest.
We will support additional images with common dependencies soon, and are open to feedback on your image needs.
Managed execution requires that you run one of the offered Docker images.
You may not use your own Docker image.
However, as noted above, you can install Python package dependencies at runtime.

If you need to use your own image, we recommend using another type of work pool.

### Code storage

Flow code must be stored in an accessible remote location.
This means git-based cloud providers such as GitHub, Bitbucket, or GitLab are supported.
Remote block-based storage is also supported, so S3, GCS, and Azure Blob are also options.

### Resources

Memory is limited to 1Gb of RAM.

Maximum run time is 1 hour.

## Pricing

Managed execution is free during the alpha period.
We will announce pricing before the beta period begins.

## Feedback

Please provide any feedback on managed execution via Prefect Community Slack TK.
