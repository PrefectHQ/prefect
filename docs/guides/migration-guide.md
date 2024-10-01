---
description: Migrate your workflows to Prefect 3.0.
tags:
    - migration
    - upgrading
    - best practices
search:
  boost: 2
---

# Migrating from Prefect 1.0 to Prefect 3.0

Learn how to migrate your workflows from Prefect 1.0 to Prefect 3.0. Check out the [quickstart](https://docs.prefect.io/latest/get-started/quickstart) for a high level overview.

!!! Note "What about Prefect 2?"
  Prefect 2 refers to the 2.x lineage of the open source prefect package, and Prefect 3.0 refers exclusively to the 3.x lineage of the prefect package. Neither version is strictly tied to any aspect of Prefect’s commercial product, [Prefect Cloud](https://docs.prefect.io/latest/manage/cloud/index).

## What stayed the same

Prefect 3.0 still:

- Has [tasks](https://docs.prefect.io/latest/develop/write-tasks) and [flows](https://docs.prefect.io/latest/develop/write-flows).
- Orchestrates your flow runs and provides observability into their execution [states](https://docs.prefect.io/latest/develop/manage-states).
- Employs the same hybrid execution model, where Prefect doesn't store your flow code or data.

## What changed

Prefect 3.0 requires modifications to your existing tasks, flows, and deployment patterns. We've organized this section into the following categories:


- **Simplified patterns** &mdash; abstractions from Prefect 1.0 that are no longer necessary in the dynamic, DAG-free Prefect workflows that support running native Python code in your flows.
- **Conceptual and syntax changes** &mdash; that often clarify names and simplify familiar abstractions such as retries and caching.
- **New features** &mdash; enabled by the dynamic and flexible Prefect API.

### Simplified patterns

Since Prefect 3.0 allows running native Python code within the flow function, some abstractions were no longer necessary:

- `Parameter` tasks: in Prefect 3.0, args and kwargs to your flow function are automatically treated as [parameters](https://docs.prefect.io/latest/develop/write-flows#specify-flow-parameters) of your flow. You can populate the parameter values when you create a deployment, or when you schedule an ad-hoc flow run. One benefit of Prefect parametrization is built-in type validation with [pydantic](https://docs.pydantic.dev/latest/).
- `Signals`: in Prefect 3.0 you can raise an arbitrary exception in your task or flow and return a custom state.
- `Conditional logic`: conditional tasks such as `case` were no longer required. Use Python native `if...else` statements to build a conditional logic.
- `Resource manager`: since you can use any context manager directly in your flow, a `resource_manager` was no longer necessary. As long as you point to your flow script in your deployment, you can share database connections and any other resources between tasks in your flow.

### Conceptual and syntax changes

The changes listed below require you to modify your flow code. The following table shows how Prefect .0 concepts have been implemented in Prefect 3.0. The last column contains references to additional resources that provide more details and examples.

| Concept                                                                | Prefect 1.0                                                                                                                               | Prefect 3.0                                                                                                                                                                                                      | Reference links                                                                                                                                                                                 |
| ---------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Flow definition.                                                       | `with Flow("flow_name") as flow:`                                                                                                       | `@flow(name="flow_name")`                                                                                                                                                                                      | [Write and run flows](https://docs.prefect.io/latest/develop/write-flows)                                                                                                           |
| Flow executor that determines how to execute your task runs.           | Executor such as `LocalExecutor`.                                                                                                       | Task runner such as `ThreadPoolTaskRunner`.                                                                                                                                                                    | [Run tasks concurrently or in parallel](https://docs.prefect.io/latest/develop/task-runners)                                                                         |
| Configuration that determines how and where to execute your flow runs. | Run configuration such as `flow.run_config = DockerRun()`.                                                                              | Create a deployment of your flow that uses an infrastructure specific work-pool.                                                       | [Deploy overview](https://docs.prefect.io/latest/deploy/index)                                                                   |
| Assignment of schedules and default parameter values.                  | Schedules were attached to the flow object and default parameter values were defined within the Parameter tasks.                          | Schedules and default parameters are assigned to a flow’s `Deployment`, rather than to a Flow object.                                                                                                          | [Workflow scheduling and parametrization](https://docs.prefect.io/latest/deploy/index#workflow-scheduling-and-parametrization)                                                                               |
| Retries                                                                | `@task(max_retries=2, retry_delay=timedelta(seconds=5))`                                                                                | `@task(retries=2, retry_delay_seconds=5)`                                                                                                                                                                      | [Retries](https://docs.prefect.io/latest/develop/write-tasks#retries)                                         |
| Logging                                                                | Logger was retrieved from `prefect.context` and could only be used within tasks.                                                           | Logger is retrieved from `prefect.get_run_logger()` in both flows and tasks.                                                                               | [Configure logging](https://docs.prefect.io/latest/develop/logging)                                                                                               |
| The syntax and contents of Prefect context.                            | Context was a thread-safe way of accessing variables related to the flow run and task run. The syntax to retrieve it: `prefect.context`. | Context is still available, but its content is much richer, allowing you to retrieve even more information about your flow runs and task runs. The syntax to retrieve it: `prefect.context.get_run_context()`. | [Access runtime context](https://docs.prefect.io/latest/develop/runtime-context)                                                                                 |
| Task library.                                                          | Included in the [main Prefect Core repository](https://docs-v1.prefect.io/core/task_library/overview.html).                                | Separated into [individually installable packages](https://docs.prefect.io/integrations/integrations) per system, cloud provider, or technology.                                                                                                            | [Use integrations](https://docs.prefect.io/integrations/use-integrations). |

### What changed in orchestration?

Let’s look at the differences in how Prefect 3.0 transitions your flow and task runs between various execution states.

- In Prefect 3.0, the final state of a flow run that finished without errors is `Completed`, while in Prefect 1.0, this flow run had a `Success` state. You can find more about that topic [here](https://docs.prefect.io/latest/develop/manage-states#final-state-determination).
- The decision about whether a flow run should be considered successful or not is no longer based on special reference tasks. Instead, your flow’s return value determines the final state of a flow run.
- In Prefect 1.0, concurrency limits were only available to Prefect Cloud users. Prefect 3.0 provides rich concurrency controls across several levels, including on [tasks](https://docs.prefect.io/latest/develop/task-run-limits), [work-pools](https://docs.prefect.io/latest/deploy/infrastructure-concepts/work-pools#manage-concurrency), and [as code](https://docs.prefect.io/latest/develop/global-concurrency-limits).


### What changed in flow deployment patterns?

To deploy your Prefect 1.0 flows, you had to send flow metadata to the backend in a step called registration. Prefect 3.0 no longer requires flow pre-registration. Flows can be invoked directly as code or locally [served](https://docs.prefect.io/latest/deploy/run-flows-in-local-processes). To leverage [dynamically provisioned infrastructure](https://docs.prefect.io/latest/deploy/infrastructure-concepts/work-pools), you can create a `deployment` which specifies:

- What infrastructure to run your flow on ([work pool type](https://docs.prefect.io/latest/deploy/infrastructure-concepts/work-pools#work-pool-types)).
- Where to access your [flow code](https://docs.prefect.io/latest/deploy/infrastructure-concepts/store-flow-code).
- When to run your flow (an `Interval`, `Cron`, or `RRule` schedule).
- How to run your flow (execution details such as `parameters`, flow deployment `name`, and [more](https://docs.prefect.io/latest/deploy/index#deployment-schema)).

The API is now implemented as a REST API rather than GraphQL. [This page](https://docs.prefect.io/latest/api-ref/rest-api/index) illustrates how you can interact with the API.

In Prefect 1.0, the logical grouping of flows was based on [projects](https://docs-v1.prefect.io/orchestration/concepts/projects.html). Prefect 3.0 provides a much more flexible way of organizing your flows, tasks, and deployments through customizable filters and tags as well as robust isolation using Prefect Cloud [workspaces](https://docs.prefect.io/latest/manage/cloud/workspaces).

Prefect 1.0 agents are called workers in Prefect 3.0, but are still typed based on infrastructure.

## New features introduced in Prefect 3.0

The following new components and capabilities are enabled by Prefect 3.0:

- More Pythonic thanks to the elimination of flow pre-registration.
- More flexibility for flow deployments, including easier promotion of a flow through development, staging, and production environments.
- Native `async` support.
- Out-of-the-box `pydantic` validation.
- [Blocks](https://docs.prefect.io/latest/develop/blocks) allow you to securely store UI-editable, type-checked configuration to external systems. All those components are configurable in one place and provided as part of the open-source Prefect 3.0 product. In contrast, the concept of [Secrets](https://docs-v1.prefect.io/orchestration/concepts/secrets.html) in Prefect 1.0 was more narrowly scoped and only available in Prefect Cloud.
- [Automations](https://docs.prefect.io/latest/automate/events/automations-triggers) provide an expressive API to define triggers (based on events) and actions. Automations power notifications and much more.
- Every flow state change, task state change, and more produces a corresponding event which can be the basis of an automation trigger.
- First-class support for `subflows` which enables a natural and intuitive way of organizing your flows into modular sub-components. In contrast, Prefect 1.0 only allowed the [flow-of-flows orchestrator pattern](https://docs-v1.prefect.io/core/idioms/flow-to-flow.html).

### Orchestration behind the API

Apart from new features, Prefect 3.0 simplifies many usage patterns and provides a much more seamless onboarding experience.

Every time you run a flow, whether it is tracked by the API server or ad-hoc through a Python script, it is on the same UI page for easier debugging and observability. 

### Code as workflows

With Prefect 3.0, your functions *are* your flows and tasks. Prefect 3.0 automatically detects your flows and tasks without the need to define a rigid DAG structure. While use of tasks is encouraged to provide you the maximum visibility into your workflows, they are no longer required. You can add a single `@flow` decorator to your main function to transform any Python script into a Prefect workflow.

### Fewer ambiguities

Prefect 3.0 eliminates ambiguities in many ways. For example. there is no more confusion between Prefect Core and Prefect Server &mdash; Prefect 3.0 unified those into a single open source product. This product is also much easier to deploy with no requirement for Docker or docker-compose.

If you want to switch your backend to use Prefect Cloud for an easier production-level managed experience, Prefect profiles let you quickly connect to your workspace.


In Prefect 1.0, there were several confusing ways you could implement `caching`. Prefect 3.0 resolves those ambiguities by providing a single `cache_policy` function paired with `cache_expiration`, allowing you to define arbitrary [caching mechanisms](https://docs.prefect.io/latest/develop/task-caching) &mdash; no more confusion about whether you needed to use `cache_for`, `cache_validator`, or file-based caching using `targets`.

A similarly confusing concept in Prefect 1.0 was distinguishing between the functional and imperative APIs. This distinction caused ambiguities with respect to how to define state dependencies between tasks. Prefect 1.0 users were often unsure whether they should use the functional `upstream_tasks` keyword argument or the imperative methods such as `task.set_upstream()`, `task.set_downstream()`, or `flow.set_dependencies()`. In Prefect 3.0, there is only the functional API.


## Next steps

We know migrations can be tough. We encourage you to take it step-by-step and experiment with the new features.

To make the migration process easier for you:

- We have dedicated resources in the Customer Success team to help you along your migration journey. Reach out to [help@prefect.io](mailto:help@prefect.io) to discuss how we can help.
- You can ask questions in our 30,000+ member [Community Slack](https://prefect.io/slack).


---
Happy Engineering!
