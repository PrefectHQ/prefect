---
description: Prefect will run your deployment on our infrastructure.
tags:
    - managed infrastructure
search:
  boost: 2
---

# TK no index, no show in search results

# Managed Execution

Prefect Cloud provides a **prefect-managed** execution environment you can use for your deployments.
This means that you can run your flows on our infrastructure, without having to worry about provisioning or maintaining your own infrastructure.
Managed execution is a great option for users who want to get started quickly, or who don't want to manage their own infrastructure.

!!! warning "Managed Execution is in alpha"
    Managed Execution is currently in alpha.
    BeIf you are interested in using this feature, please contact us at []()

##

## Example

## Limitations

### Concurrency

Currently limited to 10 flow runs at a time.

### Images

Managed execution requires that you run one of the offered Docker images.
You may not use your own Docker image.
However, as noted above, you can

If you need to use your own image, we recommend using another type of work pool.

### Resources

Resources are limited to 200Mb of RAM
