# Flow deployments

!!! tip "This tutorial relies on stateful Orion services"
    This tutorial relies on stateful services such as the Orion agent and the Orion scheduler to work properly.  

    Please begin by running `prefect orion start` within your terminal:
    <div class="termy">
    ```
    $ prefect orion start

    Starting Orion API...
    INFO:     Started server process [91744]
    INFO:     Waiting for application startup.
    13:58:06.102 | Agent service scheduled to start in-app
    13:58:06.102 | Scheduler service scheduled to start in-app
    13:58:06.102 | MarkLateRuns service scheduled to start in-app
    INFO:     Application startup complete.
    INFO:     Uvicorn running on http://127.0.0.1:4200 (Press CTRL+C to quit)
    ```
    </div>

## Deployments

Flow deployments elevate workflows from functions that users call manually to API-managed entities. Specifically, deployments contain all of the information necessary for scheduling a workflow and / or triggering it via API call.  Moreover, because a flow can have multiple distinct deployments, deployments allow for easily testing multiple versions of a flow and promoting them through various environments.

A **deployment** consists of the following pieces of required information:

- a `name`
- a `flow_location`, or the path to a flow definition; currently flow scripts must be located on the same filesystem as the Orion server

and may additionally include the following pieces of optional information:

- a set of `tags` to attach to the runs generated from this deployment
- a set of `parameters` whose values will be passed to the flow function when it runs
- a `schedule` for auto-generating flow runs on some well defined cadence

To create a deployment, we need to define a **deployment spec** and then register that spec with the Orion server; for example, suppose we have the following two files located in `/Developer/workflows/`:

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
    from prefect.client import OrionClient

    async with OrionClient() as client:
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
- [`CronSchedule`][prefect.orion.schemas.schedules.CronSchedule]: best suited for users who are already familiar with `cron` from use in other systems
- [`RRuleSchedule`][prefect.orion.schemas.schedules.RRuleSchedule]: best suited for deployments that rely on calendar logic such as irregular intervals, exclusions and day-of-month adjustments

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
