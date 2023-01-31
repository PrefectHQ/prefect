# Dashboard

<div style="border: 2px solid #27b1ff; border-radius: 10px; padding: 1em;">
Looking for the latest <a href="https://docs.prefect.io/">Prefect 2</a> release? Prefect 2 and <a href="https://app.prefect.cloud">Prefect Cloud 2</a> have been released for General Availability. See <a href="https://docs.prefect.io/">https://docs.prefect.io/</a> for details.
</div>

## Overview

The UI's dashboard provides an overview of all of your flows. It was designed around a simple question:

> What's the health of my system?

To answer this question, the dashboard surfaces many insights, including summaries of recent runs, links to error logs, descriptions of upcoming runs (including warnings for late runs), an activity timeline, and (when using Prefect Cloud) agent monitoring.

The dashboard may be filtered by period, starting with the last 24 hours and when using Prefect Cloud it may also be filtered by [project](/orchestration/concepts/projects).

![](/orchestration/ui/dashboard-overview.png)

## Agents Page <Badge text="Cloud"/>

The Agents page shows any [Prefect Agents](/orchestration/agents/overview) that have recently interacted with your Prefect Cloud instance. Agents are considered "healthy" if they have interacted with Cloud in the last minute (typically, agents ping every 10 seconds), and "unhealthy" after a few minutes have gone by.
![](/orchestration/ui/dashboard-agents.png)
