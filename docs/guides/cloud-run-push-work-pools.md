---
description: Learn how to use Prefect push work pools to schedule work on serverless infrastructure without having to run a worker.
tags:
    - work pools
    - deployments
    - Cloud Run
search:
  boost: 2
---

# Push Work to Google Cloud Run <span class="badge cloud"></span>
Push [work pools](/concepts/work-pools/#work-pool-overview) are a special type of work pool that allows Prefect Cloud to submit flow runs for execution to serverless computing infrastructure without a user running a worker. Push work pools currently support execution in GCP Cloud Run Jobs, Azure Container Instances, and AWS ECS Tasks.

In this guide we'll:

- Create a push work pool that sends work to Google Cloud Run
- Deploy a flow to that work pool
- Execute our flow without having to run a worker or agent process to poll for flow runs

## Google Cloud Run Setup

To push work to Cloud Run, a GCP service account and an API Key are required.

Create a service account by navigating to the service accounts page and clicking *Create*. Name and describe your service account, and click *continue* to configure permissions.

The service account must have two roles at a minimum, *Cloud Run Developer*, and *Service Account User*.

![Configuring service account permissions in GCP](/img/guides/gcr-service-account-setup.png)

Once the Service account is created, navigate to its *Keys* page to add an API key. Create a JSON type key, download it, and store it somewhere safe for use in the next section.

## Work Pool Configuration

Our push work pool will store information about what type of infrastructure we're running on, what default values to provide to compute jobs, and other important execution environment parameters. Because our push work pool needs to integrate securely with your Cloud Run, we need to start by storing our credentials in Prefect Cloud, which we'll do by making a block.

### Creating a GCP Credentials Block

Navigate to the blocks page, click create new block, and select GCP Credentials for the type.

For use in a push work pool, this block must have the contents of the JSON key stored in the Service Account Info field, as such:

![Configuring GCP Credentials block for use in cloud run push work pools](/img/guides/gcp-creds-block-setup.png)

Provide any other optional information and create your block.

### Create your Cloud Run - Push Work Pool

Now navigate to work pools and click create to start configuring your Cloud Run - Push work pool.

Each step has several optional fields that are detailed in the [work pools](/concepts/work-pools/) documentation. For our purposes. Select the block you created under the GCP Credentials field. This will allow Prefect Cloud to securely interact with your GCP project.

Create your pool and you are ready to deploy flows to your Cloud Run - Push work pool.

## Deployment

Deployment details are described in the deployments [concept section](/concepts/deployments/). Your deployment needs to be configured to send flow runs to our push work pool. For example, if you create a deployment through the interactive command line experience, choose the work pool you just created. If you are deploying an existing `prefect.yaml` file,  the deployment would contain:

```yaml
  work_pool:
    name: my-google-cloud-run-push-pool
```

Deploying your flow to the `my-google-cloud-run-push-pool` work pool will ensure that runs that are ready for execution will be submitted immediately, without the need for a worker to poll for them.

## Putting it all Together

With your deployment created, navigate to its detail page and create a new flow run. You'll see the flow start running without ever having to poll the work pool, because Prefect Cloud securely connected to your GCP project, created a job, ran the job, and began reporting on its execution.

![A flow running on a cloud run push work pool](/img/guides/push-flow-running.png)


