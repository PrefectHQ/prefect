description: Prefect variables are dynamic-named, mutable string values, much like environment variables.
tags:
    - variables
    - blocks

# Variables

Variables are dynamic-named, mutable string values, much like environment variables. Variables are scoped to a Prefect Server instance or a single workspace in Prefect Cloud.

Variables can be created or modified at any time, but are intended for values with infrequent writes and frequent reads. Variable values may be cached for quicker retrival.

While variable values are most commonly loaded during flow runtime, they can be loaded in other contexts, at any time, such that they can be used to pass configuration information to Prefect services, such as workers.

## Manging variables
You can create, read, edit and delete variables via the Prefect UI, API, and CLI. Names must:
- have less than or equal to 255 characters.
- only contain lowercase alphanumeric characters ([a-z], [0-9]) or underscores (_). Spaces are not allowed.
- be unique.

Values must:
- have less than or equal to 5000 characters.

Optionally, you can add tags to the variable.

### Via the Prefect UI

You can see all the variables in your Prefect Server instance or Prefect Cloud workspace on the **Variables** page of the Prefect UI. Both the name and value of all variables are visible to anyone with access to the server or workspace.

To create a new variable, select the **+** button next to the header of the **Variables** page. Enter the name and value of the variable.

### Via the REST API
Variables can be created and deleted via the REST API. You can also set and get variables via the API with either the variable name or ID. See the [REST reference](https://app.prefect.cloud/api/docs#tag/Variables) for more information.

### Via the CLI
You can list, inspect, and delete variables via the command line interface with the `prefect variable ls`, `prefect variable inspect <name>`, and `prefect variable delete <name>` commands, respectively.

## Accessing variables
In addition to the UI and API, variables can be referenced in code and in certain Prefect configuration files.

### In Python code
You can access any variable via the Python SDK.

```python
from prefect import variables
answer = variables.get('the_answer')
print(answer)
# 42

answer = await variables.get('the_answer')
print(answer)
# 42

answer = variables.get('not_a_variable')
print(answer)
# None

answer = variables.get('not_a_variable', default='42')
print(answer)
# 42
```

### In Prefect configuration

