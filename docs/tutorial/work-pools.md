---
description: Learn how Prefect deployments can be configured for scheduled and remote execution with work pools.
tags:
    - work pools
    - orchestration
    - flow runs
    - deployments
    - tutorial
search:
  boost: 2
---

# Work Pools

This part of the tutorial covers handling more complex and dynamic infrastructure requirements for your workflows using  [Prefect Cloud](https://www.prefect.io/cloud); alternatively, if you aren't using Prefect Cloud, see [Worker-based work pools](/tutorial/workers/). For simpler use cases, see [Deploying flows](/tutorial/deployments/).

## Key concepts

* Work pool: An optional configuration that defines the infrastructure for executing flow runs. You can change these configurations as your infrastructure needs change.
* Infrastructure block: Defines the specific infrastructure configuration that a work pool (such as a container image, Kubernetes manifest) uses.
* Prefect-managed work pools are a great way to get started with Prefect and run workflows remotely. You don't need a cloud-provider account, such as AWS, with a Prefect-managed work pool.

### When to use work pools

While the [`flow.serve()` method](/tutorial/deployments/) is sufficient for basic scheduling and orchestration needs, work pools are helpful for the following:

* Scaling infrastructure: Adapting execution infrastructure to workload demands.
* Isolation and security: Running flow runs in dedicated environments for enhanced security.
* Resource optimization: Dynamically provisioning infrastructure only when needed, optimizing resource utilization.

## Set up work pools

Create a Prefect-managed work pool named `my-managed-pool` of the `prefect:managed` type:

<div class="terminal">

```bash
prefect work-pool create my-managed-pool --type prefect:managed 
```

</div>

Confirm creation of the work pool by running the following command:

<div class="terminal">

```bash
prefect work-pool ls
```

</div>

You should see your new `my-managed-pool` in the output list.

## See work pools in the UI

1. Navigate to the **Work Pools** tab and verify that you see `my-managed-pool`.

1. Select **Edit** from the three-dot menu on right of the work pool card to view the details of your work pool.

    For example, you can specify additional Python packages or environment variables that should be set for all deployments that use this work pool.
    Individual deployments can override the work pool configuration.


## Create the deployment

Deploy a flow to the `my-managed-pool` work pool by updating our `repo_info.py` file to create a deployment in Prefect Cloud:

1. Change `flow.serve` to `flow.deploy`.

    When using work-pool-based execution, you can't use a `flow.serve` deployment.

1. In the `from_source` method, specify the source of our flow code.
1. Specify which work pool to deploy to in `flow.deploy`.

The following example uses a GitHub repository to store your flow code, but you can use any of several types of remote storage. Here's what its `repo_info.py` file looks like:

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
        source="https://github.com/discdiver/demos.git", 
        entrypoint="repo_info.py:get_repo_info"
    ).deploy(
        name="my-first-deployment", 
        work_pool_name="my-managed-pool", 
    )
```

If you make changes to the flow code, you need to push those changes to your own GitHub account and update the `source` argument of `from_source` to point to your repository.

## Register the deployment

After updating your script, run it to register your deployment on Prefect Cloud:

<div class="terminal">

```bash
python repo_info.py
```

</div>

You should see a message in the CLI that your deployment was created with instructions for how to run it:

<div class="terminal">

```bash
Successfully created/updated all deployments!

                       Deployments                       
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━┳━━━━━━━━━┓
┃ Name                              ┃ Status  ┃ Details ┃
┡━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━╇━━━━━━━━━┩
│ get-repo-info/my-first-deployment | applied │         │
└───────────────────────────────────┴─────────┴─────────┘

To schedule a run for this deployment, use the following command:

        $ prefect deployment run 'get-repo-info/my-first-deployment'


