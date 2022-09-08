---
description: Migrate your workflows to Prefect 2.
tags:
    - migration
    - upgrading
    - best practices
---

# Migrating from Prefect 1 to Prefect 2

This guide helps you migrate your workflows from Prefect 1 (and lower) to Prefect 2. 
It is broken down into several sections to make your migration journey as seamless as possible.

## What stayed the same

Let’s start by explicitly calling out what hasn’t changed:

- The fundamental building blocks you are so familiar with: [tasks](../concepts/tasks/) and [flows](../concepts/flows/)
- The main functionality of how Prefect orchestrates your flow runs and task runs, and provides observability into their execution [states](../concepts/states/)
- The ability to [run and inspect flow runs locally](https://discourse.prefect.io/t/how-can-i-inspect-the-flow-run-states-locally/81)
- The [principles](https://medium.com/the-prefect-blog/your-code-will-fail-but-thats-ok-f0327a208dbe) of Prefect providing the coordination plane for your dataflows
- The [hybrid execution model](https://medium.com/the-prefect-blog/the-prefect-hybrid-model-1b70c7fd296)

## What changed

Some changes require modifications to your existing tasks, flows, and deployment patterns. For more transparency, we've organized this information in the following categories:

- **Simplified patterns** &mdash; abstractions that had their place in Prefect 1, but that are no longer necessary in the dynamic, DAG-free Prefect Orion workflows that support running native Python code in your flows.
- **Conceptual and syntax changes** that often clarify the naming and simplify familiar abstractions such as retries and caching.
- **New features** enabled by the dynamic and flexible Prefect Orion API.

### Simplified patterns

Since Prefect 2 allows running native Python code within the flow function, some abstractions are no longer necessary:

- `Parameter` tasks: in Prefect 2, inputs to your flow function are automatically treated as [parameters](../concepts/flows/#parameters) of your flow. You can define the default parameter values in your `Deployment`. The additional benefit to Orion’s parametrization is type validation with [pydantic](https://pydantic-docs.helpmanual.io/).
- Task-level `state_handlers`: in Prefect 2, you can build custom logic that reacts to task-run states within your flow function without the need for `state_handlers`. [The page "
  How to take action on a state change of a task run"](https://discourse.prefect.io/t/how-to-take-action-on-a-state-change-of-a-task-run-task-level-state-handler/82) provides a further explanation and code examples.
- Instead of using `signals`, Prefect 2 allows you to raise an arbitrary exception in your tasks and flows or return a custom state. For more details and examples, see [How can I stop the task run based on a custom logic](https://discourse.prefect.io/t/how-can-i-end-the-task-run-based-on-a-custom-logic/83).
- Conditional tasks such as `case` are no longer required. Use Python native `if...else` statements to build a conditional logic. [The Discourse tag "conditional-logic"](https://discourse.prefect.io/tag/conditional-logic) provides more resources.
- Since you can use any context manager directly in your flow, `resource_manager` is no longer necessary. As long as you point to your flow script in your `Deployment`, you can share database connections and any other resources between tasks in your flow. The Discourse page [How to clean up resources used in a flow](https://discourse.prefect.io/t/how-to-clean-up-resources-used-in-a-flow/84) provides a full example.

### Conceptual and syntax changes

The changes listed below require you to modify your workflow code. The following table shows how Prefect 1 concepts have been implemented in Prefect 2. The last column contains references to additional resources that provide more details and examples.

| Concept | Prefect 1 | Prefect 2 | Reference links |
| --- | --- | --- | --- |
| Flow definition. | `with Flow("flow_name") as flow:` | `@flow(name="flow_name")` | [How can I define a flow?](https://discourse.prefect.io/t/how-can-i-define-a-flow/28) |
| Flow executor that determines how to execute your task runs. | Executor such as `LocalExecutor`. | Task runner such as `ConcurrentTaskRunner`. | [What is the default TaskRunner (executor)?](https://discourse.prefect.io/t/what-is-the-default-taskrunner-executor/63) |
| Configuration that determines how and where to execute your flow runs. | Run configuration such as `flow.run_config = DockerRun()`. | Flow runner defined on a Deployment such as `Deployment(flow_runner=DockerFlowRunner)`. | [How can I run my flow in a Docker container?](https://discourse.prefect.io/t/how-can-i-run-my-flow-in-a-docker-container/64) |
| Assignment of schedules and default parameter values. | Schedules are attached to the flow object and default parameter values are defined within the Parameter tasks. | Schedules and default parameters are assigned to a flow’s `Deployment`, rather than to a Flow object.  | [How can I attach a schedule to a flow?](https://discourse.prefect.io/t/how-can-i-attach-a-schedule-to-a-flow/65)  |
| Retries | `@task(max_retries=2, retry_delay=timedelta(seconds=5))` | `@task(retries=2, retry_delay_seconds=5)`  | [How can I specify the retry behavior for a specific task?](https://discourse.prefect.io/t/how-can-i-specify-the-retry-behavior-for-a-specific-task/60) |
| Logger syntax. | Logger is retrieved from `prefect.context` and can only be used within tasks. | In Prefect 2, you can log not only from tasks, but also within flows. To get the logger object, use: `prefect.get_run_logger()`. | [How can I add logs to my flow?](https://discourse.prefect.io/t/how-can-i-add-logs-to-my-flow/86)   |
| The syntax and contents of Prefect context. | Context is a thread-safe way of accessing variables related to the flow run and task run. The syntax to retrieve it: `prefect.context`. | Context is still available, but its content is much richer, allowing you to retrieve even more information about your flow runs and task runs. The syntax to retrieve it: `prefect.context.get_run_context()`. | [How to access Prefect context values?](https://discourse.prefect.io/t/how-to-access-prefect-context-values/62) |
| Task library. | Included in the [main Prefect Core repository](https://docs.prefect.io/core/task_library/overview.html). | Separated into [individual repositories](../collections/catalog/) per system, cloud provider, or technology. | [How to migrate Prefect 1 tasks to Prefect 2 collections](https://discourse.prefect.io/t/how-to-migrate-prefect-1-0-task-library-tasks-to-a-prefect-collection-repository-in-prefect-2-0/792). |

### What changed in workflow orchestration?

Let’s look at the differences in how Prefect 2 transitions your flow and task runs between various execution states.

- In Prefect 2, the final state of a flow run that finished without errors is `Completed`, while in Prefect 1, this flow run has a `Success` state. You can find more about that topic [here](https://discourse.prefect.io/t/what-is-the-final-state-of-a-successful-flow-run/59).
- The decision about whether a flow run should be considered successful or not is no longer based on special reference tasks. Instead, your flow’s return value determines the final state of a flow run. This [link](https://discourse.prefect.io/t/how-can-i-control-the-final-state-of-a-flow-run/56) provides a more detailed explanation with code examples.
- In Prefect 1, concurrency limits were only available to Prefect Cloud users. Prefect 2 provides highly customizable concurrency limits as part of the open-source product.
    - Task-level concurrency limits are based on tags that you can set within your flow.
    - Flow-level concurrency limits are based on a work queue that the agent pulls from.
    - The [following page](https://discourse.prefect.io/t/how-can-i-impose-concurrency-limits-for-flow-and-task-runs/87) provides further explanation.

### What changed in flow deployment patterns?

To deploy your Prefect 1 flows, you have to send flow metadata to the backend in a step called registration. To make this even easier for you, Prefect 2 no longer requires flow pre-registration. Instead, you can create a deployment that points to your flow object or flow’s code location and additionally provides details with respect to:

- Where to deploy your flow (your `flow_runner`, such as a `KubernetesFlowRunner`)
- When to run your flow (your schedule or an ad-hoc run triggered via an API call or from the UI)
- How to run your flow (execution and bookkeeping details such as `parameters`, `tags` used by work queues, flow deployment `name`, and [more](https://discourse.prefect.io/tag/deployment)).

The API is now implemented as a REST API rather than GraphQL. [This page](https://discourse.prefect.io/t/how-can-i-interact-with-the-backend-api-using-a-python-client/80) illustrates how you can interact with the API.

In Prefect 1, the logical grouping of flows was based on [projects](https://docs.prefect.io/orchestration/concepts/projects.html). Prefect 2 provides a much more flexible way of organizing your flows, tasks, and deployments through customizable filters and tags. [This page](https://discourse.prefect.io/t/how-can-i-organize-my-flows-based-on-my-business-logic-or-team-structure/66) provides more details on how to assign tags to various Prefect 2 objects.

The role of agents has changed between Prefect 1 and Prefect 2:

- In Prefect 1, agents are required to see the flow run history in the UI.
- In Prefect 2, agents and work queues are only required if you want to trigger flows via the Prefect UI or API.
- See [this Discourse page](https://discourse.prefect.io/t/whats-the-role-of-agents-and-work-queues-and-how-the-concept-of-agents-differ-between-prefect-1-0-and-2-0/689) for a more detailed description.

## New features introduced in Prefect 2

The following new components and capabilities are enabled by Prefect 2.

- More flexibility thanks to the elimination of flow pre-registration.
- More flexibility with respect to flow deployments, including easier promotion of a flow through development, staging, and production environments.
- Native `async` support.
- Out-of-the-box `pydantic` validation.
- [Blocks](../ui/blocks/) allowing you to securely store UI-editable, type-checked configuration to external systems and an easy-to-use Key-Value Store. All those components are configurable in one place and provided as part of the open-source Prefect 2 product. In contrast, the concept of [Secrets](https://docs.prefect.io/orchestration/concepts/secrets.html) in Prefect 1 was much more narrow and only available in Prefect Cloud.  
- [Notifications](../ui/notifications/) available in the open-source Prefect 2 version, as opposed to Cloud-only [Automations](https://docs.prefect.io/orchestration/ui/automations.html) in Prefect 1.  
- A first-class `subflows` concept: Prefect 1 only allowed the [flow-of-flows orchestrator pattern](https://discourse.prefect.io/tag/orchestrator-pattern), which is still supported. With Prefect 2 subflows, you are gaining a natural and intuitive way of organizing your flows into modular sub-components. For more details, see [the following list of resources about subflows](https://discourse.prefect.io/tag/subflows).


### Orchestration behind the API

Apart from new features, Prefect 2 simplifies many usage patterns and provides a much more seamless onboarding experience.

Every time you run a flow, it is tracked by the API even if you don’t know it; this brings both local and backend-triggered execution on the exact same page for better debugging and observability. This also allows you to use alternate schedulers (for example, a CRON job) when migrating to Prefect.

Similarly, because the API tracks every flow run behind the scenes, agentless deployments work out-of-the-box &mdash; if you want to manage your own flow execution, you can!

### Code as workflows

With Prefect 2, your functions *are* your flows. Prefect 2 automatically detects your flows and tasks without the need to define a rigid DAG structure. While use of tasks is encouraged to provide you the maximum visibility into your workflows, they are no longer required. You can add a single `@flow` decorator to your main function to transform any Python script into a Prefect workflow.

### Incremental adoption
The built-in SQLite database automatically tracks all your locally executed flow runs. As soon as you start Prefect Orion and open the Prefect UI in your browser (or [authenticate your CLI with your Prefect Cloud workspace](../ui/cloud-getting-started/)), you can see all your locally executed flow runs in the UI without having to spin up any additional components such as agents.

To compare that user experience to Prefect 1:

- Instead of starting an agent (`prefect agent local start`), you can start building and running flows, and then (optionally) start Prefect Orion to see the run history in the UI.
- Additionally, you can create a deployment to schedule and execute your flow on remote infrastructure, with the infrastructure being defined by a `flow_runner` configuration.

### Fewer ambiguities

Prefect 2 eliminates ambiguities in many ways. On the one hand, there is no more confusion between Prefect Core and Prefect Server &mdash; Prefect 2 unifies those into a single product. This product is also much easier to deploy with no requirement for Docker or docker-compose.

In Prefect 1, there were many ways you could implement `caching`, which was confusing to many users. Prefect 2 resolves those ambiguities by providing a single `cache_key_fn` function paired with `cache_expiration`, allowing you to define arbitrary caching mechanisms &mdash; no more confusion about whether you need to use `cache_for`, `cache_validator`, or file-based caching using `targets`.

In the future, we anticipate many cache key functions will be included directly in the Prefect 2 library. For more details on how to configure caching, check out the following resources:

- [Time-based caching](https://discourse.prefect.io/t/how-can-i-cache-a-task-result-for-two-hours-to-prevent-re-computation/67)
- [Input-based caching](https://discourse.prefect.io/t/how-can-i-cache-a-task-result-based-on-task-input-arguments/68)

A similarly confusing concept in Prefect 1 was distinguishing between a functional and imperative API. This distinction caused ambiguities with respect to how to define state dependencies between tasks. Prefect 1 users were often unsure whether they should use the functional `upstream_tasks` keyword argument or the imperative methods such as `task.set_upstream()`, `task.set_downstream()`, or `flow.set_dependencies()`. Prefect 2 resolves all those ambiguities by giving you a single argument for defining state dependencies called `wait_for`. In Prefect 2, there is only the functional API and you can use classes simply by calling those in your tasks and flows. For more details on this subject, see:

- [How can I define state dependencies between tasks?](https://discourse.prefect.io/t/how-can-i-define-state-dependencies-between-tasks/69)
- [Can I define my tasks as classes rather than functions?](https://discourse.prefect.io/t/can-i-define-my-tasks-as-classes-rather-than-functions/54)

## Next steps

Migrations are hard, we know that. We encourage you to take it step-by-step and experiment with the new features as you see fit.

To make the migration process easier for you:

- We provided [a detailed FAQ section](https://discourse.prefect.io/tag/migration-guide) allowing you to find the right information you need to move your workflows to Prefect 2. If you still have some open questions, feel free to create a new topic describing your migration issue.
- We have dedicated resources in the Customer Success team to help you along your migration journey. Reach out to [cs@prefect.io](mailto:cs@prefect.io) to discuss how we can help.  
- You can also ask us anything in our [Community Slack](https://prefect.io/slack).


---
Happy Engineering!