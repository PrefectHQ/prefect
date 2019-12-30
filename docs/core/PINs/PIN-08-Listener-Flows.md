---
title: 'PIN-8: Event-Driven Flows'
sidebarDepth: 0
---

# PIN 8: Event-Driven/Long-Running Flow Execution via Listeners

Date: March 31, 2019

Author: Jeremiah Lowin

## Status

Superseded by [PIN 14](PIN-14-Listener-Flows-2.html).

## Context

### tldr

This PIN describes the minimal changes Prefect would require to provide first-class support for launching workflows in response to arbitrary event streams. Happily, as a provider of workflow semantics, this is much easier than it sounds. Instead of focusing on looping tasks, we focus on looping flows. This allows us to address the major challenges (long-running infrastructure and keeping trigger logic inside the workflow system) while keeping Prefect's existing guarantees for event-driven flows (such as per-event checkpointing and retries).

### Current approach to launching flows

Prefect exposes a set of broadly synchronous, batch-workflow mechanisms: tasks form a DAG and are executed in some topological order. This has a few important implications, namely:

1. upstream tasks must be "finished" before downstream tasks start
1. once an upstream task is "finished", it is not run again

"Finished," in this context, means that the task completed at least one attempt to run, whether successful or failed (or a number of other conditions). Prefect has a formal `Finished` state that, among other things, is used to enforce the previous two rules.

However, Prefect makes very few claims about how flow runs should be kicked off. There is nothing preventing massively concurrent executions, even of the same flow run, and indeed Prefect was designed to expect that circumstance. Therefore, an initial design goal was that Prefect would handle event-driven workflows by simply launching a new flow run in response to each event. Prefect codifies two "first-class" events for starting flows: time (via `Schedules`) and ad-hoc webhooks (via APIs such as Prefect Cloud). This would appear to cover the broad set of circumstances identified through user research, as any event can be transformed into a standard webhook call.

However, this approach has led to suboptimal user experience for two major reasons.

1. It requires users to put workflow logic (or something that feels an awful lot like workflow logic) outside the workflow management system. This breaks a cardinal rule of Prefect's philosophy, and is generally unpleasant. In addition, that external infrastructure must be provisioned with auth tokens and flow ids, leading to unexpected maintenance.
1. It implicitly assumes that each flow run can be transparently launched and spun down with time and resources proportional to its execution. This is often not the case, as there's desire for long-running processes that can make efficient use of long-running infrastructure.

### Requirements for streaming flows

This UX manifests when dealing with "event-driven" or "streaming" workflows.

These types of workflows have been on our roadmap from day one. Most conversations have assumed we would introduce some sort of looping task that would remain in a running state, emitting events. However, this would present significant challenges to Prefect's mode of operation. Specifically, the rule that tasks do not run until upstream tasks finish _must_ be violated in order to run downstream tasks while the "emitter" is still running. Similarly, the rule that tasks only run once must be violated, because the downstream task must be re-run for each event. Other approaches involve sharing some sort of "stream" or "pipe" between tasks, but this requires _either_ all tasks to be running in the same process _or_ an external piece of infrastructure, like a message broker. Either way, it violates Prefect's assumption that tasks can be run at any time, in any location, with any concurrency.

A quick litmus test for the viability of these approaches is to ask "what does a retry look like?" In both of these approaches, it's unclear how one would retry a specific event, because the "finished" semantic isn't well defined.

In that vein, it's important to note that Prefect is not a stream processor. It's a system for describing workflow semantics traditionally found in batch processes. Therefore, our discrete design challenge is not to process a stream, but rather to launch our workflow semantics in response to a stream of events. This amounts to designing a more flexible flow trigger system.

### Examples of streaming flow triggers

- processing a file when it lands in S3
- detecting schema changes in a database
- detecting new data
- pulling work from a Redis queue
- light trigger logic involving state (X times per hour, X unique events)
- processing messages from Kafka
- running a model with dedicated hardware (such as a GPU)
- running a model with dedicated infrastructure (such as a cluster)

