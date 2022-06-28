# Artifacts

The [Artifacts API](/api/latest/backend/artifacts.html) enables you to publish data from task runs that is rendered natively in the Prefect UI, both Prefect Cloud and Prefect Server. 

Using the Artifacts API, you can easily publish information directly to the Prefect UI. These published artifacts are linked to specific task runs and flow runs, and artifacts can render more sophisticated information than you'd typically log, such as reports, tables, charts, images, and links to external data.

Currently, the Artifacts API enables you to render the following artifact types:

- Links
- Markdown

Link artifacts render a clickable hyperlink as an artifact.

Markdown artifacts render strings that can include [Github-flavored Markdown](https://github.github.com/gfm/) markup for formatting. 

!!! tip Artifacts render individually
    Note that each artifact you create in a task renders as an individual artifact in the Prefect UI. In other words, each call to `create_link_artifact()` or `create_markdown_artifact()` creates its own, separate artifact.

    Within a task, you may use these commands as many times as necessary, but they do not operate in the same manner as a `print()` command where you might string together multiple calls to add additional items to a report. 

    As a best practice, such as when using `create_markdown_artifact()` to create artifacts like reports or summaries, compile your message string separately, then pass to `create_markdown_artifact()` or `update_markdown_artifact()` to create the full artifact.


For more background on the design goals for the Artifacts API, see the [Introducing: The Artifacts API](https://www.prefect.io/blog/introducing-the-artifacts-api) blog post and the [Great Expectations task](/api/latest/tasks/great_expectations.html).

## UI

In the Prefect UI, to view artifacts created by a flow run, navigate to a specific flow run, then click the **Artifacts** tab.

![Screenshot showing the Artifacts tab for a flow run](/orchestration/concepts/artifacts_flowrun.png)

You can navigate between the artifacts created for a flow run by clicking the dots or arrows above the artifacts.

Each artifact is identified by task that created it.

To view the artifacts created by a task run, navigate to the specific task run, then click the **Artifacts** tab.

![Screenshot showing the Artifacts tab for a task run](/orchestration/concepts/artifacts_taskrun.png)

You can navigate between the artifacts created for a task run by clicking the dots or arrows above the artifacts.

## Creating Link Artifacts

To create link artifacts, just import `create_link_artifact` from `prefect.backend.artifacts`, then add a call to `create_link_artifact()` to any task orchestrated through a Prefect API. 

!!! tip Import path
    If you are using a version prior to Prefect 0.15.8, import `create_link` from `prefect.artifacts`.


Pass `create_link_artifact()` a string containing the absolute URL of the location to which you want to link. 

```python
from prefect import task, Flow
from prefect.backend.artifacts import create_link_artifact

@task
def make_artifact():
    create_link_artifact("https://www.prefect.io/")
```

After the task runs, navigate to the UI’s Artifacts tab to see the output.

In addition to creating an artifact, `create_link_artifact()` returns the ID of the artifact it created. You can use the ID to:

- Update the artifact using `update_link_artifact()`.
- Delete the artifact using `delete_artifact()`.

Note that `update_link_artifact()` updates an existing link artifact by replacing the entire current artifact string with the new data provided. See [Creating Markdown Artifacts](#creating-markdown-artifacts) and [Deleting Artifacts](#deleting-artifacts) for examples of these update and delete operations.

## Creating Markdown Artifacts

To create link artifacts, just import `create_markdown_artifact` from `prefect.backend.artifacts`, then add a call to `create_markdown_artifact()` to any task orchestrated through a Prefect API. 

!!! tip Import path
    If you are using a version prior to Prefect 0.15.8, import `create_markdown` from `prefect.artifacts`.


Pass `create_markdown_artifact()` a string that will be rendered as an artifact. The string can contain any [Github-flavored Markdown](https://github.github.com/gfm/) markup including image references, links, and tables. 

Note that any images referenced in your markdown must be linked by the absolute URL of a publicly available image. Linking to local files or by relative URL is not supported.

```python
from prefect import task, Flow
from prefect.backend.artifacts import create_markdown_artifact

@task
def make_artifact():
    create_markdown_artifact("# Heading\n\nText with [link]("https://www.prefect.io/").")
```

After the task runs, navigate to the UI’s Artifacts tab to see the output.

`create_markdown_artifact()` accepts any valid Python string and variable interpolation including, for example, f-strings.

In addition to creating an artifact, `create_markdown_artifact()` returns the ID of the artifact it created. You can use the ID to:

- Update the artifact using `update_markdown_artifact()`.
- Delete the artifact using `delete_artifact()`.

Note that `update_markdown_artifact()` updates an existing markdown artifact by replacing the entire current markdown artifact with the new data provided. Here's an example of appending new report data to an existing artifact.

```python
from prefect import task, Flow
from prefect.backend.artifacts import create_markdown_artifact, update_markdown_artifact

@task(nout=2)
def make_report():
    report = "# My Report\n\nHello!"
    artifact_id = create_markdown_artifact(report)
    # Return both the ID of the new artifact and the original content
    return artifact_id, report

@task
def add_to_report(artifact_id, current_report):
    # Append new sections to the existing report
    current_report += "\n\n## Subsection\n\ngoodbye!"
    # Update artifact by ID with replaced text
    update_markdown_artifact(artifact_id, current_report)

with Flow(name="appending-artifact") as flow:
    artifact_id, report = make_report()
    add_to_report(artifact_id, report)
```

!!! tip Markdown strings and line endings
    Explicit line endings and blank lins are important to rendering markdown correctly. When formatting markdown for artifacts, make sure that you include explicit line endings (`\n` or equivalent) where appropriate.


## Deleting Artifacts

To delete existing link or markdown artifacts, import `delete_artifact` from `prefect.backend.artifacts`, then add a call to `delete_artifact()` to any task orchestrated through a Prefect API, passing the ID of the artifact to delete.

```python
from prefect import task, Flow
from prefect.backend.artifacts import create_markdown_artifact, delete_artifact

@task
def make_artifact(artifact_msg):
    artifact_id = create_markdown_artifact(artifact_msg)
    return artifact_id

@task
def remove_artifact(artifact_id):
    delete_artifact(artifact_id)

with Flow(name="deleting-artifact") as flow:
    msg = "Space is big. Really big."
    artifact_id = make_artifact(msg)
    remove_artifact(artifact_id)
```

Artifacts cannot be retrieved once deleted.
