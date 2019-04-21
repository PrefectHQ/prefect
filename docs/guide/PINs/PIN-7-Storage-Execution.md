---
sidebarDepth: 0
---

# PIN-7: Storage and Execution

Date: April 20, 2019

Author: Josh Meek & Chris White

## Status

Approved

## Context

Our current environment setup contains multiple classes, some of which can be deployed, others which can't. Moreover, the environment classes tightly couple storage of a flow with execution platform details. This leads to an unsatisfactory interface, and a spreading out of documentation. Additionally, it makes it hard to delineate which environments are appropriate for which use cases and also requires a large number of highly specific classes.

## Proposal

Separate out the storage component of an environment into its own module and attach it to the flow as an argument.

## Consequences

All environments will need a total rewrite, new storage classes will need to be introduced, agent interfaces will need to be updated and PIN-3 will be partially voided.
