---
description: Creating flow deployments and running them with work queues and agents.
tags:
    - Orion
    - work queues
    - agents
    - orchestration
    - flow runs
    - deployments
    - schedules
    - tutorial
---

# Deployments

In the tutorials leading up to this one, you've been able to explore Prefect capabilities like flows, tasks, retries, caching, using task runners to execute tasks sequentially, concurrently, or even in parallel. But so far you've run flows pretty much as scripts. 

_Deployments_ take your flows to the next level: deployments add the information needed for scheduling a flow run or triggering it via an API call. Deployments elevate workflows from functions that users call manually to API-managed entities.

Moreover, because a flow can have multiple distinct deployments, deployments allow for easily testing multiple versions of a flow and promoting them through various environments.

## Components of a deployment

You need just a few ingredients to turn a flow definition into a deployment:

- A flow
- A deployment specification

That's it. To create flow runs based on the deployment, you need a few more pieces:

- Prefect Orion server
- A work queue
- An agent

These all come with Prefect. You just have to configure them and set them to work.

## From flow to deployment

As noted earlier, the first ingredient of a deployment is a flow. You've seen a few of these already, and perhaps have written a few if you've been following the tutorials. 

Let's start with a simple example:

```python
from prefect import flow, task, get_run_logger

@task
def log_message(name):
    logger = get_run_logger()
    logger.info(f"Hello {name}!")
    return

@flow(name="leonardo_dicapriflow")
def leonardo_dicapriflow(name: str):
    log_message(name)
    return

leonardo_dicapriflow("Leo")
```

Save this in a file `leo_flow.py` and run it as a Python script. You'll see output like this:

<div class="termy">
```
$ python leo_flow.py
20:49:47.730 | INFO    | prefect.engine - Created flow run 'rare-frog' for flow 'leonardo_dicapriflow'
20:49:47.731 | INFO    | Flow run 'rare-frog' - Using task runner 'ConcurrentTaskRunner'
20:49:47.791 | INFO    | Flow run 'rare-frog' - Created task run 'log_message-dd6ef374-0' for task 'log_message'
20:49:47.839 | INFO    | Task run 'log_message-dd6ef374-0' - Hello Leo!
20:49:47.887 | INFO    | Task run 'log_message-dd6ef374-0' - Finished in state Completed(None)
20:49:48.204 | INFO    | Flow run 'rare-frog' - Finished in state Completed('All states completed.')
```
</div>

Okay, but it's still a static script, much like our previous flow examples. Let's take this script and turn it into a deployment by creating a deployment specification.

## Deployment specifications

