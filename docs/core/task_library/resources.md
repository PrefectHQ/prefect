# Resources

Tasks and utilities for implementing control flow constructs like branching and
rejoining flows.

## ResourceManager <Badge text="class"/>

An object for managing temporary resources.

Used as a context manager, `ResourceManager` objects create tasks to setup and
cleanup temporary objects used within a block of tasks.  Examples might include
temporary Dask/Spark clusters, Docker containers, etc...

[API Reference](/api/latest/tasks/resources.html#resourcemanager)

## resource_manager <Badge text="fn"/>

A decorator for creating a `ResourceManager` object.

[API Reference](/api/latest/tasks/resources.html#prefect-tasks-resources-base-resource-manager)
