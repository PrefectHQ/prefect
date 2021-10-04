# Flow deployments

!!! tip "This tutorial relies on stateful Orion services"
    This tutorial relies on stateful services such as the Orion agent and the Orion scheduler to work properly.  

    Please begin by running `prefect orion start` within your terminal:
    <div class="termy">
    ```
    $ prefect orion start
    Starting Orion API...
    INFO:     Application startup complete.
    INFO:     Uvicorn running on http://127.0.0.1:4200 (Press CTRL+C to quit)
    ```
    </div>

## Deployments

Flow deployments elevate a workflow from a function that users call manually to an API managed entity. Specifically, deployments contain all of the information necessary for scheduling a workflow and / or triggering it via API call.  Moreover, because a flow can have multiple distinct deployments, deployments allow for easily testing multiple versions of a flow and promoting them through various environments.

A **deployment** consists of the following pieces of required information:

- a name
- the path to a flow definition; currently flow scripts must be located on the same filesystem as the Orion server

and may additionally include the following pieces of optional information:

- a set of `tags` to attach to the runs generated from this deployment
- a set of parameter values to pass to the flow function as parameters
- a schedule for auto-generating flow runs on some well defined cadence

To create a deployment, we need to define a _deployment spec_ and then register that spec with the Orion server; for example, suppose we have the following two files located in `/Developer/workflows/`:

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

    DeploymentSpec(
        flow_location="/Developer/workflows/my_flow.py",
        name="my-first-deployment",
        parameters={"nums": "[1, 2, 3, 4]"}, 
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
    ![](/img/tutorials/first-steps-ui.png){: max-width=600px}
    </figure>

=== "my_flow_deployment.py"

    Our workflow deployment specification.
    
    ```python
    from prefect.deployments import DeploymentSpec

    DeploymentSpec(
        flow_location="/Developer/workflows/my_flow.py",
        name="my-first-deployment",
        parameters={"nums": "[1, 2, 3, 4]"}, 
    )
    ```

### Additional Configuration

- multiple ways of specifying the deployment
- multiple deployments per flow, tracked via `version` 

## Schedules

Now that you have seen how to create a deployment, 

Three schedule classes, and two ways of defining schedules (YAML and Python).


!!! tip "Additional Reading"
    To learn more about the concepts presented here, check out the following resources:

    - [Deployment Specs](/api-ref/prefect/deployments/)
    - [Deployments](/concepts/deployments/)
    - [Schedules](/concepts/schedules/)
