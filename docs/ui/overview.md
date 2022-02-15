---
description: Accessing and configuring the Prefect Orion UI.
tags:
    - Orion
    - UI
    - dashboard
    - configuration
    - Cloud
---

# Orion UI Overview

The Prefect Orion UI provides an overview of all of your flows. It was designed around a simple question: what's the health of my system?

The UI displays many useful insights about your flow runs, including:

- Flow run summaries
- Deployed flow details
- Scheduled flow runs
- Warnings for late or failed runs
- Task run details 
- Radar flow and task dependency visualizer 
- Logs

You can filter the information displayed in the UI by time, flow status, and tags.

## Using the Orion UI

The UI is available in any environment where the Prefect Orion server is running with `prefect orion start`.

When Prefect Server is running, you can access the UI at [http://127.0.0.1:4200](http://127.0.0.1:4200).

![Prefect Orion UI dashboard.](/img/ui/orion-dashboard.png)

<!-- ## Prefect Cloud

Prefect Cloud provides a hosted server and UI instance for running and monitoring deployed flows. Prefect Cloud includes:

- All of the UI features of the local Orion server UI.
- The ability to invite and manage teams. 
- The option to create multiple workspaces to organize flows by team, project, or business function.

See the [Prefect Cloud](/ui/cloud.md) documentation for details about setting up accounts, workspaces, and teams. -->

## Accessing a remote Orion UI

If you are running a Prefect Orion server in a remote environment, such as a Docker container or Kubernetes cluster, you can access the UI in the remote environment via a forwarded public port.

### Forwarding Orion ports to Docker

### Forwarding Orion ports to Kubernetes

To access the Orion UI running in a Kubernetes cluster, use the `kubectl port-forward` command to forward a port on your local machine to an open port within the cluster. For example:

```bash
kubectl port-forward deployment/orion 4200:4200
```

This forwards port 4200 on the default internal loop IP for localhost to the “orion” deployment. You’ll see output like this:

To tell the local `prefect` command how to communicate with the Orion API running in Kubernetes, set the `PREFECT_API_URL` environment variable:

```bash
export PREFECT_API_URL=http://localhost:4200/api
```

Since you previously configured port forwarding for the localhost port to the Kubernetes environment, you’ll be able to interact with the Orion API running in Kubernetes when using local Prefect CLI commands.

For a demonstration, see the [Running flows in Kubernetes](/tutorials/kubernetes-flow-runner/) tutorial.

<!-- This section to be removed for moved to dev docs closer to release -->
## Using the dev UI

If you're working directly with the Prefect Orion repository &mdash; whether for contributing to Prefect or simply developing against the very latest codebase &mdash; you may need to utilize the `prefect dev` CLI commands to build the UI or launch a hot-reloading server instance.

If the UI has not been built, you'll see output like the following noting that the "dashboard is not built" when starting the Orion server:

```bash
❯ prefect orion start
Starting...

 ___ ___ ___ ___ ___ ___ _____    ___  ___ ___ ___  _  _
| _ \ _ \ __| __| __/ __|_   _|  / _ \| _ \_ _/ _ \| \| |
|  _/   / _|| _|| _| (__  | |   | (_) |   /| | (_) | .` |
|_| |_|_\___|_| |___\___| |_|    \___/|_|_\___\___/|_|\_|

Configure Prefect to communicate with the server with:

    prefect config set PREFECT_ORION_HOST=http://127.0.0.1:4200/api

The dashboard is not built. It looks like you're on a development version.
See `prefect dev` for development commands.
```

To install dependencies and build the UI, run the following command:

```bash
prefect dev build-ui
```

When the build process completes, start the server and UI with `prefect orion start`.

To see other options for running the server or UI in development mode, run `prefect dev --help`.