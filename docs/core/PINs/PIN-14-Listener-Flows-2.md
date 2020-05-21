---
title: 'PIN-14: Event-Driven Flows pt 2'
sidebarDepth: 0
---

# PIN 14: Event-Driven Flow Execution via Listeners

Date: December 14, 2019

Author: Chris White

## Status

**Paused**; supersedes [PIN 8](PIN-08-Listener-Flows.html).

## Context

Many use cases require event-driven Flows; for example, we might want to run an ETL-style Flow to process individual files each time one lands in an S3 bucket.  Historically, we have recommended users sign up for a Scheduler account and use Prefect Cloud's API to trigger parametrized runs (e.g., [using AWS Lambda](https://medium.com/the-prefect-blog/event-driven-workflows-with-aws-lambda-2ef9d8cc8f1a)).  This suffers from a few drawbacks:
- it doesn't allow users to explicitly specify that this Flow depends on an external event
- it doesn't allow users to configure that event as a first-class hook within Prefect
- it requires the Flow be run through Prefect Cloud

This PIN outlines a first-class implementation of event-driven workflows that will allow users to configure an `EventClock` that listens for events of a specified type, and passes a JSON representation of each event as a Parmeter to the Flow.  This will allow for:
- a maintained library of event-driven hooks
- the ability to configure event-driven flows which also run on a schedule
- an implementation that allows both Core and Cloud users to run event-driven Flows
- the ability to toggle whether a Flow is "listening" through Prefect instead of an external service

## Proposal

The heart of the current proposal is to introduce a new `EventClock` (see [PIN 10](PIN-10-Schedules.html) for a description of the clock model) which polls to find events matching its specification.  The proposal is similar in spirit to [PIN 8](PIN-08-Listener-Flows), with a somewhat simpler implementation now that Clocks have been implemented.  In addition to a new type of Clock, this proposal outlines a new `listen()` method on `FlowRunner` classes, which will become responsible for waiting for either a scheduled time or an event to take place, and will ultimately replace a large piece of the scheduling logic within `flow.run()`.

### Core

In Core, we introduce two new APIs:
- an `EventClock` which has an unimplemented `next` method, responsible for polling for events and collecting them in a work queue
- an `EventParameter` (or a new keyword argument to `Parameter`s) that allows users to designate a Parameter as the JSON event payload, with a default value of either `None` or `dict()`

Subclasses of this `EventClock` can then be used to construct an appropriate `Schedule` for the Flow (possibly with other time-driven clocks!), and `flow.run` will essentially work with minimal change.  The only additional piece of information that needs to be conveyed is the value for the designated event parameter, and this can be achieved through one additional call (maybe `flow.retrieve_event()` which then extracts the event from the `EventClock`) and then placing the result into Prefect context.

In addition, a new `listen` method on `FlowRunner` classes will be responsible for calling the schedule and configuring context for each run.  Much of the current scheduling logic in `flow.run()` should be replaceable by this new method on the `FlowRunner` class.

### Cloud

There are a few proposed changes that will also require changes to Prefect Cloud:

- any subclass of the `EventClock` will be deserialized as the base `EventClock` class, which returns an empty list for `next`
- users will be responsible for starting and stopping the listening by creating / cancelling a given Flow run
- once created, an appropriate agent will pick up the flow run and submit it for "execution" (in this case, submit it to listen); we might need to introduce a new pre-listening state so that the Agent knows this is a listener and not a normal flow run
- During this execution, the Flow run will enter a `Listening` state and `CloudFlowRunner.listen()` will be used to poll for events; anytime an event is found, it will be used to call the Cloud API and create a new parametrized flow run with the appropriate event parameter payload
- while polling, or through a standard heartbeat thread, if a Flow run is found to be in a `Listening` state but hasn't sent a heartbeat, the Lazarus process will revive it
- to prevent duplicate processing runs, we will also need to use some form of "event ID" as the idempotency key for the run

## Consequences

First and foremost, this will allow us to create and maintain a curated list of event-based hooks for Prefect Flows.  Additionally, if we enforce a "null"-like default vaule for event parameters, scheduled batch and cleanup jobs can still occur while the flow is listening for events.  Moreover, both Core and Cloud users will be able to benefit from the functionality as proposed above.

