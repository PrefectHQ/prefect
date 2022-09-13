---
description: Code style and best practices for contributions to Prefect.
tags:
    - standards
    - code style
    - coding practices
    - contributing
---

# Code style and practices

Generally, we follow the [Google Python Style Guide](https://google.github.io/styleguide/pyguide.html). This document covers sections where we differ or where additional clarification is necessary.

## Imports

A brief collection of rules and guidelines for how imports should be handled in this repository.

### Imports in `__init__` files

Leave `__init__` files empty unless exposing an interface. If you must expose objects to present a simpler API, please follow these rules.

#### Exposing objects from submodules

If importing objects from submodules, the `__init__` file should use a relative import. This is [required for type checkers](https://github.com/microsoft/pyright/blob/main/docs/typed-libraries.md#library-interface) to understand the exposed interface.

```python
# Correct
from .flows import flow
```

```python
# Wrong
from prefect.flows import flow
```

#### Exposing submodules

Generally, submodules should _not_ be imported in the `__init__` file. Submodules should only be exposed when the module is designed to be imported and used as a namespaced object.

For example, we do this for our schema and model modules because it is important to know if you are working with an API schema or database model, both of which may have similar names.

```python
import prefect.orion.schemas as schemas

# The full module is accessible now
schemas.core.FlowRun
```

If exposing a submodule, use a relative import as you would when exposing an object.

```
# Correct
from . import flows
```

```python
# Wrong
import prefect.flows
```

#### Importing to run side-effects

Another use case for importing submodules is perform global side-effects that occur when they are imported.

Often, global side-effects on import are a dangerous pattern. Avoid them if feasible.

We have a couple acceptable use-cases for this currently:

- To register dispatchable types, e.g. `prefect.serializers`.
- To extend a CLI application e.g. `prefect.cli`.

### Imports in modules

#### Importing other modules

The `from` syntax should be reserved for importing objects from modules. Modules should not be imported using the `from` syntax.

```python
# Correct
import prefect.orion.schemas  # use with the full name
import prefect.orion.schemas as schemas  # use the shorter name
```

```python
# Wrong
from prefect.orion import schemas
```

Unless in an `__init__.py` file, relative imports should not be used.


```python
# Correct
from prefect.utilities.foo import bar
```

```python
# Wrong
from .utilities.foo import bar
```

Imports dependent on file location should never be used without explicit indication it is relative. This avoids confusion about the source of a module.

```python
# Correct
from . import test
```

```python
# Wrong
import test
```

#### Resolving circular dependencies

Sometimes, we must defer an import and perform it _within_ a function to avoid a circular dependency.

```python
## This function in `settings.py` requires a method from the global `context` but the context
## uses settings
def from_context():
    from prefect.context import get_profile_context

    ...
```

Attempt to avoid circular dependencies. This often reveals overentanglement in the design.

When performing deferred imports, they should all be placed at the top of the function.

##### With type annotations

If you are just using the imported object for a type signature, you should use the `TYPE_CHECKING` flag.

```python
# Correct
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from prefect.orion.schemas.states import State

def foo(state: "State"):
    pass
```

Note that usage of the type within the module will need quotes e.g. `"State"` since it is not available at runtime.

#### Importing optional requirements

We do not have a best practice for this yet. See the `kubernetes`, `docker`, and `distributed` implementations for now.

#### Delaying expensive imports

Sometimes, imports are slow. We'd like to keep the `prefect` module import times fast. In these cases, we can lazily import the slow module by deferring import to the relevant function body. For modules that are consumed by many functions, the pattern used for optional requirements may be used instead.

## Command line interface (CLI) output messages

Upon executing a command that creates an object, the output message should offer:
- A short description of what the command just did.
- A bullet point list, rehashing user inputs, if possible.
- Next steps, like the next command to run, if applicable.
- Other relevant, pre-formatted commands that can be copied and pasted, if applicable.
- A new line before the first line and after the last line.

Output Example:
```bash
$ prefect work-queue create testing

Created work queue with properties:
    name - 'abcde'
    uuid - 940f9828-c820-4148-9526-ea8107082bda
    tags - None
    deployment_ids - None

Start an agent to pick up flows from the created work queue:
    prefect agent start -q 'abcde'

Inspect the created work queue:
    prefect work-queue inspect 'abcde'

```

Additionally:

- Wrap generated arguments in apostrophes (') to ensure validity by using suffixing formats with `!r`.
- Indent example commands, instead of wrapping in backticks (&#96;).
- Use placeholders if the example cannot be pre-formatted completely.
- Capitalize placeholder labels and wrap them in less than (<) and greater than (>) signs.
- Utilize `textwrap.dedent` to remove extraneous spacing for strings that are written with triple quotes (""").

Placholder Example:
```bash
Create a work queue with tags:
    prefect work-queue create '<WORK QUEUE NAME>' -t '<OPTIONAL TAG 1>' -t '<OPTIONAL TAG 2>'
```

Dedent Example:
```python
from textwrap import dedent
...
output_msg = dedent(
    f"""
    Created work queue with properties:
        name - {name!r}
        uuid - {result}
        tags - {tags or None}
        deployment_ids - {deployment_ids or None}

    Start an agent to pick up flows from the created work queue:
        prefect agent start -q {name!r}

    Inspect the created work queue:
        prefect work-queue inspect {name!r}
    """
)
```

## API Versioning

The Prefect 2 client can be run separately from the Prefect 2 orchestration server and communicate entirely via an API. Among other things, the Prefect client includes anything that runs task or flow code, (e.g. agents, and the Python client) or any consumer of Prefect metadata, (e.g. the Prefect UI, and CLI). The Orion server stores this metadata and serves it via the REST API.

Sometimes, we make breaking changes to the API (for good reasons). In order to check that a Prefect 2 client is compatible with the API it's making requests to, every API call the client makes includes a three-component `API_VERSION` header with major, minor, and patch versions.

For example, a request with the `X-PREFECT-API-VERSION=3.2.1` header has a major version of `3`, minor version `2`, and patch version `1`.

This version header can be changed by modifying the `API_VERSION` constant in `prefect.orion.api.server`.

When making a breaking change to the API, we should consider if the change might be *backwards compatible for clients*, meaning that the previous version of the client would still be able to make calls against the updated version of the server code. This might happen if the changes are purely additive: such as adding a non-critical API route. In these cases, we should make sure to bump the patch version.

In almost all other cases, we should bump the minor version, which denotes a non-backwards-compatible API change. We have reserved the major version chanes to denote also-backwards compatible change that might be significant in some way, such as a major release milestone.
