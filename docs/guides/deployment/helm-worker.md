---
description: Learn how to deploy a Prefect Worker on Kubernetes
tags:
    - kubernetes
    - containers
    - orchestration
    - infrastructure
    - deployments
search:
  boost: 2
---

# Using Prefect Helm Chart for Prefect Workers

This guide will walk you through the process of deploying Prefect workers using the [Prefect Helm Chart](https://github.com/PrefectHQ/prefect-helm/tree/main/charts/prefect-worker). We will also cover how to set up a Kubernetes secret for the API key and mount it as an environment variable.
## Prerequisites

Before you begin, ensure you have the following installed and configured on your machine:

1. Helm: [https://helm.sh/docs/intro/install/](https://helm.sh/docs/intro/install/)
2. Kubernetes CLI (kubectl): [https://kubernetes.io/docs/tasks/tools/install-kubectl/](https://kubernetes.io/docs/tasks/tools/install-kubectl/)
3. Access to a Kubernetes cluster (e.g., Minikube, GKE, AKS, EKS)

## Step 1: Add Prefect Helm Repository

First, add the Prefect Helm repository to your Helm client:

```bash

helm repo add prefect https://prefecthq.github.io/prefect-helm
helm repo update
```


## Step 2: Create a Namespace for Prefect Worker

Create a new namespace in your Kubernetes cluster to deploy the Prefect worker:

```bash

kubectl create namespace prefect
```


## Step 3: Create a Kubernetes Secret for the API Key

Create a file named `api-key.yaml` with the following contents:

```yaml

apiVersion: v1
kind: Secret
metadata:
  name: prefect-api-key
  namespace: prefect
type: Opaque
data:
  key:  <base64-encoded-api-key>
```


Replace `<base64-encoded-api-key>` with your Prefect Cloud API key encoded in base64. The helm chart looks for a secret of this name and schema, this can be overridden in the `values.yaml`.

You can use the following command to generate the base64-encoded value:

```bash

echo -n "your-prefect-cloud-api-key" | base64
```


Apply the `api-key.yaml` file to create the Kubernetes secret:

```bash

kubectl apply -f api-key.yaml
```


## Step 4: Configure Prefect Worker Values

Create a `values.yaml` file to customize the Prefect worker configuration. Add the following contents to the file:

```yaml
worker:
  cloudApiConfig:
    accountId: <target account ID>
    workspaceId: <target workspace ID>
  config:
    workPool: <target work pool name>
```

These settings will ensure that the worker connects to the proper account, workspace, and work pool. 

View your Account ID and Workspace ID in your browser URL when logged into Prefect Cloud. For example: https://app.prefect.cloud/account/abc-my-account-id-is-here/workspaces/123-my-workspace-id-is-here.

## Step 5: Install Prefect Worker Using Helm

Now you can install the Prefect worker using the Helm chart with your custom `values.yaml` file:

```bash

helm install prefect-worker prefect/prefect-worker \
  --namespace=prefect \
  -f values.yaml
```


## Step 6: Verify Deployment

Check the status of your Prefect worker deployment:

```bash

kubectl get pods -n prefect
```



You should see the Prefect worker pod running.
## Conclusion

You have now successfully deployed a Prefect worker using the Prefect Helm chart and configured the API key as a Kubernetes secret. The worker will now be able to communicate with Prefect Cloud and execute your Prefect flows.
