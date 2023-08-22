---
description: Learn how Prefect flow deployments enable configuring flows for scheduled and remote execution.
tags:
    - work pools
    - workers
    - orchestration
    - flow runs
    - deployments
    - schedules
    - triggers
    - tutorial
search:
  boost: 2
---
# Deploying Flows

## Why Deploy?

One of the most common reasons to use a tool like Prefect is [scheduling](/concepts/schedules). You want your flows running on production infrastructure in a consistent and predictable way. Up to this point, we’ve demonstrated running Prefect flows as scripts, but this means *you* have been the one triggering flow runs. In order to schedule flow runs or trigger them based on [events](/cloud/events/) or certain conditions, you’ll need to [deploy](/concepts/deployments/) them.

A deployed flow can be interacted with in additional ways:

- you can trigger runs on remote + configurable infrastructure
- you can trigger runs via schedules, the UI, Webhooks/Automations, or the REST API over HTTP
- you can trigger runs with custom parameters via any of the above methods

## What is a Deployment?

Deploying a flow is the act of specifying where, when, and how it will run. This information is encapsulated and sent to Prefect as a [Deployment](/concepts/deployments/) which contains the crucial metadata needed for orchestration. Deployments elevate workflows from functions that you call manually to API-managed entities.

Attributes of a deployment include (but are not limited to):

- __Flow entrypoint__: path to your flow function would start the flow
- __Work pool__: points to the infrastructure you want your flow to run in
- __Schedule__: optional schedule for this deployment
- __Tags__: optional text labels for organizing your deployments

Before you build your first deployment, its helpful to understand how Prefect configures flow run infrastructure. This means setting up a work pool and a worker to enable **your flows** to run on **your infrastructure**.

## Why Work Pools and Workers?

Running Prefect flows locally is great for testing and development purposes. But for production settings, Prefect work pools and workers allow you to run flows in the environments best suited to their execution.

Workers and work pools bridge the Prefect orchestration layer with the infrastructure the flows are actually executed on.

Work pools prioritize flow runs and respond to polling from the worker. Workers are light-weight processes that run in the environment where flow runs are executed.

You can create and configure work pools within the Prefect UI.

**Work Pools:**

- Respond to polling from workers
- Organize and prioritize the flow runs for a worker to pick up and execute
- Describe the ephemeral infrastructure configuration that the worker will create for each flow run

```mermaid
graph TD

    subgraph your_infra["Your Execution Environment"]
        worker["Worker"]
				subgraph flow_run_infra[Flow Run Infra]
					flow_run(("Flow Run"))
				end
        
    end

    subgraph api["Prefect API"]
				Deployment --> |assigned to| work_pool
        work_pool(["Work Pool"])
    end

    worker --> |polls| work_pool
    worker --> |creates| flow_run_infra
```

