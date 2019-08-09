# k8s-agent

The Prefect Kubernetes agent that turns a cluster into a workflow execution platform, orchestrated by Prefect Cloud.

If running on GKE you may need to execute: `kubectl create clusterrolebinding default-admin --clusterrole cluster-admin --serviceaccount=default:default`

Quick Start:

- Build Dockerfile and push to registry
- Update the `image` and `PREFECT__CLOUD__AUTH_TOKEN` env value in the deployment yaml
- Run `kubectl apply -f deployment.yaml`
