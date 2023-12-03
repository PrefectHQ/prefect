---
description: Prefect will automatically provision infrastructure for you on your cloud provider with a push work pool 
tags:
    - infrastructure
search:
  
---

# Automatic infrastructure provisioning

You can use Prefect to automatically provision infrastructure for you on your cloud provider of choice for use with a [push work pool]() TK link on Prefect cloud.

## Prerequisites

To use automatic infrastructure provisioning, you'll need to have the following installed:

=== "AWS ECS"

TK package

Prefect can automatically provision infrastructure in your AWS account and set up your Prefect workspace to support a new ECS push pool.

Here's the command:

<div class="terminal">
```bash
prefect work-pool create --type ecs:push --provision-infra my-pool
```
</div>

Using the `--provision-infra` flag will automatically set up your default AWS account to be ready to execute flows via ECS tasks:

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

=== "Google Cloud Run"

TK gcloud CLI? link

Push work pools in Prefect Cloud simplify the setup and management of the infrastructure necessary to run your flows, but they still require some setup. With this release, we've enhanced the `prefect work-pool create` CLI command to automatically configure your GCP project and set up your Prefect workspace to use a new Cloud Run push pool immediately.

Note: To take advantage of this feature, you'll need to have the `gcloud` CLI installed and authenticated with your GCP project.

You can create a new Cloud Run push work pool and configure your project with the following command:

```bash
prefect work-pool create --type cloud-run:push --provision-infra my-pool 
```

Using the `--provision-infra` flag will allow you to select a GCP project to use for your work pool and automatically configure it to be ready to execute flows via Cloud Run:

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
