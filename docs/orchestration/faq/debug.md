---
sidebarDepth: 2
---
# Debugging Flows running with a Prefect API

 [[toc]]

## My flow is stuck in a `Scheduled` state!

The most likely culprit when a flow is stuck in a Scheduled state is agent misconfiguration. A Scheduled state whose start time is past means that no agent was able to retrieve the flow run and submit it for execution (which, in normal operation, is indicated by the Flow Run entering a `Submitted` state).

Here are some tips for debugging your agent:

1. Verify that your agent is running on your desired platform
2. If using Prefect Cloud as your backend API, confirm that the API key given to the agent is set to the same tenant as the flow

```bash
$ PREFECT__CLOUD__API_KEY="YOUR-KEY" prefect get flows
# If you do not see your flow then there is a tenant mismatch
```
3. Open an issue on [GitHub](https://github.com/PrefectHQ/prefect/issues/new/choose)!

## My flow is stuck in a `Submitted` state!

Having flows stuck in a Submitted state most commonly indicates an issue with your execution platform (e.g., a full Kubernetes Cluster). A Submitted state means that an Agent found the flow run and _attempted_ to submit it for execution, but something is preventing the Flow Run from entering a Running state.  Note that Flow Runs which stay in Submitted states for too long are eventually "resurrected" and rescheduled with Cloud's [Lazarus Process](services.html#lazarus).

Here are are some steps for debugging issues in execution:

1. Check the agent logs to see if anything obvious stands out (running an agent with the `--show-flow-logs` could show more useful output)
2. Verify that your platform has the proper services running (e.g. Docker daemon for Local Agent) or permissions configured (e.g. RBAC for Kubernetes Agent)
3. Open an issue on [GitHub](https://github.com/PrefectHQ/prefect/issues/new/choose)!
