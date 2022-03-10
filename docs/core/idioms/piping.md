# Using the functional pipe operator

## Background and Motivation

Functional pipes are a common idiom in several languages. For example, you may
be used to piping commands in bash:

```bash
echo "foo" | rev
# oof
```

You might also have noticed
that [Pandas offers a pipe method](https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.pipe.html)
, and it does so for many of the same reasons we will discuss below.

In Prefect, you may find yourself calling a long series of tasks, and you might
want a way to improve the readability of your code. For example, let's say we
have defined five tasks, named `task_1` through `task_5`, which each take a
single keyword argument called `keyword`. We then want to call them
sequentially, using the output from the previous task as the input to the next
task.

One way to do this is to nest the task function calls:

```python
res = task_5(task_4(task_3(task_2(task_1(arg, keyword=1), keyword=2), keyword=3), keyword=4), keyword=5)
```

Unfortunately this code is quite confusing. In particular, it reads from inside
out, which is confusing because it neither reads left-to-right nor
right-to-left.

Another way you might do this is by assigning the output from each task to an
intermediate variable:

```python
res_1 = task_1(arg)
res_2 = task_2(res_1)
res_3 = task_3(res_2)
res_4 = task_4(res_3)
res_5 = task_5(res_4)
```

This is much clearer. It now reads left-to-right, and then up-to-down, which is
very easy to follow for many readers. However, we now have introduced four
intermediate variables. This is annoying because we:

* Have to come up with concise names for each output variable, even though there
  might not be a logical name for each output
* Have to come up with names that don't clash with existing variable names
* Have to make sure we don't use the wrong variable as an input to any task
* Have polluted the namespace with variables we aren't going to actually use
  more than once

Functional piping offers an alternative that doesn't suffer the issues of either
these approaches.

## Piping in Prefect

Prefect offers two types of "pipe":

* `|`, the pipe operator, which sets task dependencies, but does *not* pass
  arguments between tasks
* `.pipe()`, the `Task` pipe method, which sets task dependencies *and* passes
  arguments between tasks

Since this first operator is very unusual to use, we will focus instead on
the `pipe` method. At its core, `task_a.pipe(task_b)` is *exactly equivalent
to* `task_b(task_a)`, or :

```python
var = task_a()
task_b(var)
```

However, the advantage of `.pipe` should become evident when we increase the
number of tasks. Returning to our example above, we can rewrite it using `.pipe`
as follows:

```python
task_1(arg, keyword=1).pipe(task_2, keyword=2).pipe(task_3, keyword=3)
```

Notice how this reads strictly left-to-right, and doesn't require us to invent
intermediate variable names.

To make this more readable as the number of tasks in the pipeline increases, you
may consider the "call chain" formatting style:

```python
(
    task_1(arg, keyword=1)
    .pipe(task_2, keyword=2)
    .pipe(task_3, keyword=3)
    .pipe(task_4, keyword=4)
    .pipe(task_5, keyword=5)
)
```

Not only is this easy to follow, but it's fully supported by
the [Black code formatter](https://black.readthedocs.io/en/stable/the_black_code_style/current_style.html#call-chains)
, which means you don't need to worry about manually formatting your pipeline.

## Primary Argument Position

When you use `.pipe()`, the left hand side (the "primary" argument) will be
passed in **as the first positional argument** to the right hand side. Consider
the following example:

```python
from prefect import task, Flow


@task()
def task_a(a):
    return 10


@task()
def task_b(a, b, c):
    return a + b * c


with Flow("my flow") as flow:
    task_a().pipe(task_b, b=2, c=5)
```

In this case, the output of `task_a()` (10), will be passed in as the `a`
parameter for `task_b`. If you want it to be passed in as a keyword argument, or
at a different position, consider rewriting your task function, or writing a
wrapper function. In the below example, the output of `task_a()` will instead be
passed in as the `b` parameter:

```python
def func_b(a, b, c):
    return a + b * c


@task()
def task_b(b, **kwargs):
    return func_b(b=b, **kwargs)


with Flow("my flow") as flow:
    task_a().pipe(task_b)
```

## Secondary Argument Positions

Note that so far we have only used keyword arguments as the "secondary"
arguments when we use `.pipe()`. This is because `.pipe()` **does not support** 
positional secondary arguments. Therefore, the following will always fail:

```python
task_a().pipe(task_b, 1, 2, 3)
```

This isn't actually a limitation however, because most arguments can be
expressed as keyword arguments.
Only [positional-only arguments](https://www.python.org/dev/peps/pep-0570/)
and `*args` cannot, but these are not supported by Prefect anyway.