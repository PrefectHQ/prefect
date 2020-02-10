---
sidebarDepth: 0
---

# Why Prefect?

## Details matter

Prefect is a workflow engine, which means that users need absolute confidence that 1) it works and 2) it works well. For that reason, Prefect's design is backed by a strong philosophy of data engineering and we hold its code to a high standard.

Prefect already has more unit tests and greater test coverage than any other workflow engine, including the entire Airflow platform. Documentation is paramount: every module, class, and function not only has a docstring, the docstrings themselves are tested for consistency. Type annotations are used to catch errors. We've even user-tested the names of variables and functions to make sure they're clear. Users can trust that this standard of care extends even to parts of the codebase they might never look at themselves.

## Tasks are functions

In a simple sense, Prefect tasks are functions that have special rules about when they should run: they optionally take inputs, perform some work, and optionally return an output. Tasks can process data directly, or orchestrate external systems, or call out to other environments or even languages -- there are almost no restrictions on what a task can do. Furthermore, each task receives metadata about its upstream dependencies before it runs, even if it doesn't receive any explicit data inputs, giving it an opportunity to change its behavior depending on the state of the flow.

Because Prefect is a negative engineering framework, it is agnostic to the code each task runs. There are no restrictions on what inputs and outputs can be.

## Workflows are containers

Workflows (or "flows") are containers for tasks. Flows represent the dependency structure between tasks, but do not perform any logic.

## Modularity

Every component of Prefect has a modular design, making it easy to customize or replace anything from the execution engine, to logging, to data serialization and storage, to state handling itself. As a negative engineering tool, Prefect was designed to _support_ positive engineering, not replace it.

## Communication via state

Prefect uses a formal concept of `State` to reflect the behavior of the workflow at any time. Both tasks and workflows produce `States`.

## Massive concurrency

Prefect workflows are designed to be run at any time, for any reason, with any concurrency. Running a workflow on a schedule is a special case.

## Idempotency preferred (but not required)

We refer to idempotency as the "get out of jail free card" of workflow management systems. When tasks are idempotent, the engineering challenges become dramatically easier. However, building idempotent tasks is extremely difficult, so we designed Prefect without any assumptions of idempotency. Users should prefer idempotent tasks because they are naturally robust, but Prefect does not require them.

## Automation framework

A proper automation framework has three critical components:

- Workflow definition
- Workflow engine
- Workflow state

Prefect Core includes all three, and the design of each piece was heavily informed by user research and applied knowledge.

### Workflow Definition

Defining the workflow is, in many ways, the easiest part. This is the opportunity to describe all of the negative engineering: how tasks depend on each other, under what circumstances they should run, and any infrastructure requirements.

Many workflow systems expect workflows to be defined in config files or verbose data structures. Across all of the user research we performed while designing Prefect, not once did anyone say they wanted more explicit workflow definitions. Not once did we hear a request for more YAML configs. Not once did anyone volunteer to rewrite their code to comply with a workflow system's API.

Therefore, Prefect views these approaches to workflow definition as design failures. While Prefect builds a fully introspectable and customizable DAG definition for every workflow, users are never required to interact with it if they don't want to. Instead, _Python is the API_. Users define functions and call them as they would in any script, and Prefect does the work to figure out the workflow structure.

### Workflow Engine

Once the workflow is defined, we need to execute it. This is the heart of negative engineering.

Prefect's engine is a robust pipeline that embeds the logic for workflow execution. It is essentially a system of rules for deciding if a task should run; what happens while it's running; and what to do when it stops.

It's not enough to merely "kick off" each task in sequence; a task may stop running because it succeeded, failed, skipped, paused, or even crashed! Each of these outcomes might require a different response, either from the engine itself or from subsequent tasks. The role of the engine is to introspect the workflow definition and guarantee that every task follows the rules it was assigned.

### Workflow State

Arguably, Prefect's chief innovation isn't a streamlined workflow definition system or robust workflow engine. It's a rich notion of workflow state.

Most workflow systems have an "implicit success" criteria. This means that if a task stops without crashing, it is considered "successful"; otherwise, it "fails". This is an incredibly limiting view of the world. What if you wanted to skip a task? What if you wanted to pause it? If the entire system fails, can you restore it just as it was? Can you guarantee that a task will only run once, even if multiple systems in disjoint environments are attempting to run it?

By imbuing every task and workflow with a strong notion of "state", Prefect enables a rich vocabulary to describe a workflow at any moment before, during, or after its execution.
