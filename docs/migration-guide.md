---
description: Migrate your workflows to Prefect 2.
tags:
    - migration
    - upgrading
    - best practices
---

# Migrating from Prefect 1 to Prefect 2

This guide is designed to help you migrate your workflows from Prefect 1 to Prefect 2. 

## What stayed the same

Prefect 2 still:

- Has [tasks](/concepts/tasks/) and [flows](/concepts/flows/).
- Orchestrates your flow runs and provides observability into their execution [states](/concepts/states/).
- [Runs and inspects flow runs locally](https://discourse.prefect.io/t/how-can-i-inspect-the-flow-run-states-locally/81).
- Provides a coordination plane for your dataflows based on the same [principles](https://medium.com/the-prefect-blog/your-code-will-fail-but-thats-ok-f0327a208dbe). 
- Employs the same [hybrid execution model](https://medium.com/the-prefect-blog/the-prefect-hybrid-model-1b70c7fd296), where Prefect doesn't store your flow code or data. 

## What changed

Prefect 2 requires modifications to your existing tasks, flows, and deployment patterns. We've organized this section into the following categories:


- **Simplified patterns** &mdash; abstractions from Prefect 1 that are no longer necessary in the dynamic, DAG-free Prefect Orion workflows that support running native Python code in your flows.
- **Conceptual and syntax changes** that often clarify names and simplify familiar abstractions such as retries and caching.
- **New features** enabled by the dynamic and flexible Prefect Orion API.

### Simplified patterns

Since Prefect 2 allows running native Python code within the flow function, some abstractions are no longer necessary:

- `Parameter` tasks: in Prefect 2, inputs to your flow function are automatically treated as [parameters](../concepts/flows/#parameters) of your flow. You can define the parameter values in your flow code when you create your `Deployment`, or when you schedule an ad-hoc flow run. One benefit of Prefect Orion’s parametrization is built-in type validation with [pydantic](https://pydantic-docs.helpmanual.io/).
- Task-level `state_handlers`: in Prefect 2, you can build custom logic that reacts to task-run states within your flow function without the need for `state_handlers`. [The page "
  How to take action on a state change of a task run"](https://discourse.prefect.io/t/how-to-take-action-on-a-state-change-of-a-task-run-task-level-state-handler/82) provides a further explanation and code examples.
- Instead of using `signals`, Prefect 2 allows you to raise an arbitrary exception in your task or flow and return a custom state. For more details and examples, see [How can I stop the task run based on a custom logic](https://discourse.prefect.io/t/how-can-i-end-the-task-run-based-on-a-custom-logic/83).
- Conditional tasks such as `case` are no longer required. Use Python native `if...else` statements to build a conditional logic. [The Discourse tag "conditional-logic"](https://discourse.prefect.io/tag/conditional-logic) provides more resources.
- Since you can use any context manager directly in your flow, a `resource_manager` is no longer necessary. As long as you point to your flow script in your `Deployment`, you can share database connections and any other resources between tasks in your flow. The Discourse page [How to clean up resources used in a flow](https://discourse.prefect.io/t/how-to-clean-up-resources-used-in-a-flow/84) provides a full example.

### Conceptual and syntax changes

The changes listed below require you to modify your workflow code. The following table shows how Prefect 1 concepts have been implemented in Prefect 2. The last column contains references to additional resources that provide more details and examples.

| Concept | Prefect 1 | Prefect 2 | Reference links |
| --- | --- | --- | --- |
| Flow definition. | `with Flow("flow_name") as flow:` | `@flow(name="flow_name")` | [How can I define a flow?](https://discourse.prefect.io/t/how-can-i-define-a-flow/28) |
| Flow executor that determines how to execute your task runs. | Executor such as `LocalExecutor`. | Task runner such as `ConcurrentTaskRunner`. | [What is the default TaskRunner (executor)?](https://discourse.prefect.io/t/what-is-the-default-taskrunner-executor/63) |
| Configuration that determines how and where to execute your flow runs. | Run configuration such as `flow.run_config = DockerRun()`. | Create an infrastructure block such as a [Docker Container](/tutorials/docker/) and specify it as the infrastructure when creating a deployment. | [How can I run my flow in a Docker container?](https://discourse.prefect.io/t/how-can-i-run-my-flow-in-a-docker-container/64) |
| Assignment of schedules and default parameter values. | Schedules are attached to the flow object and default parameter values are defined within the Parameter tasks. | Schedules and default parameters are assigned to a flow’s `Deployment`, rather than to a Flow object.  | [How can I attach a schedule to a flow?](https://discourse.prefect.io/t/how-can-i-attach-a-schedule-to-a-flow/65)  |
| Retries | `@task(max_retries=2, retry_delay=timedelta(seconds=5))` | `@task(retries=2, retry_delay_seconds=5)`  | [How can I specify the retry behavior for a specific task?](https://discourse.prefect.io/t/how-can-i-specify-the-retry-behavior-for-a-specific-task/60) |
| Logger syntax. | Logger is retrieved from `prefect.context` and can only be used within tasks. | In Prefect 2, you can log not only from tasks, but also within flows. To get the logger object, use: `prefect.get_run_logger()`. | [How can I add logs to my flow?](https://discourse.prefect.io/t/how-can-i-add-logs-to-my-flow/86)   |
| The syntax and contents of Prefect context. | Context is a thread-safe way of accessing variables related to the flow run and task run. The syntax to retrieve it: `prefect.context`. | Context is still available, but its content is much richer, allowing you to retrieve even more information about your flow runs and task runs. The syntax to retrieve it: `prefect.context.get_run_context()`. | [How to access Prefect context values?](https://discourse.prefect.io/t/how-to-access-prefect-context-values/62) |
| Task library. | Included in the [main Prefect Core repository](https://docs.prefect.io/core/task_library/overview.html). | Separated into [individual repositories](../collections/catalog/) per system, cloud provider, or technology. | [How to migrate Prefect 1 tasks to Prefect 2 collections](https://discourse.prefect.io/t/how-to-migrate-prefect-1-0-task-library-tasks-to-a-prefect-collection-repository-in-prefect-2-0/792). |

### What changed in dataflow orchestration?

Let’s look at the differences in how Prefect 2 transitions your flow and task runs between various execution states.

- In Prefect 2, the final state of a flow run that finished without errors is `Completed`, while in Prefect 1, this flow run has a `Success` state. You can find more about that topic [here](https://discourse.prefect.io/t/what-is-the-final-state-of-a-successful-flow-run/59).
- The decision about whether a flow run should be considered successful or not is no longer based on special reference tasks. Instead, your flow’s return value determines the final state of a flow run. This [link](https://discourse.prefect.io/t/how-can-i-control-the-final-state-of-a-flow-run/56) provides a more detailed explanation with code examples.
- In Prefect 1, concurrency limits were only available to Prefect Cloud users. Prefect 2 provides customizable concurrency limits with the open-source Prefect Orion server and Prefect Cloud. In Prefect 2, flow run [concurrency limits](https://docs.prefect.io/concepts/work-queues/#work-queue-concurrency) are set on work queues.


### What changed in flow deployment patterns?

To deploy your Prefect 1 flows, you have to send flow metadata to the backend in a step called registration. Prefect 2 no longer requires flow pre-registration. Instead, you create a [Deployment](/concepts/deployments/) that specifies the entry point to your flow code and optionally specifies:

- Where to run your flow (your *Infrastructure*, such as a `DockerContainer`, `KubernetesJob`, or `ECSTask`).
- When to run your flow (an `Interval`, `Cron`, or `RRule` schedule).
- How to run your flow (execution details such as `parameters`, flow deployment `name`, and [more](https://discourse.prefect.io/tag/deployment)).
- The work queue for your deployment. If no work queue is specified, a default work queue named `default` is used.

The API is now implemented as a REST API rather than GraphQL. [This page](https://discourse.prefect.io/t/how-can-i-interact-with-the-backend-api-using-a-python-client/80) illustrates how you can interact with the API.

In Prefect 1, the logical grouping of flows was based on [projects](https://docs.prefect.io/orchestration/concepts/projects.html). Prefect 2 provides a much more flexible way of organizing your flows, tasks, and deployments through customizable filters and tags. [This page](https://discourse.prefect.io/t/how-can-i-organize-my-flows-based-on-my-business-logic-or-team-structure/66) provides more details on how to assign tags to various Prefect 2 objects.

The role of agents has changed:

- In Prefect 2, there is only one generic agent type. The agent polls a work queue looking for flow runs.
- See [this Discourse page](https://discourse.prefect.io/t/whats-the-role-of-agents-and-work-queues-and-how-the-concept-of-agents-differ-between-prefect-1-0-and-2-0/689) for a more detailed discussion.

## New features introduced in Prefect 2

The following new components and capabilities are enabled by Prefect 2.

- More flexibility thanks to the elimination of flow pre-registration.
- More flexibility for flow deployments, including easier promotion of a flow through development, staging, and production environments.
- Native `async` support.
- Out-of-the-box `pydantic` validation.
- [Blocks](../ui/blocks/) allowing you to securely store UI-editable, type-checked configuration to external systems and an easy-to-use Key-Value Store. All those components are configurable in one place and provided as part of the open-source Prefect 2 product. In contrast, the concept of [Secrets](https://docs.prefect.io/orchestration/concepts/secrets.html) in Prefect 1 was much more narrow and only available in Prefect Cloud.  
- [Notifications](../ui/notifications/) available in the open-source Prefect 2 version, as opposed to Cloud-only [Automations](https://docs.prefect.io/orchestration/ui/automations.html) in Prefect 1.  
- A first-class `subflows` concept: Prefect 1 only allowed the [flow-of-flows orchestrator pattern](https://discourse.prefect.io/tag/orchestrator-pattern). With Prefect 2 subflows, you gain a natural and intuitive way of organizing your flows into modular sub-components. For more details, see [the following list of resources about subflows](https://discourse.prefect.io/tag/subflows).


### Orchestration behind the API

Apart from new features, Prefect 2 simplifies many usage patterns and provides a much more seamless onboarding experience.

Every time you run a flow, whether it is tracked by the API server or ad-hoc through a Python script, it is on the same UI page for easier debugging and observability. 

### Code as workflows

With Prefect 2, your functions *are* your flows and tasks. Prefect 2 automatically detects your flows and tasks without the need to define a rigid DAG structure. While use of tasks is encouraged to provide you the maximum visibility into your workflows, they are no longer required. You can add a single `@flow` decorator to your main function to transform any Python script into a Prefect workflow.

### Incremental adoption
The built-in SQLite database automatically tracks all your locally executed flow runs. As soon as you start Prefect Orion and open the Prefect UI in your browser (or [authenticate your CLI with your Prefect Cloud workspace](../ui/cloud-getting-started/)), you can see all your locally executed flow runs in the UI. You don't even need to start an agent.

Then, when you want to move toward scheduled, repeatable workflows, you can build a deployment and send it to the server by running a CLI command or a Python script. 

- You can create a deployment to on remote infrastructure, where the run environment is defined by a reusable infrastructure block.

### Fewer ambiguities

Prefect 2 eliminates ambiguities in many ways. For example. there is no more confusion between Prefect Core and Prefect Server &mdash; Prefect 2 unifies those into a single open source product. This product is also much easier to deploy with no requirement for Docker or docker-compose.

If you want to switch your backend to use Prefect Cloud for an easier production-level managed experience, Prefect profiles let you quickly connect to your workspace.


In Prefect 1, there are several confusing ways you could implement `caching`. Prefect 2 resolves those ambiguities by providing a single `cache_key_fn` function paired with `cache_expiration`, allowing you to define arbitrary caching mechanisms &mdash; no more confusion about whether you need to use `cache_for`, `cache_validator`, or file-based caching using `targets`.

 For more details on how to configure caching, check out the following resources:
 
- [Caching docs](/concepts/tasks/#caching)
- [Time-based caching](https://discourse.prefect.io/t/how-can-i-cache-a-task-result-for-two-hours-to-prevent-re-computation/67)
- [Input-based caching](https://discourse.prefect.io/t/how-can-i-cache-a-task-result-based-on-task-input-arguments/68)

A similarly confusing concept in Prefect 1 was distinguishing between the functional and imperative APIs. This distinction caused ambiguities with respect to how to define state dependencies between tasks. Prefect 1 users were often unsure whether they should use the functional `upstream_tasks` keyword argument or the imperative methods such as `task.set_upstream()`, `task.set_downstream()`, or `flow.set_dependencies()`. In Prefect 2, there is only the functional API. 


## Next steps

We know migrations can be tough. We encourage you to take it step-by-step and experiment with the new features.

To make the migration process easier for you:

- We provided [a detailed FAQ section](https://discourse.prefect.io/tag/migration-guide) allowing you to find the right information you need to move your workflows to Prefect 2. If you still have some open questions, feel free to create a new topic describing your migration issue.
- We have dedicated resources in the Customer Success team to help you along your migration journey. Reach out to [cs@prefect.io](mailto:cs@prefect.io) to discuss how we can help.  
- You can ask questions in our 20,000+ member [Community Slack](https://prefect.io/slack).


---
Happy Engineering!
