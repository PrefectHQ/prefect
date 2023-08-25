---
description: Learn how to run flows on Kubernetes using containers
tags:
    - kubernetes
    - containers
    - orchestration
    - infrastructure
    - deployments
search:
  boost: 2
---

# Running flows with Kubernetes

This guide will walk you through running your flows on Kubernetes.
Though much of the guide is general to any Kubernetes cluster, there are differences between the managed Kubernetes offerings between cloud providers, especially when it comes to container registries and access management.
We'll focus on Amazon Elastic Kubernetes Service (EKS).

## Prerequisites

Before we begin, there are a few pre-requisites:

1. A Prefect Cloud account
2. A cloud provider (AWS, GCP, or Azure) account
3. [Install](/getting-started/installation/) Python and Prefect
4. Install [Helm](https://helm.sh/docs/intro/install/)
5. Install the [Kubernetes CLI (kubectl)](https://kubernetes.io/docs/tasks/tools/install-kubectl/)

!!! Note "Administrator Access"
    Though not strictly necessary, you may want to ensure you have admin access, both in Prefect Cloud and in your cloud provider.
    Admin access is only necessary during the initial setup and can be downgraded after.

## Create a cluster

Let's start by creating a new cluster. If you already have one, skip ahead to the next section.

=== "AWS"

    One easy way to get set up with a cluster in EKS is with [`eksctl`](https://eksctl.io/). 
    Node pools can be backed by either EC2 instances or FARGATE. 
    Let's choose FARGATE so there's less to manage. 
    The following command takes around 15 minutes and must not be interrupted:

    ```bash
    # Replace the cluster name with your own value
    eksctl create cluster --fargate --name <CLUSTER-NAME>

    # Authenticate to the cluster.
    aws eks update-kubeconfig --name <CLUSTER-NAME>
    ```

=== "GCP"
    
    You can easily get a GKE cluster up and running with a few short commands using the [`gcloud` CLI](https://cloud.google.com/sdk/docs/install). This will build a barebones cluster that is accessible over the open internet - this should **not** be used in a production environment. In order to deploy the cluster, your project must have a VPC network configured.

    First, authenticate to GCP by setting the following configuration options.

    ```bash
    # Authenticate to gcloud
    gcloud auth login

    # Specify the project & zone to deploy the cluster to
    # Replace the project name with your GCP project name
    gcloud config set project <GCP-PROJECT-NAME>
    gcloud config set compute/zone <AVAILABILITY-ZONE>
    ```

    Next, deploy the cluster - this command will take ~15 minutes to complete. Once the cluster has been created, authenticate to the cluster.

    ```bash
    # Create cluster
    # Replace the cluster name with your own value
    gcloud container clusters create <CLUSTER-NAME> --num-nodes=1 \
    --machine-type=n1-standard-2

    # Authenticate to the cluster
    gcloud container clusters <CLUSTER-NAME> --region <AVAILABILITY-ZONE>
    ```

    <details>
      <summary>GCP Gotchas</summary>
      
      - You'll need to enable the default service account in the IAM console, or specify a different service account with the appropriate permissions to be used.
      ```
      ERROR: (gcloud.container.clusters.create) ResponseError: code=400, message=Service account "000000000000-compute@developer.gserviceaccount.com" is disabled.
      ```
      
      - Organization policy blocks creation of external (public) IPs. You can override this policy (if you have the appropriate permissions) under the `Organizational Policy` page within IAM.
      ```
      creation failed: Constraint constraints/compute.vmExternalIpAccess violated for project 000000000000. Add instance projects/<GCP-PROJECT-NAME>/zones/us-east1-b/instances/gke-gke-guide-1-default-pool-c369c84d-wcfl to the constraint to use external IP with it."
      ```
      
    </details>

<!-- === "Azure"
    TODO -->

## Create a container registry

Besides a cluster, the other critical resource we'll need is a container registry.
A registry is not strictly required, but in most cases you'll want to use custom images and/or have more control over where images are stored.
If you already have a registry, skip ahead to the next section.

=== "AWS"

    Let's create a registry using the AWS CLI and authenticate the docker daemon to said registry:

    ```bash
    # Replace the image name with your own value
    aws ecr create-repository --repository-name <IMAGE-NAME>

    # Login to ECR
    # Replace the region and account ID with your own values
    aws ecr get-login-password --region <REGION> | docker login \
      --username AWS --password-stdin <AWS_ACCOUNT_ID>.dkr.ecr.<REGION>.amazonaws.com
    ```

=== "GCP"
    Let's create a registry using the gcloud CLI and authenticate the docker daemon to said registry:

    ```bash
    # Create artifact registry repository to host your custom image
    # Replace the repository name with your own value; it can be the 
    # same name as your image
    gcloud artifacts repositories create <REPOSITORY-NAME> \
    --repository-format=docker --location=us

    # Authenticate to artifact registry
    gcloud auth configure-docker us-docker.pkg.dev
    ```

<!-- === "Azure"
    TODO -->

## Create a work pool

Now let's switch over to Prefect Cloud, where we'll create a new work pool.
Hit the plus button on the work pools page and choose Kubernetes from the list of options.
On the next page, set Finished Job TTL to 60 so that completed flow runs are cleaned up, and set Pod Watch Timeout Seconds to 300, especially if you are using a __serverless__ type node pool since these tend to have longer startup times.
You may also want to set a custom namespace, such as `prefect`.
Generally you should leave the cluster config blank as the worker will already be provisioned with appropriate access and permissions.
Finally, leave the image field blank as we'll override that in each deployment.

## Deploy a worker using Helm

With our cluster and work pool created, it's time to deploy a worker, which will take our flows and run them as Kubernetes jobs.
The best way to deploy a worker is using the [Prefect Helm Chart](https://github.com/PrefectHQ/prefect-helm/tree/main/charts/prefect-worker).

### Add the Prefect Helm repository

Add the Prefect Helm repository to your Helm client:

```bash
helm repo add prefect https://prefecthq.github.io/prefect-helm
helm repo update
```

### Create a namespace

Create a new namespace in your Kubernetes cluster to deploy the Prefect worker:

```bash
kubectl create namespace prefect
```

### Create a Kubernetes secret for the Prefect API key

```bash
kubectl create secret generic prefect-api-key \
--namespace=prefect --from-literal=key=your-prefect-cloud-api-key
```

### Configure Helm chart values

Create a `values.yaml` file to customize the Prefect worker configuration.
Add the following contents to the file:

```yaml
worker:
  cloudApiConfig:
    accountId: <target account ID>
    workspaceId: <target workspace ID>
  config:
    workPool: <target work pool name>
```

These settings will ensure that the worker connects to the proper account, workspace, and work pool.

View your Account ID and Workspace ID in your browser URL when logged into Prefect Cloud.
For example: <https://app.prefect.cloud/account/abc-my-account-id-is-here/workspaces/123-my-workspace-id-is-here>.

### Create a Helm release

Let's install the Prefect worker using the Helm chart with your custom `values.yaml` file:

```bash
helm install prefect-worker prefect/prefect-worker \
  --namespace=prefect \
  -f values.yaml
```

### Verify Deployment

Check the status of your Prefect worker deployment:

```bash
kubectl get pods -n prefect
```

## Define a flow

Let's start simple with a flow that just logs a message.
In a directory named `flows`, create a file named `hello.py` with the following contents:

```py
from prefect import flow, get_run_logger, tags

@flow
def hello(name: str = "Marvin"):
    logger = get_run_logger()
    logger.info(f"Hello, {name}!")

if __name__ == "__main__":
    with tags("local"):
        hello()
```

Run the flow locally with `python hello.py` to verify that it works.
Note that we use the `tags` context manager to tag the flow run as `local`.
This step is not required, but does add some helpful metadata.

## Define a deployment

The [`prefect.yaml`](/concepts/deployments/#managing-deployments) file is used by the `prefect deploy` command to deploy our flows.
As a part of that process it will also build and push our image.
Create a new file named `prefect.yaml` with the following contents:

```yaml
# Generic metadata about this project
name: flows
prefect-version: 2.11.0

# build section allows you to manage and build docker images
build:
- prefect_docker.deployments.steps.build_docker_image:
    id: build-image
    requires: prefect-docker>=0.3.11
    image_name: "{{ $PREFECT_IMAGE_NAME }}"
    tag: latest
    dockerfile: auto
    platform: "linux/amd64"

# push section allows you to manage if and how this project is uploaded to remote locations
push:
- prefect_docker.deployments.steps.push_docker_image:
    requires: prefect-docker>=0.3.11
    image_name: "{{ build-image.image_name }}"
    tag: "{{ build-image.tag }}"

# pull section allows you to provide instructions for cloning this project in remote locations
pull:
- prefect.deployments.steps.set_working_directory:
    directory: /opt/prefect/flows

# the definitions section allows you to define reusable components for your deployments
definitions:
  tags: &common_tags
    - "eks"
  work_pool: &common_work_pool
    name: "kubernetes"
    job_variables:
      image: "{{ build-image.image }}"

# the deployments section allows you to provide configuration for deploying flows
deployments:
- name: "default"
  tags: *common_tags
  schedule: null
  entrypoint: "flows/hello.py:hello"
  work_pool: *common_work_pool

- name: "arthur"
  tags: *common_tags
  schedule: null
  entrypoint: "flows/hello.py:hello"
  parameters:
    name: "Arthur"
  work_pool: *common_work_pool
```

We define two deployments of the `hello` flow: `default` and `arthur`.
Note that by specifying `dockerfile: auto`, Prefect will automatically create a dockerfile that installs any `requirements.txt` and copies over the current directory.
You can pass a custom Dockerfile instead with `dockerfile: Dockerfile` or `dockerfile: path/to/Dockerfile`.
Also note that we are specifically building for the `linux/amd64` platform.
This specification is often necessary when images are built on Macs with M series chips but run on cloud provider instances.

!!! note "Deployment specific build, push, and pull"
    The build, push, and pull steps can be overridden for each deployment. 
    This allows for more custom behavior, such as specifying a different image for each deployment.

Let's make sure we define our requirements in a `requirements.txt` file:

```
prefect>=2.11.0
prefect-docker>=0.3.11
prefect-kubernetes>=0.2.11
```

The directory should now look something like this:

```
flows
├── hello.py
├── prefect.yaml
└── requirements.txt
```

### Tag images with a Git SHA

If your code is stored in a GitHub repository, it's good practice to tag your images with the Git SHA of the code used to build it. 
This can be done in the `prefect.yaml` file with a few minor modifications. 
Let's use the `run_shell_script` command to grab the SHA and pass it to the `tag` parameter of `build_docker_image`:

```yaml hl_lines="2-5 10"
build:
- prefect.deployments.steps.run_shell_script:
    id: get-commit-hash
    script: git rev-parse --short HEAD
    stream_output: false
- prefect_docker.deployments.steps.build_docker_image:
    id: build-image
    requires: prefect-docker>=0.3.1
    image_name: "{{ $PREFECT_IMAGE_NAME }}"
    tag: "{{ get-commit-hash.stdout }}"
    dockerfile: auto
    platform: "linux/amd64"
```

Let's also set the SHA as a tag for easy identification in the UI:

```yaml hl_lines="4"
definitions:
  tags: &common_tags
    - "eks"
    - "{{ get-commit-hash.stdout }}"
  work_pool: &common_work_pool
    name: "kubernetes"
    job_variables:
      image: "{{ build-image.image }}"
```

## Authenticate to Prefect

Before we deploy the flows to Prefect, we will need to authenticate via the Prefect CLI. We will also need to ensure that all of our flow's dependencies are present at `deploy` time. 

This example uses a virtual environment to ensure consistency across environments.

```bash
# Create a virtualenv & activate it
virtualenv prefect-demo
source prefect-demo/bin/activate

# Install your flow's dependencies
prefect-demo/bin/pip install -r requirements.txt

# Authenticate to Prefect & select the appropriate 
# workspace to deploy your flows to
prefect-demo/bin/prefect cloud login
```

## Deploy the flows

Now we're ready to deploy our flows which will build our images. 
The image name determines which registry it will end up in. 
We have configured our `prefect.yaml` file to get the image name from the `PREFECT_IMAGE_NAME` environment variable, so let's set that first:

=== "AWS"

    ```bash
    export PREFECT_IMAGE_NAME=<AWS_ACCOUNT_ID>.dkr.ecr.<REGION>.amazonaws.com/<IMAGE-NAME>
    ```

=== "GCP"

    ```bash
    export PREFECT_IMAGE_NAME=us-docker.pkg.dev/<GCP-PROJECT-NAME>/<REPOSITORY-NAME>/<IMAGE-NAME>
    ```

<!-- === "Azure"
    TODO -->

In order to deploy your flows, ensure your Docker daemon is running first. Deploy all the flows with `prefect deploy --all` or deploy them individually by name: `prefect deploy -n hello/default` or `prefect deploy -n hello/arthur`.

## Run the flows

Once successfully deployed we can run the flows from the UI or the CLI:

```bash
prefect deployment run hello/default
prefect deployment run hello/arthur
```

Congratulations! You just ran two flows in Kubernetes. Now head over to the UI to check their status.

<!-- ## Work pool customization -->

<!-- ### Example: cpu and memory -->
