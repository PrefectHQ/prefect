---
description: Learn how to use Prefect push work pools to schedule work on serverless infrastructure without having to run a worker.
tags:
    - work pools
    - deployments
    - Cloud Run
    - AWS ECS
    - Azure Container Instances
    - ACI
    - push work pools
search:
  boost: 2
---


# Push Work to Serverless Computing Infrastructure <span class="badge cloud"></span>

Push [work pools](/concepts/work-pools/#work-pool-overview) are a special type of work pool that allows Prefect Cloud to submit flow runs for execution to serverless computing infrastructure without running a worker. Push work pools currently support execution in GCP Cloud Run Jobs, Azure Container Instances, and AWS ECS Tasks.

In this guide you will:

- Create a push work pool that sends work to Google Cloud Run, Amazon Elastic Container Service (AWS ECS) or Azure Container Instances (ACI)
- Deploy a flow to that work pool
- Execute our flow without having to run a worker or agent process to poll for flow runs

## Setup

=== "AWS ECS"

    To push work to ECS, AWS credentials are required.

    Create a user and attach the *AmazonECS_FullAccess* permissions.

    From that user's page create credentials and store them somewhere safe for use in the next section.

=== "Azure Container Instances"

    To push work to Azure, an Azure subscription, resource group and tenant secret are required. 

    ##### Create Subscription and Resource Group

    1. In the Azure portal, create a subscription.
    2. Create a resource group within your subscription.

    ### Create App Registration

    1. In the Azure portal, create an app registration.
    2. In the app registration, create a client secret. Copy the value and store it somewhere safe.
    
    ### Add App Registration to Resource Group

    1. Navigate to the resource group you created earlier.
    2. Choose the "Access control (IAM)" blade in the left-hand side menu. Click "+ Add" button at the top, then "Add role assignment".
    3. Go to the "Privileged administrator roles" tab, click on "Contributor", then click "Next" at the bottom of the page.
    4. Click on "+ Select members". Type the name of the app registration (otherwise it may not autopopulate) and click to add it. Then hit "Select" and click "Next". The default permissions associated with a role like "Contributor" might not always be sufficient for all operations related to Azure Container Instances (ACI). The specific permissions required can depend on the operations you need to perform (like creating, running, and deleting ACI container groups) and your organization's security policies. In some cases, additional permissions or custom roles might be necessary.
    5. Click "Review + assign" to finish.

=== "Google Cloud Run"

    A GCP service account and an API Key are required, to push work to Cloud Run.

    Create a service account by navigating to the service accounts page and clicking *Create*. Name and describe your service account, and click *continue* to configure permissions.

    The service account must have two roles at a minimum, *Cloud Run Developer*, and *Service Account User*.

    ![Configuring service account permissions in GCP](/img/guides/gcr-service-account-setup.png)

    Once the Service account is created, navigate to its *Keys* page to add an API key. Create a JSON type key, download it, and store it somewhere safe for use in the next section.

## Work pool configuration

Our push work pool will store information about what type of infrastructure our flow will run on, what default values to provide to compute jobs, and other important execution environment parameters. Because our push work pool needs to integrate securely with your serverless infrastructure, we need to start by storing our credentials in Prefect Cloud, which we'll do by making a block.

### Creating a Credentials block

=== "AWS ECS"

    Navigate to the blocks page, click create new block, and select AWS Credentials for the type.
    
    For use in a push work pool, this block must have the region and cluster name filled out, in addition to access key and access key secret.

    Provide any other optional information and create your block.

=== "Azure Container Instances"

    Navigate to the blocks page and click the "+" at the top to create a new block. Find the Azure Container Instance Credentials and click "Add +".
    
    Locate the client ID and tenant ID on your app registration and use the client secret you saved earlier. Be sure to use the value of the secret, not the secret ID!

    Provide any other optional information and click "Create".

=== "Google Cloud Run"

    Navigate to the blocks page, click create new block, and select GCP Credentials for the type.

    For use in a push work pool, this block must have the contents of the JSON key stored in the Service Account Info field, as such:

    ![Configuring GCP Credentials block for use in cloud run push work pools](/img/guides/gcp-creds-block-setup.png)

    Provide any other optional information and create your block.

### Create push work pool

Now navigate to the work pools page. Click create to start configuring your push work pool by selecting a push option in the infrastructure type step.

=== "AWS ECS"

    Each step has several optional fields that are detailed in the [work pools](/concepts/work-pools/) documentation. For our purposes, select the block you created under the AWS Credentials field. This will allow Prefect Cloud to securely interact with your ECS cluster.

=== "Azure Container Instances"

    Fill in the subscription ID and resource group name from the resource group you created.  Add the Azure Container Instance Credentials block you created in the step above. 

=== "Google Cloud Run"

    Each step has several optional fields that are detailed in the [work pools](/concepts/work-pools/) documentation. For our purposes, select the block you created under the GCP Credentials field. This will allow Prefect Cloud to securely interact with your GCP project.

Create your pool and you are ready to deploy flows to your Push work pool.

!!! note "Push work pool concurrency"

    Push work pools do not have a concurrency setting. If you would like to control concurrency at the flow level, you can use [global concurrency limits](/guides/global-concurrency-limits/).

## Deployment

Deployment details are described in the deployments [concept section](/concepts/deployments/). Your deployment needs to be configured to send flow runs to our push work pool. For example, if you create a deployment through the interactive command line experience, choose the work pool you just created. If you are deploying an existing `prefect.yaml` file,  the deployment would contain:

```yaml
  work_pool:
    name: my-push-pool
```

Deploying your flow to the `my-push-pool` work pool will ensure that runs that are ready for execution will be submitted immediately, without the need for a worker to poll for them.

!!! danger "Serverless infrastructure may require a certain image architecture"
    Note that serverless infrastructure may assume a certain Docker image architecture; for example, Google Cloud Run will fail to run images built with `linux/arm64` architecture. If using Prefect to build your image, you can change the image architecture through the `platform` keyword (e.g., `platform="linux/amd64"`).

## Putting it all together

With your deployment created, navigate to its detail page and create a new flow run. You'll see the flow start running without ever having to poll the work pool, because Prefect Cloud securely connected to your serverless infrastructure, created a job, ran the job, and began reporting on its execution.

![A flow running on a cloud run push work pool](/img/guides/push-flow-running.png)