A [deployment specification](/concepts/deployments/#deployment-specifications) includes the settings that will be used to create a deployment in the Orion database. It consists of the following pieces of required information:

- The deployment `name`
- The `flow_location`, or the path to a flow definition

You can additionally include the following pieces of optional information:

- `tags` to attach to the runs generated from this deployment
- `parameters` whose values will be passed to the flow function when it runs
- a `schedule` for auto-generating flow runs

To create the deployment specification, import `DeploymentSpec`, then define a `DeploymentSpec` object as either Python or YAML code. For this example, define it as Python in the same `leo_flow.py` file as the flow. 

```python hl_lines="2 14-18"
from prefect import flow, task, get_run_logger
from prefect.deployments import DeploymentSpec

@task
def log_message(name):
    logger = get_run_logger()
    logger.info(f"Hello {name}!")
    return

@flow(name="leonardo_dicapriflow")
def leonardo_dicapriflow(name: str):
    log_message(name)
    return

DeploymentSpec(
    flow=leonardo_dicapriflow,
    name="leonardo__deployment",
    tags=['tutorial','test'],
)
```



To create a deployment, you define the deployment specification and then use that with the Orion server; for example, suppose we have the following two files located in `/Developer/workflows/`:

=== "my_flow.py"

    The definition of our workflow.

    ```python
    from prefect import flow, task
    from typing import List


    @task
    def add_numbers(nums):
        return sum(nums)

    @flow(name="Addition Machine")
    def calculator(nums: List[int]):
        return add_numbers(nums)
    ```

    !!! note "Type Hints"
        Note that we are using type hints to ensure typing compatibility between the API and Python. 

=== "my_flow_deployment.py"

    Our workflow deployment specification.
    
    ```python
    from prefect.deployments import DeploymentSpec

    # note that deployment names are 
    # stored and referenced as '<flow name>/<deployment name>'
    DeploymentSpec(
        flow_location="/Developer/workflows/my_flow.py",
        name="my-first-deployment",
        parameters={"nums": [1, 2, 3, 4]}, 
    )
    ```

We can then use the `prefect` CLI to register this deployment with the Orion server:

<div class="termy">
```
$ prefect deployment create ./my_flow_deployment.py
Loading deployments from python script at <span style="color: green;">'my_flow_deployment.py'</span>...
Created deployment <span style="color: green;">'my-first-deployment'</span> for flow <span style="color: green;">'Addition Machine'</span>
```
</div>

Now that the deployment is created, we can interact with it in multiple ways (click through the tabs to see the various options!):

=== "The Dashboard"

    Navigate to your dashboard and you should see your newly created deployment under the "Deployments" tab; clicking "Quick Run" will trigger immediate execution!

    <figure markdown=1>
    ![](/img/tutorials/my-first-deployment.png){: max-width=600px}
    </figure>

=== "The CLI"

    The same CLI that we used to create the deployment can be used to execute it; note that the CLI expects the name to be provided as 'Full Flow Name/Full Deployment Name':
    
    <div class="termy">
    ```
    $ prefect deployment execute 'Addition Machine/my-first-deployment'
    11:56:10.440 | Beginning flow run 'feathered-silkworm' for flow 'Addition Machine'...
    ```
    </div>

=== "The REST API"

    We can additionally use the REST API directly; to faciliate this, we will demonstrate how this works with the convenient Python Orion Client:
    
    ```python
    from prefect.client import get_client

    async with get_client() as client:
        deployment = await client.read_deployment_by_name("Addition Machine/my-first-deployment")
        flow_run = await client.create_flow_run_from_deployment(deployment)
    ```

    Note that the return values of these methods are full model objects.

As you can see above, deployments allow you to interact with this workflow and its associated configuration via automated services; runs created in this way are always submitted and managed by the Orion agent. 

!!! tip "Managing Multiple Deployments"

    Now that you've created one deployment, why stop there?  You can associate any number of deployments to your flows; the runs they generate will be associated with the corresponding deployment ID for easy discovery in the dashboard.  Additionally, using metadata such as flow `version`s provides another dimension for you to bookkeep and filter in your Orion dashboard.

## Schedules

Deployments can additionally have schedules that automate the creation of flow runs based on clock time.  Prefect currently supports three schedule types:

- [`IntervalSchedule`][prefect.orion.schemas.schedules.IntervalSchedule]: best suited for deployments that need to run at some consistent cadence that isn't related to absolute time 
- [`RRuleSchedule`][prefect.orion.schemas.schedules.RRuleSchedule]: best suited for deployments that rely on calendar logic such as irregular intervals, exclusions and day-of-month adjustments
- [`CronSchedule`][prefect.orion.schemas.schedules.CronSchedule]: best suited for users who are already familiar with `cron` from use in other systems

For example, suppose we wanted to run our first deployment above every 15 minutes; we can alter our deployment spec as follows:
```python hl_lines="2-3 9"
from prefect.deployments import DeploymentSpec
from prefect.orion.schemas.schedules import IntervalSchedule
from datetime import timedelta

DeploymentSpec(
    flow_location="/Developer/workflows/my_flow.py",
    name="my-first-deployment",
    parameters={"nums": [1, 2, 3, 4]}, 
    schedule=IntervalSchedule(interval=timedelta(minutes=15)),
)
```

and rerun our `prefect deployment create` CLI command to update the deployment.

Once the deployment has been updated with a schedule, the Orion scheduler will proceed scheduling future runs that are inspectable in your dashboard.

!!! tip "Additional Reading"
    To learn more about the concepts presented here, check out the following resources:

    - [Deployment Specs](/api-ref/prefect/deployments/)
    - [Deployments](/concepts/deployments/)
    - [Schedules](/concepts/schedules/)
