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

    Install the [AWS CLI](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html) and authenticate with your AWS account.

=== "Google Cloud Run"

    Install the [gcloud CLI](https://cloud.google.com/sdk/docs/install) and authenticate with your GCP project.

## Creating a new push work pool and provisioning infrastructure

Here's the command to create a new push work pool named `my-pool` and configure the necessary infrastructure.

=== "AWS ECS"

    <div class="terminal">
    ```bash
    prefect work-pool create --type ecs:push --provision-infra my-pool
    ```
    </div>

    Using the `--provision-infra` flag will automatically set up your default AWS account to be ready to execute flows via ECS tasks. 
    This command will create a new IAM user, IAM policy, ECS cluster that uses AWS Fargate, and VPC in your AWS account.

    Here's example output from running the command:

    <div class="terminal">
    ```
    ╭───────────────────────────────────────────────────────────────────────────────────────────────────────────────────╮
    │ Provisioning infrastructure for your work pool my-work-pool will require:                                         │
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
    Created work pool 'my-pool'!
    ```
    <div class="terminal">

=== "Google Cloud Run"

    <div class="terminal">
    ```bash
    prefect work-pool create --type cloud-run:push --provision-infra my-pool 
    ```
    </div>

    Using the `--provision-infra` flag will allow you to select a GCP project to use for your work pool and automatically configure it to be ready to execute flows via Cloud Run.
    This command will activate the Cloud Run API for your project, create a service account, create a key for the service account, and create a GCP credentials block in your Prefect workspace.

    <div class="terminal">
    ```
    ╭──────────────────────────────────────────────────────────────────────────────────────────────────────────╮
    │ Provisioning infrastructure for your work pool my-pool will require:                                     │
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
    Created work pool 'my-pool'!
    ```
    </div>

That's it!
You're ready to create and schedule deployments that use your new push work pool.
Reminder that no worker is needed to run flows with a push work pool.

## Making changes to your work pool

If you'd like to make changes to your work pool, navigate to **Work Pools** in the Prefect Cloud UI and choose **Edit** from the three dot menu for your work pool.

## Using existing resources

TK Alex to add
