
# Debugging Flows in Cloud

 [[toc]]

### My flow is stuck in scheduled!

The most likely culprit when a flow is stuck in scheduled is agent misconfiguration. Here are some steps for debugging your agent:

1. Verify that your agent is running on your desired platform
2. Check that the API token given to the agent is scoped to the same tenant as your flow

```
$ export PREFECT__CLOUD__AUTH_TOKEN=YOUR_TOKEN
$ prefect get flows
# if you do not see your flow then there is a tenant mismatch
```

3. Open an issue on [GitHub](https://github.com/PrefectHQ/prefect/issues/new/choose)!

### My flow is stuck in submitted!

Having flows stuck in submitted most commonly indicates an issue with your execution platform. Here are are some steps for debugging issues in execution:

1. Check the agent logs to see if anything obvious stands out
2. Verify that your platform has the proper services running (e.g. Docker daemon for Local Agent) or permissions configured (e.g. RBAC for Kubernetes Agent)
3. Open an issue on [GitHub](https://github.com/PrefectHQ/prefect/issues/new/choose)!

### "Update failed: bad version"

Occasionally a task run will fail with the message "update failed: bad version." This is due to Prefect Cloud's state locking mechanism, and actually means the system is working as intended.
