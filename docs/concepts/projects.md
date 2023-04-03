---
description: Learn how Prefect projects allow you to easily manage your code and deployments.
tags:
    - work pools
    - workers
    - orchestration
    - flow runs
    - deployments
    - projects
    - storage
    - infrastructure
    - blocks
    - tutorial
---

# Projects<span class="badge beta"></span>

A project is a minimally opinionated set of files that describe how to prepare one or more [flow deployments](/concepts/deployments/).  At a high level, a project is a directory with the following key files stored in the root:

- [`deployment.yaml`](#the-deployment-yaml-file): a YAML file describing base settings for a deployment produced from this project
- [`prefect.yaml`](#the-prefect-yaml-file): a YAML file describing procedural steps for preparing a deployment from this project, as well as instructions for preparing the execution environment for a deployment run
- [`./prefect`](#the-prefect-directory): a hidden directory where Prefect will store workflow metadata

Projects can be initialized via the CLI command `prefect project init` run anywhere you consider to be the root of a project.  

!!! tip "Project recipes"
    Prefect ships with many off-the-shelf "recipes" that allow you to get started with more structure within your `deployment.yaml` and `prefect.yaml` files; run `prefect project recipe ls` to see what recipes are available in your installation. You can provide a recipe name in your initialization command with the `--recipe` flag, otherwise Prefect will attempt to guess an appropriate recipe based on the structure of your project directory (for example if you initialize within a `git` repository, Prefect will use the `git` recipe).

## The Deployment YAML file

The `deployment.yaml` file contains default configuration for all deployments created from within this project; all settings within this file can be overridden via the `prefect deploy` CLI command when creating a deployment.

The base structure for `deployment.yaml` is as follows:

```yaml
# base metadata
name: null
version: null
tags: []
description: null
schedule: null

# flow-specific fields
flow_name: null
entrypoint: null
path: null
parameters: {}
parameter_openapi_schema: null

# infra-specific fields
work_pool:
  name: null
  work_queue_name: null
  job_variables: {}
```

You can create deployments via the CLI command `prefect deploy` without ever needing to alter this file in any way - its sole purpose is for version control and providing base settings in the situation where you are creating many deployments from your project.  [As described below](#deployment-mechanics), when creating a deployment these settings are first loaded from this base file, and then any additional flags provided via `prefect deploy` are layered on top before registering the deployment with the Prefect API.

### Templating Options

Values that you place within your `deployment.yaml` file can reference dynamic values in two different ways:

- **step outputs**: every step of both `build` and `push` produce named fields such as `image_name`; you can reference these fields within `deployment.yaml` and `prefect deploy` will populate them with each call.  References must be enclosed in double brackets and be of the form `"{{ field_name }}"`
- **blocks**: [Prefect blocks](/concepts/blocks) can also be referenced with the special syntax `{{ prefect.blocks.block_type.block_slug }}`

As an example, consider the following `deployment.yaml` file:

```yaml
# base metadata
name: null
version: "{{ image_tag }}"
tags:
    - "{{ image_tag }}"
description: null
schedule: null

# flow-specific fields
flow_name: null
entrypoint: null
path: null
parameters: {}
parameter_openapi_schema: null

# infra-specific fields
work_pool:
  name: "my-k8s-work-pool"
  work_queue_name: null
  job_variables:
    image: "{{ image_name }}"
    cluster_config: "{{ prefect.blocks.kubernetesclusterconfig.my-favorite-config }}"
```

So long as our `build` steps produce fields called `image_name` and `image_tag`, every time we deploy a new version of our deployment these fields will be dynamically populated with the relevant values.

!!! note "Docker step"
    The most commonly used build step is [`prefect_docker.projects.steps.build_docker_image`](https://prefecthq.github.io/prefect-docker/projects/steps/#prefect_docker.projects.steps.build_docker_image) which produces both the `image_name` and `image_tag` fields.

## The Prefect YAML file

The `prefect.yaml` file contains instructions for how to build and push any necessary code artifacts (such as Docker images) from this project, as well as instructions for pulling a deployment in remote execution environments (e.g., cloning a GitHub repository).

The base structure for `prefect.yaml` is as follows:

```yaml
# generic metadata
prefect-version: null
name: null

# preparation steps
build: null
push: null

# runtime steps
pull: null
```

The metadata fields are always pre-populated for you and are currently for bookkeeping purposes only.  The other sections are pre-populated based on recipe; if no recipe is provided, Prefect will attempt to guess an appropriate one based on local configuration.  Each step has the following format:

```yaml
section:
  - prefect_package.path.to.importable.step:
      requires: "pip-installable-package-spec" # optional
      kwarg1: value
      kwarg2: more-values
```

Every step can optionally provide a `requires` field that Prefect will use to auto-install in the event that the step cannot be found in the current environment.  The additional fields map directly onto Python keyword arguments to the step function.  Within a given section, steps always run in the order that they are provided within the `prefect.yaml` file.  

!!! tip "Step templating"
    [Just as in `deployment.yaml`](#templating-options), step inputs can be templated with the outputs of prior steps or with block references.

For more information on the mechanics of steps, [see below](#deployment-mechanics).

### The Build Section
### The Push Section
### The Pull Section

The pull section is the most important section within the `prefect.yaml` file as it contains instructions for preparing this project for a deployment run.  These instructions will be executed each time a deployment created wthin this project is run via a worker.

## The `.prefect/` directory

In general this directory doesn't need to be altered or inspected by users (hence the fact that it is hidden); its only use case right now is storing the existence of known workflows within your project in the `flows.json` file.  Workflows get registered into `.prefect/flows.json` through two mechanisms:

- running `prefect deploy` with an entrypoint (e.g., `prefect deploy ./path/to/file.py:flow_func`) will automatically register this flow within this project
- explicity running `prefect project register-flow ./path/to/file.py:flow_func` allows users to register flows explicitly themselves

Registration of flows allows you to to deploy based on flow name reference using the `--flow` or `-f` flag of `prefect deploy`:

<div class="terminal">
```bash
$ prefect deploy -f 'My Flow Name'
```
</div>

Registration also allows users to share their projects without requiring a full understanding of the project's file structure; for example, you can commit `./prefect/flows.json` to a version control system, and allow users to deploy these flows without needing to know each flow's individual entrypoint.

## Deployment mechanics

When creating a deployment via `prefect deploy`, the following steps are taken in order:

- first, run the `prefect.yaml` `build` section, if provided; steps within this section will always run in order
- next, run the `prefect.yaml` `push` section, if provided; steps within this section will always run in order
