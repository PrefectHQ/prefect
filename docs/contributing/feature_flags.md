---
description: Guidelines for using feature flags during development.
tags:
   - contributing
   - development
---

# Feature Flags

This section describes how Prefect uses feature flagging during
development.

## What are feature flags?

_Feature flagging_ is the process of introducing _flags_ that allow
developers to turn a feature of an application on or off at runtime &mdash;
without having to deploy code.

## When to use feature flags

Not everything that an application wants to make configurable at runtime
should become a feature flag. Because feature flags usually introduce
branching logic at every point that needs to reference a flag, they add
complexity and maintenance burden.

The ideal uses of feature flags are:

1. Testing a new feature before it's complete. With feature flags,
   a developer can test, merge, and deploy an incomplete feature.
   This lets us move faster and integrate in-progress systems early.

2. Releasing a feature to a subset of users, AKA "canary releases."
   On this technique, we release a new (complete) feature to a small
   group of users, monitor the results, and gradually release the
   feature to more users until 100% of users see the new feature.

A crucial fact about both of these uses of feature flags is that soon
after the feature is "complete," we remove the feature flag and
the branching logic from the codebase, keeping our code clean.

## Creating a new flag

To create a feature flag, first define a new feature name in the module
`prefect/utilities/feature_flags.py`. You should do so at the bottom of
the module because you'll be using functions defined within the module.

```python
MY_FLAG = "my-flag"

create_if_missing(MY_FLAG)
```

By default, new flags are disabled, but you can make the flag enabled by
default instead:

```python
create_if_missing(MY_FLAG, is_enabled=True)
```

## Checking if a flag is enabled

When you want to check if the flag is enabled from elsewhere in the
application, you'll import the flag name and call `flag_is_enabled()`:

```python
from prefect.utilities import feature_flags


def your_function():
    if feature_flags.flag_is_enabled(feature_flags.MY_FLAG):
        # your_special_logic()
        ...
    else:
        # your_normal_logic()
        ...
```

## Enabling or disabling a feature flag based on conditions

You can attach "conditions" to a flag so that a flag is only
enabled if you pass input data satisfying the condition when you
check the flag at runtime.

For example, to make a flag that only affects admin users, you'd
create an `is_admin` condition and include it when creating the flag
at the bottom of the `feature_flags.md` module:

```python
from flipper import Condition


MY_FLAG = "my-flag"
IS_ADMIN = Condition(is_admin=True)

create_if_missing(MY_FLAG, conditions=[is_admin])
```

!!! note "Referencing the condition object"
    You won't need to refer to the condition object later. This example
    includes it as a separate variable for ease of reading.

Then, at runtime, you can check the flag by specifying the condition
as a keyword argument to `flag_is_enabled()`:

```python
from prefect.utilities import feature_flags


# Note: The difference between this and the last example of using
# `flag_is_enabled` is that this time, we pass `is_admin=True`.
if feature_flags.flag_is_enabled(feature_flags.MY_FLAG, is_admin=True):
    # your_special_logic()
    ...
else:
    # your_normal_logic()
    ...
```

Passing conditions as input to `flag_is_enabled()` is not required
when you check if a flag that has conditions is enabled. If you don't specify
any conditions to `flag_is_enabled()`, the return value is the current state
of the flag, e.g. `True` if the flag is enabled.

## Turning a flag on and off for specific "buckets"

You can set a "bucketer" for a feature flag to use. This is useful for
canary roll-outs of a feature, when you want to roll out a feature to e.g.
10% of users. Like with conditions, you indicate a bucketer when you
create a flag in `prefect/utilities/feature_flags.py`:

```python
from flipper.bucketing import Percentage, PercentageBucketer

MY_FLAG = "my-flag"
TEN_PERCENT_BUCKETER = PercentageBucketer(percentage=Percentage(0.1))

create_if_missing(MY_FLAG, bucketer=TEN_PERCENT_BUCKETER)
```

For more details, see the [docs for the flipper-client library](https://github.com/carta/flipper-client).
