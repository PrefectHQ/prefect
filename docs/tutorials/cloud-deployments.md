---
description: Create and run Prefect flow deployments with Prefect Cloud.
tags:
    - Prefect Cloud
    - work queues
    - agents
    - orchestration
    - flow runs
    - deployments
    - schedules
    - tutorial
---

# Flow deployments with Prefect Cloud

## Run a flow from a deployment

[Deployments](/concepts/deployments/) are flows packaged in a way that let you run them directly from the Prefect Cloud UI, either ad-hoc runs or via a schedule.

To run a flow from a deployment with Prefect Cloud, you'll need to:

- Create a flow script
- Create the deployment using the Prefect CLI
- Start an agent in your execution environment
- Run your deployment to create a flow run

### Configure storage 

For the Prefect Cloud quickstart, we'll use local storage. You don't need to set up any remote storage to complete this tutorial. 

When using Prefect Cloud in production, we recommend configuring remote storage. Storage is used to make flow scripts available when creating flow runs via API in remote execution environments. Storage is also used for persisting flow and task data. See [Storage](/concepts/storage/) for details.

By default, Prefect uses local file system storage to persist flow code and flow and task results. For local development and testing this may be adequate. Be aware, however, that local storage is not guaranteed to persist data reliably between flow or task runs, particularly when using container-based environments such as Docker or Kubernetes, or when executing tasks with distributed computing tools like Dask and Ray.

### Create a deployment

Let's go back to your flow code in `basic_flow.py`. In a terminal, run the `prefect deployment build` Prefect CLI command to build a manifest JSON file and deployment YAML file that you'll use to create the deployment on Prefect Cloud.

<div class="terminal">
```bash
$ prefect deployment build ./basic_flow.py:basic_flow -n test-deployment -q test
```
</div>

What did we do here? Let's break down the command:

- `prefect deployment build` is the Prefect CLI command that enables you to prepare the settings for a deployment.
-  `./basic_flow.py:basic_flow` specifies the location of the flow script file and the name of the entrypoint flow function, separated by a colon.
- `-n test-deployment` is an option to specify a name for the deployment.
- `-q test` specifies a work queue for the deployment. The deployment's runs will be sent to any agents monitoring this work queue.

The command outputs `basic_flow-deployment.yaml`, which contains details about the deployment for this flow.

### Create the deployment

In the terminal, use the `prefect deployment apply` command to apply the settings contained in the manifest and `deployment.yaml` to create the deployment on Prefect Cloud.

Run the following Prefect CLI command.

<div class="terminal">
```bash
$ prefect deployment apply basic_flow-deployment.yaml
Successfully loaded 'test-deployment'
Deployment '66b3fdea-cd3a-4734-b3f2-65f6702ff260' successfully created.
```
</div>

Now your deployment has been created and is ready to orchestrate future `Testing` flow runs.

To demonstrate that your deployment exists, go back to Prefect Cloud and select the **Deployments** page. You'll see the 'Testing/Test Deployment' deployment was created.

!['Testing/Test Deployment' appears in the Prefect Cloud Deployments page](/img/ui/cloud-test-deployment.png)

### Create a work queue and agent

Next, we start an agent that can pick up the flow run from your 'Testing/Test Deployment' deployment. Remember that when we created the deployment, it was configured to send work to a work queue called `test`. This work queue was automatically created when we created the deployment. In Prefect Cloud, you can view your work queues and create new ones manually by selecting the **Work Queues** page.

In your terminal, run the `prefect agent start` command, passing a `-q test` option that tells it to look for work in the `test` work queue.

<div class="terminal">
```

$ prefect agent start -q test

Starting agent connected to https://api.prefect.cloud/api/accounts/...

  ___ ___ ___ ___ ___ ___ _____     _   ___ ___ _  _ _____
 | _ \ _ \ __| __| __/ __|_   _|   /_\ / __| __| \| |_   _|
 |  _/   / _|| _|| _| (__  | |    / _ \ (_ | _|| .` | | |
 |_| |_|_\___|_| |___\___| |_|   /_/ \_\___|___|_|\_| |_|


Agent started! Looking for work from queue 'test'...
```
</div>

!!! tip "`PREFECT_API_URL` setting for agents"
    `PREFECT_API_URL` must be set for the environment in which your agent is running. 

    In this case, we're running the agent in the same environment we logged into Prefect Cloud earlier. However, if you want the agent to communicate with Prefect Cloud from a remote execution environment such as a VM or Docker container, you must configure `PREFECT_API_URL` in that environment.

### Run a flow

Now create a flow run from your deployment. You'll start the flow run from the Prefect Cloud UI, see it run by the agent in your local execution environment, and then see the result back in Prefect Cloud.

Go back to Prefect Cloud and select the **Deployments** page, then select **Test Deployment** in the 'Testing/Test Deployment' deployment name. You'll see a page showing details about the deployment.

![Overview of the test deployment in Prefect Cloud](/img/ui/cloud-test-deployment-details.png)

To start an ad-hoc flow run, select the **Run** button from Prefect Cloud.

In the local terminal session where you started the agent, you can see that the agent picks up the flow run and executes it.

<div class="terminal">
```
$ prefect agent start -q test
Starting agent connected to https://api.prefect.cloud/api/accounts/...

  ___ ___ ___ ___ ___ ___ _____     _   ___ ___ _  _ _____
 | _ \ _ \ __| __| __/ __|_   _|   /_\ / __| __| \| |_   _|
 |  _/   / _|| _|| _| (__  | |    / _ \ (_ | _|| .` | | |
 |_| |_|_\___|_| |___\___| |_|   /_/ \_\___|___|_|\_| |_|


Agent started! Looking for work from queue 'test-queue'...
22:38:06.072 | INFO    | prefect.agent - Submitting flow run '7a9e94d4-7a97-4188-a539-b8594874eb86'
22:38:06.169 | INFO    | prefect.flow_runner.subprocess - Opening subprocess for flow run '7a9e94d4-7a97-4188-a539-b8594874eb86'...
22:38:06.180 | INFO    | prefect.agent - Completed submission of flow run '7a9e94d4-7a97-4188-a539-b8594874eb86'
22:38:09.918 | INFO    | Flow run 'crystal-hog' - Using task runner 'ConcurrentTaskRunner'
22:38:10.225 | WARNING | Flow run 'crystal-hog' - The fun is about to begin
22:38:10.868 | INFO    | Flow run 'crystal-hog' - Finished in state Completed()
22:38:11.797 | INFO    | prefect.flow_runner.subprocess - Subprocess for flow run '7a9e94d4-7a97-4188-a539-b8594874eb86' exited cleanly.
```
</div>

In Prefect Cloud, select the **Flow Runs** page and notice that your flow run appears on the dashboard. (Your flow run name will be different, but the rest of the details should be similar to what you see here.)

![Viewing the flow run based on the test deployment in Prefect Cloud](/img/ui/cloud-test-flow-run.png)

To learn more, see the [Deployments tutorial](/tutorials/deployments/#work-queues-and-agents) for a hands-on example.