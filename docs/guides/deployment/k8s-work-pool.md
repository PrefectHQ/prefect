---
description: Learn how to deploy a Prefect Worker on Kubernetes
tags:
    - kubernetes
    - containers
    - orchestration
    - infrastructure
    - deployments
---

## Prefect Kubernetes Work Pools

In this tutorial, we will walk you through how to configure and use Prefect Kubernetes work pools. Work pools allow you to manage multiple deployments with different settings, resources, and labels. Follow the steps below to set up and use Kubernetes work pools in Prefect.

Prerequisites:
- [Prefect Kubernetes Worker](/guides/deployment/helm-worker.md) deployed in a kubernetes cluster

### Step 1: Create a new Work Pool

1. Navigate to the Prefect Dashboard and click on the "Work Pools" tab on the left sidebar.
2. Click the "Add Work Pool" button.
3. Select "Kubernetes" as the work pool type.
4. Provide a name for your new Kubernetes work pool.

### Step 2: Configure Work Pool settings

The following settings are available for configuring your Kubernetes work pool:

#### 1. Flow Run Concurrency (Optional)
Set the maximum number of flow runs that can run concurrently. If you don't set a limit, it will be unlimited.

#### 2. Environment Variables (Optional)
Add environment variables to set when starting a flow run. Click on the "Add" button to add a new variable.

#### 3. Image (Optional)
Specify the container image to use for created jobs. If not set, the latest Prefect image will be used by default.

#### 4. Labels (Optional)
Apply labels to the infrastructure created by a worker. Click on the "Add" button to add new labels.

#### 5. Command (Optional)
Provide a custom command to use when starting a flow run. In most cases, leave this blank to let the worker automatically generate the command.

#### 6. Namespace (Optional)
Set the Kubernetes namespace to create jobs within. By default, it is set to "default".

#### 7. Stream Output (Optional)
Enable this option if you want to stream output from the job to local standard output.

#### 8. Cluster Config
Configure the Kubernetes cluster to use for job creation by specifying the `KubernetesClusterConfig`. You can use `from_file` for creation.

#### 9. Finished Job TTL (Optional)
Set the number of seconds to retain jobs after completion. If set, finished jobs will be cleaned up by Kubernetes after the given delay. If not set, jobs will be retained indefinitely.

#### 10. Image Pull Policy (Optional)
Select the Kubernetes image pull policy to use for job containers. The default value is "IfNotPresent".

#### 11. Service Account Name (Optional)
Specify the Kubernetes service account to use for job creation.

#### 12. Job Watch Timeout Seconds (Optional)
Set the number of seconds to wait for each event emitted by a job before timing out. If not set, the worker will wait for each event indefinitely.

#### 13. Pod Watch Timeout Seconds (Optional)
Specify the number of seconds to watch for pod creation before timing out. By default, it is set to 60 seconds.

### Step 3: Save your configuration

After configuring the work pool settings, click the "Save" button to save your configuration. Your new Kubernetes work pool should now appear in the list of work pools.

### Step 4: Assigning the Work Pool to your Flows

Your worker, which was started with a command like `prefect worker start -t kubernetes -p <name of work pool>` will connect to the work pool and start submitting scheduled work.