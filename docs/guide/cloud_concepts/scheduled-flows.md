# Auto-Scheduled Flows

If a flow has a `schedule` attached, then Cloud can automatically create new flow runs according to that schedule.

Scheduling in this manner is nothing more than a convenient way to generate new runs; users can still create ad-hoc runs alongside the auto-scheduled ones (even if they have the same start time).

You can turn auto-scheduling on or off at any time: <Badge text="GQL"/>

```graphql
mutation {
  setFlowScheduleState(input: { flowId: "<flow id>", setActive: true }) {
    success
  }
}
```

::: warning Scheduling with parameters
Prefect cannot auto-schedule flows that have required parameters, because the scheduler won't know what value to use. You will get an error if you try to turn on scheduling for such a flow.

To resolve this, provide a default value for your parameters in Core:

```python
from prefect import Parameter

x = Parameter('x', default=1)
```
:::
