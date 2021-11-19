# Artifacts <Badge text="Beta"/>

The [Artifacts API](/api/latest/backend/artifacts.html) enables you to publish data from task runs that is rendered natively in the Prefect UI, both Prefect Cloud and Prefect Server. 

Using the Artifacts API, you can easily publish information directly to the Prefect UI. These published artifacts are linked to specific task runs and flow runs, and artifacts can render more sophisticated information than you'd typically log, such as reports, tables, charts, images, and links to external data.

Currently, the Artifacts API enables you to render the following artifact types:

- Links
- Markdown strings

Link artifacts render a clickable hyperlink as an artifact.

Markdown artifacts render strings that can include [Github-flavored Markdown](https://github.github.com/gfm/) markup for formatting. 

::: tip Artifacts render individually
Note that each artifact you create in a task renders as an individual artifact in the Prefect UI. In other words, each call to `create_link()` or `create_markdown()` creates its own, separate artifact.

Within a task, you may use these commands as many times as necessary, but they do not operate in the same manner as a `print()` command where you might string together multiple calls to add additional items to a report. 

As a best practice, such as when using `create_markdown()` to create artifacts like reports or summaries, compile your message string separately, then pass to `create_markdown()` to create the full artifact.
:::

For more background on the design goals for the Artifacts API, see the [Introducing: The Artifacts API](https://medium.com/the-prefect-blog/introducing-the-artifacts-api-b9e5972db043) blog post and the [Great Expectations task](/api/latest/tasks/great_expectations.html).

## UI

In the Prefect UI, to view artifacts created by a flow run, navigate to a specific flow run, then click the **Artifacts** tab.

![Screenshot showing the Artifacts tab for a flow run](/orchestration/concepts/artifacts_flowrun.png)

You can navigate between the artifacts created for a flow run by clicking the dots or arrows above the artifacts.

Each artifact is identified by task that created it.

To view the artifacts created by a task run, navigate to the specific task run, then click the **Artifacts** tab.

![Screenshot showing the Artifacts tab for a task run](/orchestration/concepts/artifacts_taskrun.png)

You can navigate between the artifacts created for a task run by clicking the dots or arrows above the artifacts.

## Creating Link Artifacts

To create link artifacts, just import `create_link` from `prefect.artifacts`, then add a call to `create_link()` to any task orchestrated through a Prefect API. 

Pass `create_link()` a string containing the absolute URI of the location to which you want to link. 

```python
from prefect import task, Flow
from prefect.artifacts import create_link

@task
def send_artifact():
    create_link("https://www.prefect.io/")
```

After the task runs, navigate to the UI’s Artifacts tab to see the output.

## Creating Markdown Artifacts

To create link artifacts, just import `create_markdown` from `prefect.artifacts`, then add a call to `create_markdown()` to any task orchestrated through a Prefect API. 

Pass `create_markdown()` a string that will be rendered as an artifact. The string can contain any [Github-flavored Markdown](https://github.github.com/gfm/) markup including images, links, and tables. 

```python
from prefect import task, Flow
from prefect.artifacts import create_markdown

@task
def send_artifact():
    create_markdown("# Heading\nText with [link]("https://www.prefect.io/").")
```

`create_markdown()` accepts any valid Python string and variable interpolation including, for example, f-strings.

```python
@task
def send_artifact(heading, link_text, link):
    create_markdown(f"# {heading}\nLink to [{link_text}]({link}).")
```

After the task runs, navigate to the UI’s Artifacts tab to see the output.

::: tip Markdown strings and line endings
Explicit line endings are important to the renderer correctly parsing markdown. When formatting markdown for artifacts, make sure that you include explicit line endings (`\n` or equivalent) where appropriate.
:::