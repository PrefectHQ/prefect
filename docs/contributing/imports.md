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

For example, we do this for our schema and model modules because the it is important to know if you are working with a API schema or database model which may have similar names.

```python
import prefect.orion.schemas as schemas

# The full module is accessible now
schemas.core.FlowRun
```

#### Side-effects

Another justifiable use-case is for submodules that perform global side-effects.

Often, global side-effects on import are a dangerous pattern. Avoid them if feasible.

We have a couple uses of this currently:

- To register dispatchable types in `prefect.serializers`.
- To extend our CLI application in `prefect.cli`.

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

### Deferred imports

Sometimes, we must perform imports _within_ a function to avoid a circular dependency.

```python
# This function in `settings.py` requires a method from the global `context` but the context
# uses settings
def from_context():
    from prefect.context import get_profile_context

    ...
```

Attempt to avoid circular dependencies. This often reveals overentanglement in the design.

When performing deferred imports, they should all be placed at the top of the function.

If you are just using the imported object for a type signature, you should use the `TYPE_CHECKING` flag.

```python
from typing import TYPE_CHECKING:

if TYPE_CHECKING:
    from prefect.orion.schemas.states import State
```

### Importing optional requirements

We do not have a best practice for this yet. See the `kubernetes`, `docker`, and `distributed` implementations for now.
