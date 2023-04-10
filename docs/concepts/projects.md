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
- [`.prefect/`](#the-prefect-directory): a hidden directory where Prefect will store workflow metadata

Projects can be initialized by running the CLI command `prefect project init` in any directory that you consider to be the root of a project.  

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
- **blocks**: [Prefect blocks](/concepts/blocks) can also be referenced with the special syntax `{{ prefect.blocks.block_type.block_slug }}`; it is highly recommended that you use block references for any sensitive information (such as a GitHub access token or any credentials) to avoid hardcoding these values in plaintext

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
    The most commonly used build step is [`prefect_docker.projects.steps.build_docker_image`](https://prefecthq.github.io/prefect-docker/projects/steps/#prefect_docker.projects.steps.build_docker_image) which produces both the `image_name` and `image_tag` fields.  For an example, [check out the project tutorial](/tutorials/projects/#dockerized-deployment).

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

The build section of `prefect.yaml` is where any necessary side effects for running your deployments are built - the most common type of side effect produced here is a Docker image.  If you initialize with the docker recipe, you will be prompted to provide required information, such as image name and tag: 

<div class="terminal">
```bash
$ prefect project init --recipe docker
>> image_name: < insert image name here >
>> tag: < insert image tag here >
```
</div>

!!! tip "Use `--field` to avoid the interactive experience"
    We recommend that you only initialize a recipe when you begin a project, and afterwards store your configuration files within version control; however, sometimes you may need to initialize programmatically and avoid the interactive prompts.  To do so, provide all required fields for your recipe using the `--field` flag:
    <div class="terminal">
    ```bash
    $ prefect project init --recipe docker \
        --field image_name=my-repo/my-image \
        --field tag=my-tag
    ```
    </div>
    
```yaml
build:
- prefect_docker.projects.steps.build_docker_image:
    requires: prefect-docker>=0.2.0
    image_name: my-repo/my-image
    tag: my-tag
    dockerfile: auto
```

Once you've confirmed that these fields are set to their desired values, this step will automatically build a Docker image with the provided name and tag and push it to the repository referenced by the image name.  [As the documentation notes](https://prefecthq.github.io/prefect-docker/projects/steps/#prefect_docker.projects.steps.BuildDockerImageResult), this step produces a few fields that can optionally be used in future steps or within `deployment.yaml` as template values.  It is best practice to use `{{ image_name }}` within `deployment.yaml` (specificially the work pool's job variables section) so that you don't risk having your build step and deployment specification get out of sync with hardcoded values.  For a worked example, [check out the project tutorial](/tutorials/projects/#dockerized-deployment).


!!! note Some steps require Prefect integrations
    Note that in the build step example above, we relied on the `prefect-docker` package; in cases that deal with external services, additional packages are often required and will be auto-installed for you.

### The Push Section

The push section is most critical for situations in which code is not stored on persistent filesystems or in version control.  In this scenario, code is often pushed and pulled from a Cloud storage bucket of some kind (e.g., S3, GCS, Azure Blobs, etc.).  The push section allows users to specify and customize the logic for pushing this project to arbitrary remote locations. 

For example, a user wishing to store their project in an S3 bucket and rely on default worker settings for its runtime environment could use the `s3` recipe:

<div class="terminal">
```bash
$ prefect project init --recipe s3
>> bucket: < insert bucket name here >
```
</div>

Inspecting our newly created `prefect.yaml` file we find that the `push` and `pull` sections have been templated out for us as follows:

```yaml
push:
  - prefect_aws.projects.steps.push_project_to_s3:
      requires: prefect-aws>=0.3.0
      bucket: my-bucket
      folder: project-name
      credentials: null

pull:
  - prefect_aws.projects.steps.pull_project_from_s3:
      requires: prefect-aws>=0.3.0
      bucket: my-bucket
      folder: "{{ folder }}"
      credentials: null
```

The bucket has been populated with our provided value (which also could have been provided with the `--field` flag); note that the `folder` property of the `push` step is a template - the `pull_project_from_s3` step outputs both a `bucket` value as well as a `folder` value that can be used to template downstream steps.  Doing this helps you keep your steps consistent across edits. 

As discussed above, if you are using [blocks](/concepts/blocks/), the credentials section can be templated with a block reference for secure and dynamic credentials access:

```yaml
push:
  - prefect_aws.projects.steps.push_project_to_s3:
      requires: prefect-aws>=0.3.0
      bucket: my-bucket
      folder: project-name
      credentials: "{{ prefect.blocks.aws-credentials.dev-credentials }}"
```

Anytime you run `prefect deploy`, this `push` section will be executed upon successful completion of your `build` section. For more information on the mechanics of steps, [see below](#deployment-mechanics).

### The Pull Section

The pull section is the most important section within the `prefect.yaml` file as it contains instructions for preparing this project for a deployment run.  These instructions will be executed each time a deployment created wthin this project is run via a worker.

There are three main types of steps that typically show up in a `pull` section:

- `set_working_directory`: this step simply sets the working directory for the process prior to importing your flow
- `git_clone_project`: this step clones the provided repository on the provided branch
- `pull_project_from_{cloud}`: this step pulls the project directory from a Cloud storage location (e.g., S3)

!!! tip "Use block and variable references"
    All [block and variable references](#templating-options) within your pull step will remain unresolved until runtime and will be pulled each time your deployment is run. This allows you to avoid storing sensitive information insecurely; it also allows you to manage certain types of configuration from the API and UI without having to rebuild your deployment every time.

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

Anytime you run `prefect deploy`, the following actions are taken in order:

- the project `prefect.yaml` file is loaded; first, the `prefect.yaml` `build` section is loaded and all variable and block references are resolved. The steps are then run in the order provided
- next, the `push` section is loaded and all variable and block references are resolved; the steps within this section are then run in the order provided
- next, the `pull` section is templated with any step outputs but *is not run*.  Note that block references are _not_ hydrated for security purposes - block references are always resolved at runtime 
- next, the project `deployment.yaml` file is loaded. All variable and block references are resolved.  All flags provided via the `prefect deploy` CLI are then overlaid on the values loaded from the file. 
- the final step occurs when the fully realized deployment specification is registered with the Prefect API

Anytime a step is run, the following actions are taken in order:

- The step's inputs and block / variable references are resolved (see [the templating documentation above](#templating-options) for more details)
- The step's function is imported; if it cannot be found, the special `requires` keyword is used to install the necessary packages
- The step's function is called with the resolved inputs
- The step's output is returned and used to resolve inputs for subsequent steps

