# Strings

## StringFormatter <Badge text="task"/>

A convenience Task for functionally creating Task instances with arbitrary callable `run` methods. This is the Task that powers Prefect's `@task` decorator.

[API Reference](/api/unreleased/tasks/strings.html#prefect-tasks-templates-strings-stringformattertask)

## JinjaTemplate <Badge text="task"/>

This task contains a Jinja template which is formatted with the results of any upstream tasks and returned.

Variables from `prefect.context` will also be used for rendering.

[API Reference](/api/unreleased/tasks/strings.html#prefect-tasks-templates-jinja2-jinjatemplatetask)