!!! note "Security Note:"
    Prefect provides execution through the hybrid model, which allows you to deploy workflows that run in the environments best suited to their execution while allowing you to keep your code and data completely private. There is no ingress required. For more information see [here.](https://www.prefect.io/security/overview/#overview)

Now that we’ve reviewed the concepts of a Work Pool and Worker, let’s create them so that you can deploy your tutorial flow, and execute it later using the Prefect API.

## Setting up the Worker and Work Pool

For this tutorial you will create a **Process** type work pool via the CLI. 

The **Process** work pool type specifies that all work sent to this work pool will run as a subprocess on the same infrastructure on which the worker is running.

!!! tip "Other work pool types"
    There are work pool types for all major managed code execution platforms, such as Kubernetes services or serverless computing environments such as AWS ECS, Azure Container Instances, and GCP Cloud Run.
    
    These are expanded upon in the [Guides](/guides) section.

In your terminal run the following command to set up a **Process** type work pool. 
<div class="terminal">
```bash
prefect work-pool create --type process my-process-pool
```
</div>
Let’s confirm that the work pool was successfully created by running the following command in the same terminal. You should see your new `my-process-pool` in the output list.
<div class="terminal">
```bash
prefect work-pool ls 
```
</div>
Finally, let’s double check that you can see this work pool in the Prefect Cloud UI. Navigate to the Work Pool tab and verify that you see `my-process-pool` listed.

<div class="terminal">
```bash
                                             Work Pools                                             
┏━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━┓
┃ Name                  ┃ Type          ┃                                   ID ┃ Concurrency Limit ┃
┡━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━┩
│ my-process-pool       │ process       │ 33ce63a5-cc80-4f43-9092-11122ccea60b │ None              │
└───────────────────────┴───────────────┴──────────────────────────────────────┴───────────────────┘
```
</div>
When you click into the `my-process-pool`, select the "Work Queues" tab. You should see a red status icon listed for the default work queue signifying that this queue is not ready to submit work. Work queues are an advanced feature. You can learn more about them in the [work queue documentation.](/concepts/work-pools/#work-queues) 

To get the work queue healthy and ready to submit flow runs, you need to start a worker.

Workers are a lightweight polling process that kick off scheduled flow runs on a certain type of infrastructure (like Process). To start a worker on your laptop, open a new terminal and confirm that your virtual environment has `prefect` installed.

Run the following command in this new terminal to start the worker:
<div class="terminal">
```bash
prefect worker start --pool my-process-pool
```
</div>
You should see the worker start - it's now polling the Prefect API to request any scheduled flow runs it should pick up and then submit for execution. You’ll see your new worker listed in the UI under the worker tab of the Work Pool page with a recent last polled date. You should also be able to see a `Healthy` status indicator in the default work queue under the work queue tab.

You would need to keep this terminal session active in order for the worker continue to pick up jobs. Since you are running this worker locally, the worker will terminate if you close the terminal. Therefore, in a production setting this worker should be running as a daemonized or managed process. See next steps for more information on this.

Now that we’ve set up your work pool and worker, we have what we need to kick off and execute flow runs of deployed flows. Lets deploy your tutorial flow to `my-process-pool`.

## Create a Deployment

### From our previous steps, we now have:

1. A flow
2. A work pool
3. A worker
4. An understanding of why Prefect Deployments are useful

Now it’s time to put it all together.

In your terminal (not the terminal in which the worker is running), let’s run the following command ***from the root of your repo*** to begin deploying your flow:

<div class="terminal">
```bash
prefect deploy
```
</div>

!!! tip "Specifying an entrypoint"
    In non-interactive settings (like CI/CD), you can specify the entrypoint of your flow directly in the CLI. 
    
    For example, if `my_flow` is defined in `my_flow.py`, provide deployment details with flags `prefect deploy my_flow.py:my_flow -n my-deployment -p my-pool`.

When running `prefect deploy` interactively, the CLI will discover all flows in your working directory. Select the flow you want to deploy, and the deployment wizard will walk you through the rest of the deployment creation process:

1. **Deployment name**: Choose a name, like `my-deployment`
2. **Would you like to schedule when this flow runs? (y/n):** Type `n` for now, you can set up a schedule later
3. **Which work pool would you like to deploy this flow to? (use arrow keys):** Select the work pool you just created, `my-process-pool`
4. When asked if you would like your workers to pull your flow code from its remote repository, select yes if you’ve been following along and defining your flow code script from within a GitHub repository:
    - __`y`__ (***Recommended***): Prefect will automatically register your GitHub repo as the the remote location of this flow’s code. This means a worker started on any machine (for example: on your laptop, on your team-mate’s laptop, or in a cloud VM) will be able to facilitate execution of this deployed flow.
    - __`n`__: If you would like to continue this tutorial without the use of GitHub, thats ok, Prefect will always first look to see if the flow code exists locally before referring to remote flow code storage, so your local `my-process-pool` should have all it needs to complete the execution of this deployed flow.

!!! danger "Common Pitfalls"
    - When running `prefect deploy` or `prefect init` commands, double check that you are at the **root of your repo**, otherwise the worker may attempt to use an incorrect flow entrypoint during remote execution!
    - Ensure that you have pushed any changes to your flow script to your GitHub repo - at any given time, your worker will pull the code that exists there!
 

As you continue to use Prefect, you'll likely author many different flows and deployments of them. Check out the next section to learn about defining deployments in a `prefect.yaml` file.

!!! tip "Did you know?"
    A Prefect flow can have more than one deployment. This can be useful if you want your flow to run in different execution environments or have multiple different schedules.

## Next Steps

- Learn about deploying multiple flows and CI/CD with our [`prefect.yaml`](/concepts/projects/#the-prefect-yaml-file)
- Check out some of our other [work pools](/concepts/work-pools/)
- [Concepts](/concepts/) contain deep dives into Prefect components.
- [Guides](/guides/) provide step by step recipes for common Prefect operations including:
    - [Deploying on Kubernetes](/guides/deployment/helm-worker/)
    - [Deploying flows in Docker](/guides/deployment/docker/)
    - [Writing tests](/guides/testing)
      
And more!
