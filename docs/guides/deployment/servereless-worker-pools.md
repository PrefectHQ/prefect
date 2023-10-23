---
description: Learn how to use Prefect to schedule work on serverless infrastructure with a worker.
tags:
    - work pools
    - deployments
    - Cloud Run
    - GCP
    - Vertex AI
    - AWS ECS
    - Azure Container Instances
    - ACI
search:
  boost: 2
---


# Run Deployments on Serverless Computing Infrastructure

Prefect provides work pools for workers to run flows on cloud provider platforms. Options:

- AWS ECS
- Azure Container Instances (ACI)
- Google Cloud Run
- Google Vertex AI

In this guide you will:

- Create a work pool that sends work to your chosen option
- Deploy a flow to that work pool
- Start a worker to match the work pool
- Schedule a deployment run that a worker will pick up from the work pool

![Work pool options](/img/ui/work-pools.png)

!!! Note - Options for push versions of AWS ECS, Azure Container Instances, and Google Cloud Run that do not require a worker are available with Prefect Cloud. Read more in the [Serverless Push Work Pool Guide](/guides/deployments/serverless/).

More in-depth versions of guides for these serverless work pool options are available in the respective Prefect integration libraries. TK links
Move ACI guide to prefect-azure TK

## Setup

TK make sure that permissions are correct - check related guides

=== "AWS ECS"

    To run a flow on ECS, AWS credentials are required.

    Create a user and attach the *AmazonECS_FullAccess* permissions.

    From that user's page create credentials and store them somewhere safe for use in the next section.

=== "Azure Container Instance"

    To push work to Azure, an Azure subscription, resource worker and tenant secret are required. 

    ##### Create Subscription and Resource Worker

    1. In the Azure portal, create a subscription.
    2. Create a resource group within your subscription.

    ### Create App Registration

    1. In the Azure portal, create an app registration.
    2. In the app registration, create a client secret. Copy the value and store it somewhere safe.
    
    ### Add App Registration to Subscription

    1. Navigate to the resource group you created earlier.
    2. Click on "Access control (IAM)" and then "Role assignments".
    3. Search for the app registration and select it. Give it a role that has sufficient privileges to create, run, and delete ACI container groups.

=== "Google Cloud Run"

    To push work to Cloud Run, a GCP service account and an API Key are required.

    Create a service account by navigating to the service accounts page and clicking *Create*. Name and describe your service account, and click *continue* to configure permissions.

    The service account must have two roles at a minimum, *Cloud Run Developer*, and *Service Account User*.

    ![Configuring service account permissions in GCP](/img/guides/gcr-service-account-setup.png)

    Once the Service account is created, navigate to its *Keys* page to add an API key. Create a JSON type key, download it, and store it somewhere safe for use in the next section.

=== "Google Vertex AI"

    To push work to Cloud Run, a GCP service account and an API Key are required.

    Create a service account by navigating to the service accounts page and clicking *Create*. Name and describe your service account, and click *continue* to configure permissions.

    The service account must have two roles at a minimum, *Cloud Run Developer*, and *Service Account User*.

    ![Configuring service account permissions in GCP](/img/guides/gcr-service-account-setup.png)

    Once the Service account is created, navigate to its *Keys* page to add an API key. Create a JSON type key, download it, and store it somewhere safe for use in the next section.

## Create a work pool

Our push work pool will store information about what type of infrastructure we're running on, what default values to provide to compute jobs, and other important execution environment parameters. Because our push work pool needs to integrate securely with your serverless infrastructure, we need to start by storing our credentials in Prefect Cloud, which we'll do by making a block.

### Create a Credentials block

=== "AWS ECS"

    Navigate to the blocks page, click create new block, and select AWS Credentials for the type.
    
    For use in a push work pool, this block must have the region and cluster name filled out, in addition to access key and access key secret.

    Provide any other optional information and create your block.

=== "Azure Container Instance"

    Navigate to the blocks page, click create new block, and select Azure Container Instance Credentials for the type.
    
    Locate the client ID and tenant ID on your app registration and use the client secret you saved earlier.

    Provide any other optional information and create your block.

=== "Google Cloud Run"

    Navigate to the blocks page, click create new block, and select GCP Credentials for the type.

    For use in a push work pool, this block must have the contents of the JSON key stored in the Service Account Info field, as such:

    ![Configuring GCP Credentials block for use in cloud run push work pools](/img/guides/gcp-creds-block-setup.png)
    
    TK fix image

    Provide any other optional information and create your block.

=== "Google Vertex AI"

    Navigate to the blocks page, click create new block, and select GCP Credentials for the type.

    For use in a push work pool, this block must have the contents of the JSON key stored in the Service Account Info field, as such:

    ![Configuring GCP Credentials block for use in cloud run push work pools](/img/guides/gcp-creds-block-setup.png)

    TK fix image

    Provide any other optional information and create your block.

### Create serverless work pool

Navigate to **Work Pools** in the Prefect UI and select the serverless cloud option you have prepared on your cloud provider platform.

=== "AWS ECS"

    Each step has several optional fields that are detailed in the [work pools](/concepts/work-pools/) documentation. For our purposes, select the block you created under the AWS Credentials field. This will allow Prefect Cloud to securely interact with your ECS cluster.

=== "Azure Container Instance"

    Fill in the subscription ID and resource group name from the resource group you created.  Add the Azure Container Instance Credentials block you created in the step above. 

=== "GCP Cloud Run"

    Each step has several optional fields that are detailed in the [work pools](/concepts/work-pools/) documentation. For our purposes, select the block you created under the GCP Credentials field. This will allow Prefect Cloud to securely interact with your GCP project.

=== "GCP Vertex AI"

    Each step has several optional fields that are detailed in the [work pools](/concepts/work-pools/) documentation. For our purposes, select the block you created under the GCP Credentials field. This will allow Prefect Cloud to securely interact with your GCP project.

Create your pool with any customizations you like. You can override work pool details when you create your deployment.

## Create a deployment

Deployment details are described in the deployments [concept section](/concepts/deployments/).

You have several options to create a deployment:

1. Python script with `flow.deploy()` or `deploy`. Specify your newly created work pool name.
    Note that running a Python file with `flow.serve()` or `serve` creates a long-running server that does not use a work pool. Use a work pool when you want fine-grained infrastructure customizability, have expensive infrastructure, or need to dynamically scale infrastructure.
1. Interactive CLI with `prefect deploy`. Choose the work pool you just created.
1. If deploying an existing `prefect.yaml` file,  the deployment would contain:

```yaml
  work_pool:
    name: my-serverless-pool
```

## Start a worker

On your local machine or the the infrastructure of your choice, start a worker in an environment with Prefect installed.

```prefect worker start my_worker```

## Run a deployment

With your deployment created, navigate to its detail page in the UI and schedule a run. Watch your serveless infrastructure spin up and your flow run logs in the UI or your worker's CLI.

![A flow running on a cloud  work pool](/img/guides/  .png) TK image
