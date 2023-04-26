---
description: Prefect variables are dynamic-named, mutable string values, much like environment variables.
tags:
    - variables
    - blocks
---

# Variables

Variables enable you to store and reuse non-sensitive bits of data, such as configuration information. Variables are named, mutable string values, much like environment variables. Variables are scoped to a Prefect Server instance or a single workspace in Prefect Cloud.

Variables can be created or modified at any time, but are intended for values with infrequent writes and frequent reads. Variable values may be cached for quicker retrieval.

While variable values are most commonly loaded during flow runtime, they can be loaded in other contexts, at any time, such that they can be used to pass configuration information to Prefect configuration files, such as project steps.

!!! warning "Variables are not Encrypted"
    Using variables to store sensitive information, such as credentials, is not recommended. Instead, use [Secret blocks](https://docs.prefect.io/concepts/blocks/#prefect-built-in-blocks) to store and access sensitive information.

## Managing variables

You can create, read, edit and delete variables via the Prefect UI, API, and CLI. Names must adhere to traditional variable naming conventions:

- have less than or equal to 255 characters.
- only contain lowercase alphanumeric characters ([a-z], [0-9]) or underscores (_). Spaces are not allowed.
- be unique.

Values must:

- have less than or equal to 5000 characters.

Optionally, you can add tags to the variable.

### Via the Prefect UI

You can see all the variables in your Prefect Server instance or Prefect Cloud workspace on the **Variables** page of the Prefect UI. Both the name and value of all variables are visible to anyone with access to the server or workspace.

To create a new variable, select the **+** button next to the header of the **Variables** page. Enter the name and value of the variable.

![variables-ui](../img/concepts/variables-ui.png)

### Via the REST API

Variables can be created and deleted via the REST API. You can also set and get variables via the API with either the variable name or ID. See the [REST reference](https://app.prefect.cloud/api/docs#tag/Variables) for more information.

### Via the CLI

You can list, inspect, and delete variables via the command line interface with the `prefect variable ls`, `prefect variable inspect <name>`, and `prefect variable delete <name>` commands, respectively.

## Accessing variables

In addition to the UI and API, variables can be referenced in code and in certain Prefect configuration files.

### In Python code

You can access any variable via the Python SDK via the `.get()` method. If you attempt to reference a variable that does not exist, the method will return `None`.

```python
from prefect import variables

# from a synchronous context
answer = variables.get('the_answer')
print(answer)
# 42

# from an asynchronous context
answer = await variables.get('the_answer')
print(answer)
# 42

# with a default value
answer = variables.get('not_the_answer')
print(answer)
# None

# with a default value
answer = variables.get('not_the_answer', default='42')
print(answer)
# 42
```

### In Project steps

In `.yaml` files, variables are denoted by quotes and double curly brackets, like so: `"{{ prefect.variables.my_variable }}"`. You can use variables to templatize project steps by referencing them in the `prefect.yaml` file used to create deployments. For example, you could pass a variable in to specify a branch for a git repo in a projects `pull` step:

```
pull:
- prefect.projects.steps.git_clone_project:
    repository: https://github.com/PrefectHQ/hello-projects.git
    branch: "{{ prefect.variables.deployment_branch }}"
```

The `deployment_branch` variable will be evaluated at runtime for the deployed flow, allowing changes to be made to variables used in a pull action without updating a deployment directly.