## Proposal

### New Requirements

- A new `FlowRunner` subclass called `ListenerFlowRunner`
- An `Event` class that has an arbitrary JSON-esque `value` and an optional `ack()` method for acknowledging the event
- A `Listener` class whose `listen()` method is a generator that emits `Events`. It is attached to the `ListenerFlowRunner` as the `listener` attribute
- The `ListenerFlowRunner` designates one of the flow's `Parameters` as the `event_parameter`. When an event is emitted by the `listener`, the flow will be executed with the event passed to that `event_parameter`.
- A new `Listening` state that subclasses `Running`
- A new schedule called `AlwaysRunning` that attempts to immediately restart a flow if it stops

### Process

This process bears some resemblance to Prefect's `mapping` semantic, where users define a process for handling a single item and Prefect automatically applies it to a list. Here, users build flows for processing a single event, and the `ListenerFlowRunner` automatically applies it to a stream.

When `ListenerFlowRunner.run()` is called, the runner enters a `Listening` state rather than a `Running` state. It then begins looping over its `Listener.listen()` method, which is a generator of `Events`. Each `Event` has an `Event.value` attribute containing the actual value of the event (whatever that might be, including nothing) and an `Event.ack()` method allowing the event to be acknowledged, if appropriate. By default, this method does nothing.

Each event is passed into a separate call of the `FlowRunner.run()` superclass method as the appropriately defined parameter value. Each of these "runs" represents a completely distinct processing of an event, and is therefore independently retry-able. The runner no longer defines success or failure from its tasks, but rather from whether it encounters an error in the listener.

The superclass `run()` can be called in the FlowRunner's executor, allowing asynchronous execution.

Each event therefore triggers a completely new flow run, but from a long-running process that replaces some of the latency of spinning up new architecture.

Here is pseudocode for the process:

```Python
# inside ListenerFlowRunner
def run(self, *args, parameters, context, **kwargs):

    try:
        # set state LISTENING
        for event in self.listener.listen():

            # add the event to parameters
            run_params = parameters.copy()
            run_params.update({self.event_parameter.name: event.value})

            # --
            # if running in Cloud, generate a new Submitted flow run at
            # this time and pass the information to self.run
            # self.client.create_flow_run(parameters=run_params)
            # context.update(...)
            # --

            # acknowledge the event
            event.ack()

            # run the flow in the executor
            executor.submit(super().run, *args, parameters, context=context, **kwargs))

    except StopIteration:
        return Success("listener exhausted successfully.")
    except Exception as exc:
        return Failed("failure in listener execution: {}".format(exc))
```

The listener itself could emit any sort of event: popping a message from Kafka, notifying that a file landed in storage or was modified, even clock-based events.

A new `AlwaysRunning` schedule would indicate that this flow is intended to be restarted if it ever fails. Some work may be required to apply this logic only to the "parent", not the "children".

### Benefits

This approach extends Prefect to support long-running, event-driven processes. Importantly, it does so by hardly modifying any of Prefect's core mechanisms, essentially just implementing a Listener loop over the flow runner. The critical difference between this approach and the prior approach of kicking off flow runs on an ad hoc basis is that this approach doesn't require any new infrastructure requirements; the same process, container, cluster, etc. can be reused for each event's run.

Because each event generates a new flow run with the event as a parameter, Prefect Cloud acts as a robust event-storage layer. This means that if processing for a single event fails, it can be trivially retried as a standalone flow run using existing tooling.

## Consequences

Prefect will support streaming / event-driven / long-running flows for which constant-running infrastructure is a key requirement. Each event will generate a new flow run, resulting in a retry-able, introspectable record of the event's processing. The long-running flow itself will have a "parent" flow run that is (assuming all goes well) in a `Listening` state.

## Actions
