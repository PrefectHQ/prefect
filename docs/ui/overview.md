---
description: Accessing and configuring the Prefect Orion UI.
tags:
    - Orion
    - UI
    - dashboard
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

You can filter the information displayed in the UI by time, flow state, and tags.

## Using the Orion UI

The UI is available in any environment where the Prefect Orion server is running with `prefect orion start`.

When Prefect Server is running, you can access the UI at [http://127.0.0.1:4200](http://127.0.0.1:4200).

![Prefect Orion UI dashboard.](/img/ui/orion-dashboard.png)

The following sections provide details about Orion UI pages and visualizations:

- [Dashboard](/ui/dashboard/) provides a high-level overview of your flows, tasks, and deployments.
- [Flows and Tasks](/ui/flows-and-tasks/) pages let you dig into details of flow runs and task runs.
- [Filters](/ui/filters/) enable you to customize the display based on flow state, tags, execution time, and more.

<!-- ## Prefect Cloud

Prefect Cloud provides a hosted server and UI instance for running and monitoring deployed flows. Prefect Cloud includes:

- All of the UI features of the local Orion server UI.
- The ability to invite and manage teams. 
- The option to create multiple workspaces to organize flows by team, project, or business function.

See the [Prefect Cloud](/ui/cloud.md) documentation for details about setting up accounts, workspaces, and teams. -->

<!-- This section to be removed for moved to dev docs closer to release -->
## Using the dev UI

If you're working directly with the Prefect Orion repository &mdash; whether for contributing to Prefect or simply developing against the very latest codebase &mdash; you may need to utilize the `prefect dev` CLI commands to build the UI or launch a hot-reloading server instance.

If the UI has not been built, you'll see output like the following noting that the "dashboard is not built" when starting the Orion server:

```bash
$ prefect orion start
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