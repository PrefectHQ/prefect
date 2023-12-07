---
description: Prefect will automatically provision infrastructure for you on your cloud provider with a push work pool 
tags:
    - infrastructure
    - automatic provisioning
    - push work pools
    - serverless
    - ECS
    - Google Cloud Run
    - Cloud Run
search:
  boost: 2
  
---

# Automatic infrastructure provisioning

In this guide, you'll learn how to use Prefect to automatically provision infrastructure on your cloud provider of choice.

Currently, with Prefect Cloud you can provision infrastructure for use with an AWS ECS or Google Cloud Run [push work pool](/guides/deployment/push-work-pools/).

Push work pools in Prefect Cloud simplify the setup and management of the infrastructure necessary to run your flows.
However, setting up infrastructure on your cloud provider can still be a time-consuming process.
Prefect can dramatically simplify this process by automatically provisioning the necessary infrastructure for you.

We'll use the `prefect work-pool create` CLI command with the `--provision-infra` flag to automatically provision your serverless cloud resources and set up your Prefect workspace to use a new push pool.

## Prerequisites

To use automatic infrastructure provisioning, you'll need to have the relevant cloud CLI library installed and to have authenticated with your cloud provider.

=== "AWS ECS"

    Install the [AWS CLI](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html) and [authenticate with your AWS account](https://docs.aws.amazon.com/signin/latest/userguide/command-line-sign-in.html).

=== "Azure Container Instances"

    Install the [Azure CLI](https://learn.microsoft.com/en-us/cli/azure/install-azure-cli) and [authenticate with your Azure account](https://learn.microsoft.com/en-us/cli/azure/authenticate-azure-cli).

=== "Google Cloud Run"

    Install the [gcloud CLI](https://cloud.google.com/sdk/docs/install) and [authenticate with your GCP project](https://cloud.google.com/docs/authentication/gcloud).

## Creating a new push work pool and provisioning infrastructure

Here's the command to create a new push work pool named `my-pool` and configure the necessary infrastructure.

=== "AWS ECS"

    <div class="terminal">
    ```bash
    prefect work-pool create --type ecs:push --provision-infra my-ecs-pool
    ```
    </div>

    Using the `--provision-infra` flag will automatically set up your default AWS account to be ready to execute flows via ECS tasks. 
    In your AWS account, this command will create a new IAM user, IAM policy, ECS cluster that uses AWS Fargate, and VPC, if they don't already exist.

    Here's example output from running the command:

    <div class="terminal">
    ```
    ╭───────────────────────────────────────────────────────────────────────────────────────────────────────────────────╮
    │ Provisioning infrastructure for your work pool my-ecs-pool will require:                                         │
    │                                                                                                                   │
    │          - Creating an IAM user for managing ECS tasks: prefect-ecs-user                                          │
    │          - Creating and attaching an IAM policy for managing ECS tasks: prefect-ecs-policy                        │
    │          - Storing generated AWS credentials in a block                                                           │
    │          - Creating an ECS cluster for running Prefect flows: prefect-ecs-cluster                                 │
    │          - Creating a VPC with CIDR 172.31.0.0/16 for running ECS tasks: prefect-ecs-vpc                          │
    ╰───────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
    Proceed with infrastructure provisioning? [y/n]: y
    Provisioning IAM user
    Creating IAM policy
    Generating AWS credentials
    Creating AWS credentials block
    Provisioning ECS cluster
    Provisioning VPC
    Creating internet gateway
    Setting up subnets
    Setting up security group
    Provisioning Infrastructure ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 100% 0:00:00
    Infrastructure successfully provisioned!
    Created work pool 'my-ecs-pool'!
    ```
    <div class="terminal">

=== "Azure Container Instances"

    <div class="terminal">
    ```bash
    prefect work-pool create --type aci:push --provision-infra my-aci-pool
    ```
    </div>

    Using the `--provision-infra` flag will automatically set up your default Azure account to be ready to execute flows via Azure Container Instances.
    In your Azure account, this command will create a resource group, app registration, service account with necessary permission, generate a secret for the app registration, and create an Azure Container Instance, if they don't already exist.
    In your Prefect workspace, this command will create an `AzureContainerInstanceCredentials` block for storing the client secret value from the generated secret.

    Here's example output from running the command:

    <div class="terminal">
    ```
    TK
    ```
    </div>

=== "Google Cloud Run"

    <div class="terminal">
    ```bash
    prefect work-pool create --type cloud-run:push --provision-infra my-cloud-run-pool 
    ```
    </div>

    Using the `--provision-infra` flag will allow you to select a GCP project to use for your work pool and automatically configure it to be ready to execute flows via Cloud Run.
    In your GCP project, this command will activate the Cloud Run API, create a service account, and create a key for the service account, if they don't already exist..
    In your Prefect workspace, this command will create a `GCPCredentials` block.

    Here's example output from running the command:

    <div class="terminal">
    ```
    ╭──────────────────────────────────────────────────────────────────────────────────────────────────────────╮
    │ Provisioning infrastructure for your work pool my-cloud-run-pool will require:                                     │
    │                                                                                                          │
    │     Updates in GCP project central-kit-405415 in region us-central1                                      │
    │                                                                                                          │
    │         - Activate the Cloud Run API for your project                                                    │
    │         - Create a service account for managing Cloud Run jobs: prefect-cloud-run                        │
    │             - Service account will be granted the following roles:                                       │
    │                 - Service Account User                                                                   │
    │                 - Cloud Run Developer                                                                    │
    │         - Create a key for service account prefect-cloud-run                                             │
    │                                                                                                          │
    │     Updates in Prefect workspace                                                                         │
    │                                                                                                          │
    │         - Create GCP credentials block my--pool-push-pool-credentials to store the service account key   │
    │                                                                                                          │
    ╰──────────────────────────────────────────────────────────────────────────────────────────────────────────╯
    Proceed with infrastructure provisioning? [y/n]: y
    Activating Cloud Run API
    Creating service account
    Assigning roles to service account
    Creating service account key
    Creating GCP credentials block
    Provisioning Infrastructure ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 100% 0:00:00
    Infrastructure successfully provisioned!
    Created work pool 'my-cloud-run-pool'!
    ```
    </div>

That's it!
You're ready to create and schedule deployments that use your new push work pool.
Reminder that no worker is needed to run flows with a push work pool.

## Making changes to your work pool

If you'd like to make changes to your work pool, navigate to **Work Pools** in the Prefect Cloud UI and choose **Edit** from the three dot menu for your work pool.

## Using existing resources

If you already have the necessary infrastructure set up, Prefect will detect that upon work pool creation and the infrastructure provisioning for that resource will be skipped.

For example, here's how `prefect work-pool create my-work-pool --provision-infra` looks when existing Azure resources are detected:

<div class="terminal">

```bash
Proceed with infrastructure provisioning? [y/n]: y
Creating resource group
Resource group 'prefect-aci-push-pool-rg' already exists in location 'eastus'.
Creating app registration
App registration 'prefect-aci-push-pool-app' already exists.
Generating secret for app registration
Provisioning infrastructure... ━━━━━━━━━━━━━━━━╺━━━━━━━━━━━━━━━━━━━━━━━  40% 0:00:02Secret generated for app registration with client ID '1111cb05-3b9e-4d1b-92cc-d897b2d4f337'
ACI credentials block 'bb-push-pool-credentials' created
Assigning Contributor role to service account...
Service principal with object ID '4be6fed7-ecbd-4941-9da8-16af068f2a45' already has the 'Contributor' role assigned in 
'/subscriptions/2d38d768-2bc9-46b1-af48-5568eeea417c/resourceGroups/prefect-aci-push-pool-rg'
Creating Azure Container Instance
Container instance 'prefect-aci-push-pool-container' already exists.
Creating Azure Container Instance credentials block
Provisioning infrastructure... ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 100% 0:00:00
Infrastructure successfully provisioned!
Created work pool 'my-work-pool'!
```

</div>
