# Operators

The tasks in this module can be used to represent builtin operations, including math, indexing, and logical comparisons.

In general, users will not instantiate these tasks by hand; they will automatically be
applied when users apply inline Python operators to a task and another value.

For example:

```python
Task() or Task() # applies Or
Task() + Task() # applies Add
Task() * 3 # applies Mul
Task()['x'] # applies GetItem
```

## GetItem <Badge text="task"/>

Helper task that retrieves a specific index of an upstream task's result.

[API Reference](/api/unreleased/tasks/operators.html#prefect-tasks-core-operators-getitem)


## Add <Badge text="task"/>

Evaluates `x + y`

[API Reference](/api/unreleased/tasks/operators.html#prefect-tasks-core-operators-add)

## Sub <Badge text="task"/>

Evaluates `x - y`

[API Reference](/api/unreleased/tasks/operators.html#prefect-tasks-core-operators-sub)

## Mul <Badge text="task"/>

Evaluates `x * y`

[API Reference](/api/unreleased/tasks/operators.html#prefect-tasks-core-operators-mul)

## Div <Badge text="task"/>

Evaluates `x / y`

[API Reference](/api/unreleased/tasks/operators.html#prefect-tasks-core-operators-div)

## FloorDiv <Badge text="task"/>

Evaluates `x // y`

[API Reference](/api/unreleased/tasks/operators.html#prefect-tasks-core-operators-floordiv)

## Pow <Badge text="task"/>

Evaluates `x ** y`

[API Reference](/api/unreleased/tasks/operators.html#prefect-tasks-core-operators-pow)

## Mod <Badge text="task"/>

Evaluates `x % y`

[API Reference](/api/unreleased/tasks/operators.html#prefect-tasks-core-operators-mod)

## And <Badge text="task"/>

Evaluates `x and y.`

[API Reference](/api/unreleased/tasks/operators.html#prefect-tasks-core-operators-and)

## Or <Badge text="task"/>

Evaluates `x or y`

[API Reference](/api/unreleased/tasks/operators.html#prefect-tasks-core-operators-or)

## Not <Badge text="task"/>

Evaluates `not x`

[API Reference](/api/unreleased/tasks/operators.html#prefect-tasks-core-operators-not)

## Equal <Badge text="task"/>

Evaluates `x == y`

[API Reference](/api/unreleased/tasks/operators.html#prefect-tasks-core-operators-equal)

## NotEqual <Badge text="task"/>

Evaluates `x != y`

[API Reference](/api/unreleased/tasks/operators.html#prefect-tasks-core-operators-notequal)

## GreaterThanOrEqual <Badge text="task"/>

Evaluates `x ≥ y`

[API Reference](/api/unreleased/tasks/operators.html#prefect-tasks-core-operators-greaterthanorequal)

## GreaterThan <Badge text="task"/>

Evaluates `x > y`

[API Reference](/api/unreleased/tasks/operators.html#prefect-tasks-core-operators-greaterthan)

## LessThanOrEqual <Badge text="task"/>

Evaluates `x ≤ y`

[API Reference](/api/unreleased/tasks/operators.html#prefect-tasks-core-operators-lessthanorequal)

## LessThan <Badge text="task"/>

Evaluates `x < y`

[API Reference](/api/unreleased/tasks/operators.html#prefect-tasks-core-operators-lessthan)