You can also run your flow via the Prefect UI: https://app.prefect.cloud/account/
abc/workspace/123/deployments/deployment/xyz
```

</div>

## Schedule a deployment run

Now everything is set up for us to submit a flow-run to the work pool, using one of the following options:

* Use the CLI:

    <div class="terminal">

    ```bash
    prefect deployment run 'get_repo_info/my-deployment'
    ```

    </div>

* Use the UI, by navigating to your Prefect Cloud UI and viewing your new deployment. Click **Run** to trigger a run of your deployment that Prefect Cloud runs on your behalf.

    View the logs in the UI.

For more details on using Prefect-managed work pools, see [Managed Execution guide](/guides/managed-execution/).


## Customize more granular infrastructure control

For users requiring greater infrastructure control, Prefect Cloud offers push work pools. These serverless options:

* Scale infinitely.
* Provide more configuration options than Prefect-managed work pools.
* Support AWS ECS on Fargate, Azure Container Instances, Google Cloud Run, and Modal.

While setting up cloud provider infrastructure can be complex, Prefect can automate provisioning and integration for a seamless experience. The following example uses Google Cloud.

### Before you begin

1. To build and push images to your registry, install [Docker](https://docs.docker.com/get-docker/).
1. Install the [gcloud CLI](https://cloud.google.com/sdk/docs/install) or update to the latest version with `gcloud components update`.
1. [Authenticate with your GCP project](https://cloud.google.com/docs/authentication/gcloud).
1. Ensure you have the following permissions in your GCP project:

    - `resourcemanager.projects.list`
    - `serviceusage.services.enable`
    - `iam.serviceAccounts.create`
    - `iam.serviceAccountKeys.create`
    - `resourcemanager.projects.setIamPolicy`
    - `artifactregistry.repositories.create`

### Create a push work pool

1. Set up a push work pool named `my-cloud-run-pool` of type `cloud-run:push` that creates a [`GCPCredentials` block](https://prefecthq.github.io/prefect-gcp/credentials/) for storing the service account key:

    <div class="terminal">

    ```bash
    prefect work-pool create --type cloud-run:push --provision-infra my-cloud-run-pool 
    ```

    </div>

    Using the `--provision-infra` flag allows you to select a GCP project to use for your work pool and automatically configures it to be ready to execute flows via Cloud Run.
    In your GCP project, this command activates the Cloud Run API, creates a service account, and creates a key for the service account, if they don't already exist.

    Here's an abbreviated example output from running the command:

    <div class="terminal">

    ```bash
    ╭──────────────────────────────────────────────────────────────────────────────────────────────────────────╮
    │ Provisioning infrastructure for your work pool my-cloud-run-pool will require:                           │
    │                                                                                                          │
    │     Updates in GCP project central-kit-405415 in region us-central1                                      │
    │                                                                                                          │
    │         - Activate the Cloud Run API for your project                                                    │
    │         - Activate the Artifact Registry API for your project                                            │
    │         - Create an Artifact Registry repository named prefect-images                                    │
    │         - Create a service account for managing Cloud Run jobs: prefect-cloud-run                        │
    │             - Service account will be granted the following roles:                                       │
    │                 - Service Account User                                                                   │
    │                 - Cloud Run Developer                                                                    │
    │         - Create a key for service account prefect-cloud-run                                             │
    │                                                                                                          │
    │     Updates in Prefect workspace                                                                         │
    │                                                                                                          │
    │         - Create GCP credentials block my--pool-push-pool-credentials to store the service account key   │
    │                                                                                                          │
    ╰──────────────────────────────────────────────────────────────────────────────────────────────────────────╯
    Proceed with infrastructure provisioning? [y/n]: y
    Activating Cloud Run API
    Activating Artifact Registry API
    Creating Artifact Registry repository
    Configuring authentication to Artifact Registry
    Setting default Docker build namespace
    Creating service account
    Assigning roles to service account
    Creating service account key
    Creating GCP credentials block
    Provisioning Infrastructure ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 100% 0:00:00
    Infrastructure successfully provisioned!
    Created work pool 'my-cloud-run-pool'!
    ```

    </div>

1. Authenticate into your new Artifact Registry repository and the default Docker build namespace sets to the URL of the repository.

1. Specify a registry or username/organization pushes to the repository by writing your deploy script like the following. Make sure you have Docker running locally before running this script:

    ```python hl_lines="14" title="example_deploy_script.py"
    from prefect import flow                                                       
    from prefect.deployments import DeploymentImage                                


    @flow(log_prints=True)
    def my_flow(name: str = "world"):
        print(f"Hello {name}! I'm a flow running on Cloud Run!")


    if __name__ == "__main__":                                                     
        my_flow.deploy(                                                            
            name="my-deployment",
            work_pool_name="above-ground",
            cron="0 1 * * *",
            image=DeploymentImage(
                name="my-image:latest",
                platform="linux/amd64",
            )
        )
    ```

    This script accomplishes the following:

    * Creates a deployment on the Prefect Cloud server.
    * Builds a Docker image with the tag `<region>-docker.pkg.dev/<project>/<repository-name>/my-image:latest` and pushes it to your repository.
    * If you're building your image on a machine with an ARM-based processor, you only need to include an object of the `DeploymentImage` class with the `platform="linux/amd64` argument. Otherwise, you could just pass `image="my-image:latest"` to `deploy`.
    * The `cron` argument schedules the deployment to run at 1 AM every day. For information on scheduling options, see [schedules](/concepts/schedules/).

For more details and example commands for each cloud provider, see the [Push Work Pool guide](/guides/deployment/push-work-pools/).

## Next steps

Congratulations! You've learned how to deploy flows to work pools.
If these work pool options meet all of your needs, dive deeper with [Concepts](/concepts/) or explore [How-to guides](/guides/) to see examples of particular Prefect use cases.

However, if you need more control over your infrastructure, want to run your workflows in Kubernetes, or are running a self-hosted Prefect server instance, see the [Workers tutorial](/tutorial/workers/).