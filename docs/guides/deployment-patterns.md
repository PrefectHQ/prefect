---
description: Answers to frequently asked questions about Prefect.
tags:
    - FAQ
    - frequently asked questions
    - questions
    - license
    - databases
---





### Patterns in Prefect
There are four common dataflow design patterns in Prefect. Each pattern offers different degrees and types of separation from related flows.

 - Conceptual separation is when a flow can be thought of as separate from another flow, even if it’s part of the same process.

 - Execution separation is when a flow can be executed separately from another flow.

 - Awareness separation is when a flow doesn’t have any direct reference to another flow, even if it’s related.



### Monoflow
A monoflow is a single flow made up of series of tasks with data passed from one to the next. Within the flow, tasks are tightly coupled to each other through dependencies. It is the most common way to use Prefect. It’s the pattern that most people think of when they think of workflow orchestrators.

This pattern is most useful for most common, straightforward flows. There’s only two levels of abstraction to think about—the flow itself and the tasks within it. It’s an easy pattern to set up, maintain, and use, especially if the flow is fully owned and maintained by a single person or team. However, this pattern can get unwieldy when there are multiple code owners, many tasks, or tasks with different infrastructure needs within the same flow.


### Flow of subflows 
Prefect’s orchestration engine is the first to offer first-class subflows. Any flow written with Prefect can be used as a component in another flow. A subflow has the same relationship to its parent flow as a task does. It runs in the same process as its parent flow. You can use subflows much as you would use an imported module in a python script.

This pattern is most useful when you only want conceptual separation. It increases conceptual overhead in the form of additional layers of abstraction: the parent flow, its task and subflow runs, and the subflow runs’ tasks. In exchange, this pattern compartmentalizes the components of the parent process. For an individual, this can be useful for decomposing large flows into more easily reasoned logical units. For teams, it facilitates clear ownership boundaries and facilitates code-reuse.

### Flow of deployments 
Prefect flows can also start a run of another flow through a deployment—a specification that associates a flow with a particular infrastructure. In this case, the deployed flow isn’t so much “part of” the initial flow, as it is “called by” that flow. Once a flow has called another flow, it can wait for it to complete, or it can simply start the deployed flow and proceed with the rest of its tasks. A deployed flow can run on separate infrastructure from the initial flow. Our community calls this the orchestrator pattern. Prefect users can think of and use deployed flows much like an external web service.

This pattern is most useful when you want both conceptual and execution separation. The conceptual complexity is about the same as using a subflow, but the execution complexity is greater, because there’s separate infrastructure and processes to think about. Still, the complexity can be worth it, particularly when certain tasks need a certain type of infrastructure, like GPUs.

### Event Triggered Flow 
With Prefect’s recent automations release, a new pattern is now possible. Whenever a flow run changes state, as it does when it starts or completes running, it emits an event signaling the change to the rest of the system. With automations, Prefect can trigger flows based on a specific flow run state change, or lack thereof. Just as with a submitted flow, a triggered flow can run on separate infrastructure from the initial flow.

This pattern is most useful when you want conceptual, execution, and awareness separation. In this pattern, the triggered flow doesn’t need to know anything about the initial flow. The event that triggers it could come from anywhere. It could even be one of several events that the trigger is listening for. We expect that users will adopt this pattern for the similar reasons that any organization might adopt an event-driven architecture. The loose coupling enables more distributed software and minimizes coordination costs.