# Scheduled Flows

If a flow has a schedule, then Cloud can automatically create new flow runs according to that schedule.

Scheduling is nothing more than a convenient way to generate new runs, and users can still create ad-hoc runs alongside the auto-scheduled ones (even if they have the same start time). The only difference is that auto-scheduled runs have an `auto_scheduled=True` flag set.

You can turn auto-scheduling on or off at any time:

```graphql
mutation {
  setFlowScheduleState(input: {flowId: "<flow id>", setActive: <true>/<false>}) {
      success
  }
}
```

::: warning Scheduling with parameters
Prefect can not auto-schedule flows that have required parameters, because the scheduler won't be able to supply a value. You will get an error if you try to turn on scheduling for such a flow.

To resolve this, provide a default value for your parameters in Core:

```python
from prefect import Parameter

x = Parameter('x', defualt=1)
```

:::
