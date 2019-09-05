---
title: 'PIN-3: Environment Execution'
sidebarDepth: 0
---

# PIN-3: Agent-Environment Model for Flow Execution

Date: 2019-01-29

Author: Josh Meek

## Status

Accepted

## Context

**Environments**:
Environments in the Prefect core library are serializable objects that describe how to run a flow. They serve as a way of describing how a specific flow should be stored, shared, and executed.

**Agents**:
The current status of open source Prefect _agents_ revolves around small running processes that retrieve flow runs and then determine how to execute them based on the environment metadata information found in the flow itself.

---

Currently the main supporting agent of the execution model is a small go application that runs as a minimal agent on the user's cluster of choice. Right now it only supports Kubernetes and is dubbed the k8s-agent. The agent is responsible for the following process:

1. Grab any flow runs that are ready to be executed
2. Spin up infrastructure to support those flow runs
3. Run the flow
4. Exit once flow's infrastructure has entered a finished state
5. Tear down infrastructure that supported the flow run

This mode of execution is stable and works however it is not very flexible. It introduces challenges and frictions at the environment level. For example if we have a flow that executes using a Dask cluster and the agent is set to spin up infrastructure related to using Dask, then it is incompatible whenever a user submits a flow with an environment that is set to run on some other platform of execution. This would require the agent to be able to handle every possible environment that exists in the Prefect library, which could lead to various problems such as:

1. Agent will no longer become a tiny running process
2. Agent will require a change every time a new type of environment is created
3. Agent will refuse to run when it encounters an environment it was not partitioned for

## Proposal

Prefect will adopt a more agnostic and robust agent-environment model for execution by trimming down the agent to only handle minor resource control, moving execution and environment related logic into the environments themselves, and relying on a base prefect Docker image to run the environments.

There will be three main components of this execution model:

- Prefect Docker image
- Platform agent
- Environment metadata

**Prefect Docker image**:
The Prefect docker image will be a small Python image with Prefect installed. Upon run time the image will take in arguments such as the flow run id, runner auth token, and the serialized environment. Will only ever act as an intermediary container for running environments.

**Platform agent**:
The platform agent will be a tiny deployment process that will look for flow runs to be executed and will act as a sort of simple [TTL controller](https://kubernetes.io/docs/concepts/workloads/controllers/ttlafterfinished/) for processes.

**Environment metadata**:
The environment metadata contains information about the environment itself that was present on the flow which acts as a serializable set of instructions on how to recreate the environment.

---

### Process Details

_Note: the context of this proposal is an agent that runs on Kubernetes and anytime it refers to states it is referring to Kubernetes states, not Prefect states._

Environments will now be responsible for creating their own infrastructure dependencies and running their flows. They will take on a more generalized format for execution and will need to inherit `setup` and `execute` functions. When an environment's `run` function is called from the Prefect container it will first run that environment's `setup` function that is responsible for handling the creation of all infrastructure dependencies. Then it will call the `execute` function that is actually where the flow is run against the environment's infrastructure requirements. Now you may be thinking, where is the `post_execute` function? Environments will not be responsible for any post processing that may occur for that environment. This is due to the fact that an environment is never guaranteed to reach the post-processing step inside the environment itself and in an effort to make this as clean and robust as possible, nothing will be responsible for long running connections between components of an execution (i.e. the Prefect image will not _wait_ for the `execute` function to finish and then run a `post_execute` function). The post processing step (resource management in the form of cleanup/tear down/deletion) of any infrastructure created during the `setup` function will be handled by the agent.

The agent, while looking for new flow runs that need to be executed, will also work as a TTL controller that is responsible for removing finished [jobs](https://kubernetes.io/docs/concepts/workloads/controllers/jobs-run-to-completion/) on the cluster. There are two definite times when jobs will be used: creating the Prefect container that runs the environment and the running of the flow itself. It will be a hard requirement at an agent-environment level in this Kubernetes scenario that any time a flow is run it will be as a job and **not** a long-running `exec` call because that can lead to unexpected resource limit issues. The running of a flow will always occur separate from any infrastructure that was created during the `setup`. Since the Prefect container will be a job then it will enter a finished state after it calls the environment's `execute` function. It will then be cleaned up by the agent because it is a job in the finished state. The `execute` function will _at the least_ create a Kubernetes job that runs the flow in a container of choice. As an example a _LocalOnKubernetesEnvironment_ will be responsible for a process that creates a job that runs the flow in a Prefect container (or depending on how it is implemented, could just run in the base Prefect container that runs the environment) or a _DaskOnKubernetesEnvironment_ will create a job that runs the flow on a `setup` created Dask cluster. Once that job enters a finished state, that job and all resources associated with that run will be safely deleted from the cluster. Resource management will be partitioned based on labels in the spec.

The method of looking for completed jobs adds two main benefits:

1. No need for a zombie killer between agent deployments because they always just look for finished jobs. So a flow run that was executed from one agent can be handled by the next one.
2. It does not matter what happens inside the flow because the job will still reach a completed state once the flow is no longer running.

The labels will play a crucial role in the agent handling which resources to delete. Upon finding a new flow run the agent will generate a UUID and that will be attached to both the Prefect container and any resources created by the environment's `setup` function. The Prefect container will also be labeled with something signifying that it is separate from any other resources which will allow it to be deleted upon job completion without having any interference on the other resources created for that particular run. Now the Prefect container can be deleted and the job that is responsible for running the flow can continue on without leaving behind any unused resources. After completion of that job the agent will see that another job had entered a finished state, look at the labels, see that it isn't the original Prefect container which created it, and delete any resources tagged with that particular deployment's UUID.

## Consequences

The agent is still platform specific. For example, our k8s-agent is still responsible for running Kubernetes related environments. Users aren't able to use environments for a platform different than theirs is set up to run on because it will be incompatible. Going forward, Kubernetes will be our primarily supported agent platform unless noted otherwise.

Environments will not become more hyper-specific and detailed. As seen above there were examples such as _LocalOnKubernetesEnvironment_ and _DaskOnKubernetesEnvironment_. This is due to what the `setup` step will be responsible for with infrastructure/resource dependencies as those will be specific to that environment.

Any currently created flows will need to be redeployed if the agent that executes them is changed to use this newer format. They will be incompatible otherwise.

## Actions

This PIN was largely superseded by [PIN 7](PIN-07-Storage-Execution.md).
