# Writing imports

A brief collection of rules and guidelines for how imports should be handled in this repository.

## Imports in `__init__` files

`__init__` files should be left empty unless exposing an interface. If exposing submodules or submodule objects to present a simpler API, the following rules must be followed.

### Exposing objects from submodules

If importing objects from submodules, the `__init__` file should import from the local path.

Right:

```python
from .flows import flow
```

Wrong:

```python
from prefect.flows import flow
```

This is [required for type checkers](https://github.com/microsoft/pyright/blob/main/docs/typed-libraries.md#library-interface) to understand the exposed interface.

### Exposing submodules

If exposing submodules, the same rule applies.

Right

```
from . import flows
```

Wrong:

```python
import prefect.flows
```

Generally, submodules should _not_ be imported in the `__init__` file. Submodules should only be exposed when the module is designed to be imported and used as a namespaced object. 

For example, we do this for our schema and model modules:

```python
import prefect.orion.schemas as schemas

# The full module is accessible now
schemas.core.FlowRun
```

## Imports in modules

### Importing other modules

Modules should not be imported using the `from` syntax.

Right:

```python
import prefect.orion.schemas as schemas
```

Wrong:

```python
from prefect.orion import schemas
```

The `from` syntax should be reserved for importing objects from modules.