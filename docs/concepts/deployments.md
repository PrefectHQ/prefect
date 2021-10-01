# Deployments

## Overview

A `Deployment` contains information about where to find flow code and instructions for how/when to execute it. Deployments are the bridge between running a flow interactively and handing it to the API for automatic or remote execution.

A deployment's `flow_location` specifies **where** to find the flow to execute. Flow locations can refer to file locations or to code stored within the Orion database. When a flow run associated with a deployment is run by an agent, f

A deployment's `schedule` specifies **when** to execute flow runs. Schedules are optional, and can be turned on or off at any time. More detailed information about schedules is available [here](/api-ref/schemas/schedules.md). 

A deployment's `parameters` specify **how** to execute flow runs. Parameters are passed to the `flow` function when the flow run is executed.

Deployments are linked to a flow. One flow can have multiple deployments, which do not necessarily need to execute the same code. For example, you can create three deployments of the same flow for dev/staging/prod and use flow code from their respective environments.



Stuff to include
- what is a deployment
- what can i do with a deployment
- how to do stuff with a deployment? just a few basic examples

## Creating A Deployment

DOCSTODO