---
sidebarDepth: 0
---

# Why Prefect?

## Negative engineering

Every piece of code has some purpose or objective that it seeks to achieve. We call that **positive engineering**.

However, in order to execute code in an automated way, we need to answer an enormous number of questions:

- when should it run?
- where should it run?
- what dependencies does it require?
- what inputs does it require?
- can it be paused and resumed seamlessly?
- what logs does it produce?
- what outputs does it produce?
- where are outputs stored?
- what happens if it succeeds?
- what happens if it fails?
- what happens if it encounters an error?
- what happens if the computer it runs on crashes?
- under what circumstances should notifications be sent?
- can it be retried?
- when should it retry?
- can it be skipped?
- ...

Each question, taken individually, might be trivial, but complexity starts to emerge when we combine them. If we contemplate thousands of concurrent tasks running in distributed, possibly disjoint environments, the entire system breaks down.

We call this complexity **negative engineering**. It encompasses everything that needs to be done to ensure that positive engineering can run robustly. Focusing on negative engineering is critical because it ensures that code runs as intended. However, most engineers don't like building negative infrastructure because it's often orthagonal to the postive code they set out to write in the first place.

**Prefect is an automation framework for negative engineering.** Prefect's job is to make sure that no matter what your code is, or what environment it's deployed to, it gets executed in a controlled manner that satisfies all of these negative engineering requirements.


## "This should be easy"

Each aspect of negative engineering seems simple. How hard could it be to trap an error, store logs, retry, or create an execution endpoint? Unsurprisingly, the most common thing we hear from users is: "This should be easy."

And they're right: it should be.

But negative engineering requirements compound. The more things the positive code does, the more complex the negative engineering challenge becomes.

The trend among workflow systems is to tackle this complexity by exposing it to the user. This has led to a proliferation of configuration files and obscure data structures that "only an engineer could love."

Unlike other tools, Prefect doesn't require you to know (or care) about every single automation detail. Prefect has a common-sense default for everything, informed by extensive user research. If you just want to run a function at 8am every day, then that's the only bit of information you need to provide. Prefect will handle everything else. On the other hand, if you ARE the type of person who loves to introspect a complex DAG data structure, it's got you covered. Prefect is the most complete automation framework available.


## Automation framework

A proper automation framework has three critical components:

- Workflow definition
- Workflow engine
- Workflow state


### Workflow Definition

Defining the workflow is, in many ways, the easiest part. This is the opportunity to describe all of the negative engineering: how tasks depend on each other, under what circumstances they run, and any infrastructure requirements.

Many workflow systems expect workflows to be defined in config files or verbose data structures. Across all of the user research we performed while designing Prefect, not once did anyone say they wanted more explicit workflow definitions. Not once did we hear a request for more YAML configs. Not once did anyone volunteer to rewrite their code to comply with a workflow system's API.

Therefore, Prefect views these approaches as design failures. While Prefect builds a fully introspectable and customizable DAG definition for every workflow, users are never required to interact with it if they don't want to. Instead, _Python is the API_. Users define functions and call them as they would in any script, and Prefect does the work to figure out the workflow structure.

### Workflow Engine

Once the workflow is defined, we need to execute it. This is the heart of negative engineering.

Prefect's engine is a robust pipeline that embeds the logic for workflow execution. It is essentially a system of rules for deciding if a task should run; what happens while it's running; and what to do when it stops.

It's not enough to merely "kick off" each task in sequence; a task may stop running because it succeeded, failed, skipped, paused, or even crashed! Each of these outcomes might require a different response, either from the engine itself or from subsequent tasks. The role of the engine is to introspect the workflow definition and guarantee that every task follows the rules it was assigned.

### Workflow State

Arguably, Prefect's chief innovation isn't a streamlined workflow definition system or robust workflow engine. It's a rich notion of workflow state.

Most workflow systems have an "implicit success" criteria. This means that if a task stops without crashing, it is considered "succesful"; otherwise, it "fails". This is an incredibly limiting view of the world. What if you wanted to skip a task? What if you wanted to pause it? If the entire system fails, can you restore it just as it was? Can you guarantee that a task will only run once, even if multiple systems in disjoint environments are attempting to run it?

By embuing every task and workflow with a strong notion of "state", Prefect enables a rich vocabulary to describe a workflow at any moment before, during, or after its execution.
