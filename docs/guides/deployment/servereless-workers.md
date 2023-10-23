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

Prefect provides work pools for workers to run serverless flows on cloud provider platforms. Options:

- AWS ECS
- Azure Container Instances (ACI)
- Google Cloud Run
- Google Vertex AI

![Work pool options](/img/ui/work-pools.png)

In this guide you will:

- Create a work pool that sends work to your chosen serverless infrastructure option
- Deploy a flow to that work pool
- Start a worker that will poll the matched work pool for scheduled runs
- Schedule a deployment run that a worker will pick up from the work pool

!!! note "Serverless push work pools don't require a worker"
    Options for push versions of AWS ECS, Azure Container Instances, and Google Cloud Run work pools that do not require a worker are available with Prefect Cloud.
    These options require less configuration because no worker is required.
    Read more in the [Serverless Push Work Pool Guide](/guides/deployments/serverless/).

In this guide we will run our worker locally.
You could run your worker in a cloud VM or the serverless infrastructure type where you are running your flows.
To see an example of running flows in AWS ECS and a worker in AWS ECS see the [guide in the `prefect-aws` docs](https://prefecthq.github.io/prefect-aws/ecs_guide/)
To see an example of running flows in Google Cloud Run and a worker in Google Cloud Run see the forthcoming guide in the [`prefect-gcp` docs](https://prefecthq.github.io/prefect-gcp/).

!!! note "Choosing between Google Cloud Run and Google Vertex AI"
    Google Vertex AI is well-suited for machine learning model training applications in which GPUs or TPUs and high resource levels are desired.

## Setup

TK make sure that permissions are correct

=== "AWS ECS"

    To run a deployment on ECS, AWS credentials are required.

    Create a user and attach the *AmazonECS_FullAccess* permissions.

    From that user's page create credentials and store them somewhere safe for use in the next section.

=== "Azure Container Instances"

    To run a deployment on ACI, an Azure subscription, resource worker and tenant secret are required. 

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

    To run a deployment on Google Cloud Run, a GCP service account and an API Key are required.

    Create a service account by navigating to the service accounts page and clicking *Create*. Name and describe your service account, and click *continue* to configure permissions.

    The service account must have two roles at a minimum, *Cloud Run Developer*, and *Service Account User*.

    ![Configuring service account permissions in GCP](/img/guides/gcr-service-account-setup.png)

    Once the Service account is created, navigate to its *Keys* page to add an API key. Create a JSON type key, download it, and store it somewhere safe for use in the next section.

=== "Google Vertex AI"

    To run a deployment on Google Vertex AI, a GCP service account and an API Key are required.

    Create a service account by navigating to the service accounts page and clicking *Create*. Name and describe your service account, and click *continue* to configure permissions.

    The service account must have two roles at a minimum, *Cloud Run Developer*, and *Service Account User*.

    ![Configuring service account permissions in GCP](/img/guides/gcr-service-account-setup.png)

    Once the Service account is created, navigate to its *Keys* page to add an API key. Create a JSON type key, download it, and store it somewhere safe for use in the next section.

## Create a work pool

Choose a work pool type that corresponds to your cloud provider infrastructure.
The work pool will contain default values to provide to compute jobs and any other important execution environment parameters.
Because the work pool needs to integrate securely with the serverless infrastructure, let's store our credentials in a server-side block.

Navigate to the **Blocks** page.

### Create a Credentials block

=== "AWS ECS"

    Select **AWS Credentials** for the block type.
    
    For use in a work pool, this block must have the region and cluster name filled out, in addition to access key and access key secret. TK, true?

    Provide any other optional information and create your block.

=== "Azure Container Instance"

    Select **Azure Container Instance Credentials** for the block type.
    
    Locate the client ID and tenant ID on your app registration and use the client secret you saved earlier.

    Provide any other optional information and create your block.

=== "Google Cloud Run"

    Select **GCP Credentials** for the block type.

    For use in a push work pool, this block must have the contents of the JSON key stored in the Service Account Info field, as such:

    ![Configuring GCP Credentials block for use in GCP work pools](/img/guides/gcp-creds-block-setup.png)

    Provide any other optional information and create your block.

=== "Google Vertex AI"

    Select **GCP Credentials** for the block type.

    For use in a push work pool, this block must have the contents of the JSON key stored in the Service Account Info field, as such:

    ![Configuring GCP Credentials block for use in GCP work pools](/img/guides/gcp-creds-block-setup.png)

    Provide any other optional information and create your block.

### Create serverless work pool

Navigate to **Work Pools** in the Prefect UI and select the serverless cloud work pool type you plan to use.

=== "AWS ECS"

    Each step has several optional fields that are detailed in the [work pools](/concepts/work-pools/) documentation. 
    Select the block you created under the AWS Credentials field so that Prefect Cloud can securely interact with your ECS cluster.

=== "Azure Container Instance"

    Fill in the subscription ID and resource group name from the resource group you created.  
    Add the Azure Container Instance Credentials block you created in the step above. 

=== "Google Cloud Run"

    Each step has several optional fields that are detailed in the [work pools](/concepts/work-pools/) documentation. 
    Select the block you created under the GCP Credentials field so that Prefect Cloud can securely interact with your GCP project.

=== "Google Vertex AI"

    Each step has several optional fields that are detailed in the [work pools](/concepts/work-pools/) documentation. 
    Select the block you created under the GCP Credentials field so that Prefect Cloud can securely interact with your GCP project.

Specify any customizations needed for your work pool.
You can override individual work pool fields when you create your deployment.

## Create a deployment

You can create a deployment using any of the methods outlined below:

1. Python script with `flow.deploy()` or `deploy`. Specify your newly created work pool name.
    Note that running a Python file with `flow.serve()` or `serve` creates a long-running server that does not use a work pool.
    Use a work pool when you want fine-grained infrastructure customizability, have expensive infrastructure, or need to dynamically scale infrastructure.
1. Interactive CLI experience with `prefect deploy`.
    Choose the work pool you just created.
1. Deploy an existing `prefect.yaml` file with `prefect deploy`. The `prefect.yaml` file will contain:

```yaml
  work_pool:
    name: my-serverless-pool
```

See the [deployments concept page](/concepts/deployments/) for more details.

## Start a worker

On your local machine or on the cloud infrastructure of your choice, start a worker in an environment with Prefect installed.

```prefect worker start my_worker```

TK does worker need to have relevant Prefect integration library installed or not if the library is specified in the Docker image on the serverless infrastructure.

If your worker has the necessary credentials to run workflows on your serverles infrastructure, you may not need to create a Credentials block (TK - depends where image is hosted - e.g. registry, probably, too)

## Run a deployment

Navigate to your deployment page in the UI and schedule a run or schedule a run from the CLI.
Watch your serveless infrastructure spin up and your flow run logs in the UI or your worker's CLI.

## Next steps

More in-depth versions of guides for these serverless work pool options are available in the respective Prefect integration libraries.

Options for push versions of AWS ECS, Azure Container Instances, and Google Cloud Run work pools that do not require a worker are available with Prefect Cloud.
    Read more in the [Serverless Push Work Pool Guide](/guides/deployments/serverless/).
I
