# Scheduling flow runs

If a flow has a schedule attached, then the Prefect backend can [automatically create new flow runs](#scheduled-flow-run-creation) according to that schedule.

!!! tip
    Scheduling in this manner is nothing more than a convenient way to generate new runs; you can still create ad-hoc runs alongside the auto-scheduled ones (even if they have the same start time).
:::

Flow schedules can be defined when your flow is registered using the Prefect Core library or after registration using the Prefect API or UI. For details on defining a schedule at registration time, see the [Core scheduling documentation](../../core/concepts/schedules.md). The Core documentation will also be useful for understanding the basic building blocks of schedules, but if you'd like to venture forward here's a quick summary:

- Flows can have as many schedules as you want
- Flows have two types of schedules: `CronClock` (datetime based) and `IntervalClock` (every x seconds)
- Schedules are independent; if schedules overlap, multiple flow runs will be created
- Schedules can set flow parameter values

If you're looking to run a flow _once_ in the future instead of creating a recurring schedule you can create a flow run with a specified start time. See the [flow run creation documentation](./creation.md#start-times) for details.

## Creating flow schedules <Badge text="GQL" />

Flow schedules are attached to the flow group and can be set using the `set_flow_group_schedule` mutation.

!!! warning Existing schedules
    Setting flow group schedules will remove any existing schedules.
:::

!!! tip Scheduling in the Prefect UI
    The UI provides a friendly interface for setting schedules in the [flow group settings page](../ui/flow.md#settings).
    The UI will preserve existing schedules and generate CRON clocks for you.
:::

In this example, two interval clocks are set for a flow group. The first runs every hour and sets the parameter `name` to `"Marvin 1hr"`. The second runs every two hours and sets the parameter `name` to `"Marvin 2hr"`.

```graphql
mutation {
  set_flow_group_schedule(
    input: {
      flow_group_id: "<flow-group-id>", 
      interval_clocks: [
        {interval: 3600, parameter_defaults: "{\"name\": \"Marvin 1hr\"}"}
        {interval: 7200, parameter_defaults: "{\"name\": \"Marvin 2hr\"}"}
      ]
    }
  ) {
    success
  }
}
```

In the next example, a single cron clock is set for a flow group. This clock will run the flow at 12:00 PM Monday, Wednesday, and Friday. The parameters will retain their default values.

```graphql
mutation {
  set_flow_group_schedule(
    input: {
      flow_group_id: "947c0966-a7b2-452b-a7da-2051415dbddf", 
      cron_clocks: [{cron: "0 12 * * 1,3,5"}]
    }
  ) {
    success
  }
}
```

!!! warning Scheduling with parameters
    Prefect cannot auto-schedule flows that have required parameters, because the scheduler won't know what value to use. You will get an error if you try to turn on scheduling for such a flow.

    To resolve this, provide a default value for your parameters in your flow code or the schedule clock:

    ```python
    from prefect import Parameter

    x = Parameter('x', default=1)
    ```

    ```graphql
    {..., parameter_defaults: "{\"x\": 1}"}
    ```
:::

## Scheduled flow run creation

Flows with an active schedule will have some of their flow runs created ahead of time. These flow runs will have a scheduled start time and will not begin executing until then. When a flow schedule is updated, these generated runs will be deleted and new runs will be created. Scheduled flow run creation is handled by the [Prefect Scheduler](../concepts/services.md#scheduler).


## Querying for flow schedules <Badge text="GQL" />

To query for schedules on a flow group, you can select the `schedule` property.

```graphql
query {
  flow_group(where: {id: {_eq: "<flow-group-id>"}}) {
    schedule
  }
}
```

Example return value

```json
{
  "data": {
    "flow_group": [
      {
        "schedule": {
          "type": "Schedule",
          "clocks": [
            {
              "cron": "0 0 * * 1,3,5",
              "type": "CronClock",
              "start_date": {
                "dt": "2021-05-07T10:24:07.143675",
                "tz": "America/Chicago"
              }
            },
            {
              "type": "IntervalClock",
              "interval": 3600000000,
              "start_date": {
                "dt": "2021-05-07T10:24:07.143675",
                "tz": "America/Chicago"
              },
              "parameter_defaults": {
                "name": "Marvin"
              }
            }
          ]
        }
      }
    ]
  }
}
```

## Toggling flow schedules <Badge text="GQL"/>

You can turn auto-scheduling on or off at any time:

```graphql
mutation {
  set_schedule_active(input: {
    flow_id: "<flow-id>"
  }) {
    success
  }
}
```

```graphql
mutation {
  set_schedule_inactive(input: {
    flow_id: "<flow-id>"
  }) {
    success
  }
}
```
