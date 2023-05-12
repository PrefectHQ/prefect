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

- [`deployment.yaml`](#the-deployment-yaml-file): a YAML file describing base settings for deployments produced from this project
- [`prefect.yaml`](#the-prefect-yaml-file): a YAML file describing procedural steps for preparing a deployment from this project, as well as instructions for preparing the execution environment for a deployment run
- [`.prefect/`](#the-prefect-directory): a hidden directory where Prefect will store workflow metadata

Projects can be initialized by running the CLI command `prefect project init` in any directory that you consider to be the root of a project.  

!!! tip "Project recipes"
    Prefect ships with many off-the-shelf "recipes" that allow you to get started with more structure within your `deployment.yaml` and `prefect.yaml` files; run `prefect project recipe ls` to see what recipes are available in your installation. You can provide a recipe name in your initialization command with the `--recipe` flag, otherwise Prefect will attempt to guess an appropriate recipe based on the structure of your project directory (for example if you initialize within a `git` repository, Prefect will use the `git` recipe).

## The Deployment YAML file

The `deployment.yaml` file contains default configuration for all deployments created from within this project; all settings within this file can be overridden via the `prefect deploy` CLI command when creating a deployment.

The base structure for `deployment.yaml` is as follows:

```yaml
deployments:
  - # base metadata
    name: null
    version: null
    tags: []
    description: null
    schedule: null

    # flow-specific fields
    flow_name: null
    entrypoint: null
    parameters: {}

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
- **variables**: [Prefect variables](/concepts/variables) can also be referenced with the special syntax `{{ prefect.variables.variable_name }}`. Variables can be used reference non-sensitive, reusable pieces of information such as a default image name or a default work pool name.

As an example, consider the following `deployment.yaml` file:

```yaml
deployments:
  - # base metadata
    name: null
    version: "{{ image_tag }}"
    tags:
        - "{{ image_tag }}"
        - "{{ prefect.variables.some_common_tag }}"
    description: null
    schedule: null

    # flow-specific fields
    flow_name: null
    entrypoint: null
    parameters: {}

    # infra-specific fields
    work_pool:
        name: "my-k8s-work-pool"
        work_queue_name: null
        job_variables:
            image: "{{ image_name }}"
            cluster_config: "{{ prefect.blocks.kubernetes-cluster-config.my-favorite-config }}"
```

So long as our `build` steps produce fields called `image_name` and `image_tag`, every time we deploy a new version of our deployment these fields will be dynamically populated with the relevant values.

!!! note "Docker step"
    The most commonly used build step is [`prefect_docker.projects.steps.build_docker_image`](https://prefecthq.github.io/prefect-docker/projects/steps/#prefect_docker.projects.steps.build_docker_image) which produces both the `image_name` and `image_tag` fields.  
    
    For an example, [check out the project tutorial](/tutorials/projects/#dockerized-deployment).

### Working With Multiple Deployments

Projects can support multiple deployment declarations within a project's `deployment.yaml` file. This method of declaring multiple deployments allows the configuration for all deployments within a project to be version controlled and deployed with a single command.

New deployment declarations can be added to a project's `deployment.yaml` file by adding a new entry to the `deployments` list. Each deployment declaration must have a unique `name` field which is used to select deployment declarations when using the `prefect deploy` command.

For example, consider the following `deployment.yaml` file:

```yaml
deployments:
  - name: deployment-1
    entrypoint: flows/hello.py:my_flow
    parameters: 
        number: 42,
        message: Don't panic!
    work_pool:
        name: my-process-work-pool
        work_queue_name: primary-queue

  - name: deployment-2
    entrypoint: flows/goodbye.py:my_other_flow
    work_pool:
        name: my-process-work-pool
        work_queue_name: secondary-queue

  - name: deployment-3
    entrypoint: flows/hello.py:yet_another_flow
    work_pool:
        name: my-docker-work-pool
        work_queue_name: tertiary-queue
```

This file has three deployment declarations, each referencing a different flow in the project. Each deployment declaration has a unique `name` field and can be deployed individually by using the `--name` flag when deploying. 

For example, to deploy `deployment-1` we would run:

<div class="terminal">
```bash
$ prefect deploy --name deployment-1
```
</div>

To deploy multiple deployments you can provide multiple `--name` flags:

<div class="terminal">
```bash
$ prefect deploy --name deployment-1 --name deployment-2
```
</div>

To deploy all deployments in a project you can use the `--all` flag:

<div class="terminal">
```bash
$ prefect deploy --all
```
</div>

!!! note "CLI Options When Deploying Multiple Deployments"
    When deploying more than one deployment with a single `prefect deploy` command, any additional attributes provided via the CLI will be ignored.

    To provide overrides to a deployment via the CLI, you must deploy that deployment individually.


#### Reusing Configuration Across Deployments

Because a project's `deployment.yaml` file is a standard YAML file, you can use [YAML aliases](https://yaml.org/spec/1.2.2/#71-alias-nodes) to reuse configuration across deployments.

This functionality is useful when multiple deployments need to share the work pool configuration, deployment actions, or other configurations.

You can declare a YAML alias by using the `&{alias_name}` syntax and insert that alias elsewhere in the file with the `*{alias_name}` syntax. When aliasing YAML maps, you can also override specific fields of the aliased map by using the `<<: *{alias_name}` syntax and adding additional fields below.

We recommend adding a `definitions` section to your `deployment.yaml` file at the same level as the `deployments` section to store your aliases.

For example, consider the following `deployment.yaml` file:

```yaml
definitions:
    work_pools:
        my_docker_work_pool: &my_docker_work_pool
            name: my-docker-work-pool
            work_queue_name: default
            job_variables:
                image: "{{ image_name }}"
    schedules:
        every_ten_minutes: &every_10_minutes
            interval: 600
    actions:
        docker_build: &docker_build
            - prefect_docker.projects.steps.build_docker_image: &docker_build_config
                requires: prefect-docker>=0.2.0
                image_name: my-example-image
                tag: dev
                dockerfile: auto
                push: true

deployments:
  - name: deployment-1
    entrypoint: flows/hello.py:my_flow
    schedule: *every_10_minutes
    parameters: 
        number: 42,
        message: Don't panic!
    work_pool: *my_docker_work_pool
    build: *docker_build # Uses the full docker_build action with no overrides

  - name: deployment-2
    entrypoint: flows/goodbye.py:my_other_flow
    work_pool: *my_docker_work_pool
    build:
        - prefect_docker.projects.steps.build_docker_image:
            <<: *docker_build_config # Uses the docker_build_config alias and overrides the dockerfile field
            dockerfile: Dockerfile.custom

  - name: deployment-3
    entrypoint: flows/hello.py:yet_another_flow
    schedule: *every_10_minutes
    work_pool: 
        name: my-process-work-pool
        work_queue_name: primary-queue

```

In the above example, we are using YAML aliases to reuse work pool, schedule, and build configuration across multiple deployments:

- `deployment-1` and `deployment-2` are using the same work pool configuration
- `deployment-1` and `deployment-3` are using the same schedule 
- `deployment-1` and `deployment-2` are using the same build deployment action, but `deployment-2` is overriding the `dockerfile` field to use a custom Dockerfile

### Deployment Declaration Reference

#### Root Level Fields

Below are fields that can be added at the root level of the `deployment.yaml` file.

| Property | Description |
| --- | --- |
| <span class="no-wrap">`deployments`</span> | A list of deployment declarations for the current project. Fields for this section are documented in the [Deployment Fields](#deployment-fields) section. |
| `definitions` | Definitions for configuration that is shared across deployment declarations (e.g., schedules, deployment actions, etc.). |

#### Deployment Fields

Below are fields that can be added to each deployment declaration.

| Property | Description |
| --- | --- |
| `name` | The name to give to the created deployment. Used with the `prefect deploy` command to create or update specific deployments in a project. |
| `version` | An optional version for the deployment. |
| `tags` | A list of strings to assign to the deployment as tags. |
| <span class="no-wrap">`description`</span> | An optional description for the deployment. |
| `schedule` | An optional [schedule](/concepts/schedules) to assign to the deployment. Fields for this sections are documented in the [Schedule Fields](#schedule-fields) section. |
| `flow_name`   | The name of a flow that has been registered in the current project's [`.prefect` directory](#the-prefect-directory). Either `flow_name` **or** `entrypoint` is required. |
| `entrypoint` | The path to the `.py` file containing flow you want to deploy (relative to the root directory of your project) combined with the name of the flow function. Should be in the format `path/to/file.py:flow_function_name`. Either `flow_name` **or** `entrypoint` is required. |
| `parameters` | Optional default values to provide for the parameters of the deployed flow. Should be an object with key/value pairs. |
| `work_pool` | Information on where to schedule flow runs for the deployment. Fields for this sections are documented in the [Work Pool Fields](#work-pool-fields) section. |

#### Schedule Fields

Below are fields that can be added to a deployment declaration's `schedule` section.

| Property | Description |
| --- | --- |
| `interval` | Number of seconds indicating the time between flow runs. Cannot be used in conjunction with `cron` or `rrule`. |
| <span class="no-wrap">`anchor_date`</span> | Datetime string indicating the starting or "anchor" date to begin the schedule. If no `anchor_date` is supplied, the current UTC time is used. Can only be used with `interval`. |
| `timezone` | String name of a time zone, used to enforce localization behaviors like DST boundaries. See the [IANA Time Zone Database](https://www.iana.org/time-zones) for valid time zones. |
| `cron` | A valid cron string. Cannot be used in conjunction with `interval` or `rrule`. |
| `day_or` | Boolean indicating how croniter handles day and day_of_week entries. Must be used with `cron`. Defaults to `True`. |
| `rrule` | String representation of an RRule schedule. See the [`rrulestr` examples](https://dateutil.readthedocs.io/en/stable/rrule.html#rrulestr-examples) for syntax. Cannot be used in conjunction with `interval` or `cron`. |

For more information about schedules, see the [Schedules](/concepts/schedules/#creating-schedules-through-a-deployment-yaml-files-schedule-section) concept doc.

#### Work Pool Fields

Below are fields that can be added to a deployment declaration's `work_pool` section.

| Property | Description |
| --- | --- |
| `name` | The name of the work pool to schedule flow runs in for the deployment. |
| <span class="no-wrap">`work_queue_name`</span> | The name of the work queue within the specified work pool to schedule flow runs in for the deployment. If not provided, the default queue for the specified work pool with be used.  |
| `job_variables` | Values used to override the default values in the specified work pool's [base job template](/concepts/work-pools/#base-job-template). Maps directly to a created deployments `infra_overrides` attribute. |

## The Prefect YAML file

The `prefect.yaml` file contains default instructions for how to build and push any necessary code artifacts (such as Docker images) from this project, as well as default instructions for pulling a deployment in remote execution environments (e.g., cloning a GitHub repository).

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

!!! tip "Deployment Instruction Overrides"
    `build`, `push`, and `pull` sections can all be overridden a per-deployment basis by defining `build`, `push`, and `pull` fields within a deployment definition in the project's `deployment.yaml` file.

    The `prefect deploy` command will use any `build`, `push`, or `pull` instructions provided in a deployment's definition instead of the project's `prefect.yaml` file.

    This capability is useful for projects that have multiple deployments that require different deployment instructions.

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
    push: true
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

- The project `prefect.yaml` and `deployment.yaml` files are loaded. First, the `build` section is loaded and all variable and block references are resolved. The steps are then run in the order provided. 
- Next, the `push` section is loaded and all variable and block references are resolved; the steps within this section are then run in the order provided
- Next, the `pull` section is templated with any step outputs but *is not run*.  Note that block references are _not_ hydrated for security purposes - block references are always resolved at runtime 
- Next, all variable and block references are resolved with the deployment declaration.  All flags provided via the `prefect deploy` CLI are then overlaid on the values loaded from the file. 
- The final step occurs when the fully realized deployment specification is registered with the Prefect API

!!! tip "Deployment Instruction Overrides"
    The `build`, `push`, and `pull` sections in deployment definitions take precedence over the corresponding sections in `prefect.yaml`.


Anytime a step is run, the following actions are taken in order:

- The step's inputs and block / variable references are resolved (see [the templating documentation above](#templating-options) for more details)
- The step's function is imported; if it cannot be found, the special `requires` keyword is used to install the necessary packages
- The step's function is called with the resolved inputs
- The step's output is returned and used to resolve inputs for subsequent steps

