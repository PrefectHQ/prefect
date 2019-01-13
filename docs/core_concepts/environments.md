# Environments

## Overview

Environments are serializable objects that describe how to run a flow. By using an appropriate `Environment`, users can store (and share) flows in a variety of storage and compute locations.

## Design

Environment objects have a simple lifecycle.

When they are instantiated, environments are given as much information as possible to describe how the flow will run.

Later, the environment is `built` for a specific flow. At this time, any flow-specific information can be stored.

After being built, an environment must be able to produce a JSON description of itself that can be reused to recreate it at any time.

Finally, environments have a `run()` method that runs their flow.

For a more detailed description, please see the [API docs](/api/environments.html)

## LocalEnvironment

The simplest environment is the `LocalEnvironment`, and it will be used by most other environment classes.

When a `LocalEnvironment` is built, it records a serialized version of the flow. Later, when it's time to run the `LocalEnvironment`, it deserializes the flow and executes it.

## ContainerEnvironment

The ContainerEnvironment runs flows in a Docker container. It is instantiated with a variety of information, including a base image, list of Python dependencies, and registry URL. When built, it creates and builds a Dockerfile that copies a `LocalEnvironment` into an appropriately-configured container.
