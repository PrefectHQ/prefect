# Dashboard

## Overview

![](/cloud/ui/dashboard-overview.png)

The Cloud dashboard provides an overview of all of your team's flows. It was designed around a simple question:

> What's the health of my system?

To answer this question, the dashboard surfaces many insights, including:

- a summary of recent runs
- links to error logs
- a description of all upcoming runs
- recent flow state updates
- links to any failed flows
- monitoring for agents

Colors and icons help indicate if attention is required.

## Agents

![](/cloud/ui/dashboard-agents.png)

The Agents page shows any [Prefect Agents](/cloud/agent) that have recently interacted with your Prefect Cloud instance. Agents are considered "healthy" if they have interacted with Cloud in the last minute (typically, agents ping every 10 seconds), and "unhealthy" after a few minutes have gone by.
