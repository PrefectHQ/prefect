# k8s-agent

The Prefect Kubernetes agent that turns a cluster into a workflow execution platform, orchestrated by Prefect Cloud.

If running on GKE you may need to execute: `kubectl create clusterrolebinding default-admin --clusterrole cluster-admin --serviceaccount=default:default`

The agent needs to be able to read, list, and create both pods and jobs. The resource manager aspect needs the same permissions with the added role of being able to delete jobs and pods.

Quick Start:

- Build Dockerfile and push to registry
- Update the `image` and `PREFECT__CLOUD__API_TOKEN` env value in the deployment yaml
- Run `kubectl apply -f deployment.yaml`
