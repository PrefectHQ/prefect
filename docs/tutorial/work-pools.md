---
description: Learn how Prefect deployments can be configured for scheduled and remote execution with work pools.
tags:
    - work pools
    - orchestration
    - flow runs
    - deployments
    - schedules
    - tutorial
search:
  boost: 2
---

# Work Pools

!!! note "Prefect Cloud"
    This tutorial uses Prefect Cloud to deploy flows to work pools.
    Managed execution and push work pools are available in [Prefect Cloud](https://www.prefect.io/cloud) only.
    If you are not using Prefect Cloud, please learn about work pools below and then proceed to the [next tutorial](/tutorial/workers/) that uses worker-based work pools.

## Why work pools?

Work pools are a bridge between the Prefect orchestration layer and infrastructure for flow runs that can be dynamically provisioned.
To transition from persistent infrastructure to dynamic infrastructure, use `flow.deploy` instead of `flow.serve`.

!!! tip "[Choosing Between `flow.deploy()` and `flow.serve()`](/concepts/deployments/#two-approaches-to-deployments)"
    Earlier in the tutorial you used `serve` to deploy your flows.
    For many use cases, `serve` is sufficient to meet scheduling and orchestration needs.
    Work pools are **optional**.
    If infrastructure needs escalate, work pools can become a handy tool.
    The best part?
    You're not locked into one method.
    You can seamlessly combine approaches as needed.

!!! note "Deployment definition methods differ slightly for work pools"
    When you use work-pool-based execution, you define deployments differently.
    Deployments for workers are configured with `deploy`, which requires additional configuration.
    A deployment created with `serve` cannot be used with a work pool.

The primary reason to use work pools is for **dynamic infrastructure provisioning and configuration**.
For example, you might have a workflow that has expensive infrastructure requirements and is run infrequently.
In this case, you don't want an idle process running within that infrastructure.

Other advantages to using work pools include:

- You can configure default infrastructure configurations on your work pools that all jobs inherit and can override.
- Platform teams can use work pools to expose opinionated (and enforced!) interfaces to the infrastructure that they oversee.
- Work pools can be used to prioritize (or limit) flow runs through the use of [work queues](/concepts/work-pools/#work-queues).

Prefect provides several [types of work pools](/concepts/work-pools/#work-pool-types).
Prefect Cloud provides a Prefect Managed work pool option that is the simplest way to deploy remote workflows.
A cloud-provider account, such as AWS, is not required with a Prefect Managed work pool.

## Set up a work pool

### Create a Prefect Managed work pool

In your terminal, run the following command to set up a work pool named `my-managed-pool` of type `prefect:managed`.

<div class="terminal">

```bash
prefect work-pool create my-managed-pool --type prefect:managed 
```

</div>

Let’s confirm that the work pool was successfully created by running the following command.

<div class="terminal">

```bash
prefect work-pool ls
```

</div>

You should see your new `my-managed-pool` in the output list.

Finally, let’s double check that you can see this work pool in the UI.

Navigate to the **Work Pools** tab and verify that you see `my-managed-pool` listed.

Feel free to select **Edit** from the three-dot menu on right of the work pool card to view the details of your work pool.

Work pools contain configuration that is used to provision infrastructure for flow runs.
For example, you can specify additional Python packages or environment variables that should be set for all deployments that use this work pool.
Note that individual deployments can override the work pool configuration.

Now that you’ve set up your work pool, we can create a deployment that is tied to this work pool.
Let's deploy your tutorial flow to `my-managed-pool`.

## Create the deployment

From our previous steps, we now have:

1. [A flow](/tutorial/flows/)
2. A work pool

Let's update our `repo_info.py` file to create a deployment in Prefect Cloud.

The updates that we need to make to `repo_info.py` are:

1. Change `flow.serve` to `flow.deploy`.
2. Tell `flow.deploy` which work pool to deploy to.

Here's what the updated `repo_info.py` looks like:

```python hl_lines="17-23" title="repo_info.py"
import httpx
from prefect import flow


@flow(log_prints=True)
def get_repo_info(repo_name: str = "PrefectHQ/prefect"):
    url = f"https://api.github.com/repos/{repo_name}"
    response = httpx.get(url)
    response.raise_for_status()
    repo = response.json()
    print(f"{repo_name} repository statistics 🤓:")
    print(f"Stars 🌠 : {repo['stargazers_count']}")
    print(f"Forks 🍴 : {repo['forks_count']}")


if __name__ == "__main__":
    get_repo_info.from_source(
        source="TK https://github.com/desertaxle/demo.git", 
        entrypoint="flow.py:my_flow")
    .deploy(
        name="my-first-deployment", 
        work_pool_name="my-managed-pool", 
    )
```

In the `from_source` method, we specify the source of our flow code.

You can store your flow code in any of several types of remote storage.
In this example, we use a GitHub repository, but you could use a Docker image, as you'll see in an upcoming section of the tutorial.
Alternatively, you could store your flow code in cloud provider storage such as AWS S3, or within a different git-based cloud provider such as GitLab or Bitbucket.

!!! note
    In the example above, we store our code in a GitHub repository.
    If you make changes to the flow code, you will need to push those changes to your own GitHub account and update the `source` argument of `from_source` to point to your repository.

In the `deploy` method, we specify the name of our deployment and the name of the work pool that we created earlier.

Run the script again and you should see a message in the CLI that your deployment was created with instructions for how to run it.

Navigate to your Prefect Cloud UI and view your new deployment.
Click the "Run" button to trigger a run of your deployment.

Because this deployment was configured with a Prefect Managed work pool, Prefect Cloud will run your flow on your behalf.

View the logs in the UI.

Now that you've updated your script, you can run it to register your deployment on Prefect Cloud:

<div class="terminal">

```bash
python repo_info.py
```

</div>

Now everything is set up for us to submit a flow-run to the work pool:

<div class="terminal">

```bash
prefect deployment run 'get_repo_info/my-deployment'
```

</div>

Prefect Managed work pools are a great way to get started with work pools.

Many users will find that they need more control over the infrastructure that their flows run on.
Prefect Cloud's push work pools are a great option in cases where you need more control over your infrastructure.

## Push work pools with automatic infrastructure provisioning

Serverless push work pools scale infinitely and are a great option for many production workloads.

Setting up the cloud provider pieces for infrastructure can be tricky and time consuming.

Fortunately, Prefect can automatically provision infrastructure for you and wire it all together.

### Create a push work pool

In your terminal, run the following command to set up a **push work pool*.
We'll use AWS for this example.

<div class="terminal">

```bash

```

</div>

See the [Push Work Pool guide](/guides/push-work-pools/) for more details.

## Next step

- Learn how to use work pools that rely on a worker in the [next section of the tutorial](/tutorial/workers/).
    Kubernetes and serverless non-push work pools are popular options.
