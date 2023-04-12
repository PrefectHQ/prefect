# Artifacts

Artifacts are persisted outputs such as tables, files, or links. They can be published via the Prefect SDK or API. They can also be rendered and managed in the Prefect UI, making it easy to track and monitor the objects that your flows produce and update over time. Published artifacts may be associated with a particular task run, flow run, or outside a flow run context. Artifacts provide a richer way to present information relative to typical logging practices-- including the ability to display tables, markdown, and links to external data.
## Artifacts Overview

Whether you're publishing links, markdown, or tables, artifacts provide a powerful and flexible way to showcase data within your workflow. With artifacts, you can easily manage and share information with your team, providing valuable insights and context.

Common use cases for artifacts include:

- Debugging: By publishing data that you care about in the UI, you can easily see when and where your results were written. If an artifact doesn't look the way you expect, you can find out which flow run last updated it, and you can click through a link in the artifact to the location where the artifact is stored (such as an S3 bucket).
- Data quality checks: Artifacts can be used to publish data quality checks from in-progress tasks. This can help ensure that data quality is maintained throughout the pipeline. During long-running tasks such as ML model training, you might use artifacts to publish performance graphs. This can help you visualize how well your models are performing and make adjustments as needed. You can also track the versions of these artifacts over time, making it easier to identify changes in your data.
- Documentation: Artifacts can be used to publish documentation and sample data to help you keep track of your work and share information with your colleagues. For instance, artifacts allow you to add a description to let your colleagues know why this piece of data is important. 

## Creating Artifacts

Creating artifacts allows you to publish data from task and flow runs or outside of a flow run context. Currently, you can render three artifact types: links, markdown, and tables.

!!! note "Artifacts render individually"
    Please note that every artifact created within a task will be displayed as an individual artifact in the Prefect UI. This means that each call to `create_link_artifact()` or `create_markdown_artifact()` generates a distinct artifact. 
    
    Unlike the `print()` command, where you can concatenate multiple calls to include additional items in a report, within a task, these commands must be used multiple times if necessary. 
    
    To create artifacts like reports or summaries using `create_markdown_artifact()`, compile your message string separately and then pass it to `create_markdown_artifact()` to create the complete artifact.

### Creating Link Artifacts

To create a link artifact, use the `create_link_artifact()` function.

```python
from prefect import flow, task
from prefect.artifacts import create_link_artifact

@task
def my_first_task():
        create_link_artifact(
            key="irregular-data",
            link="https://nyc3.digitaloceanspaces.com/my-bucket-name/highly_variable_data.csv",
            description="## Highly variable data",
        )

@task
def my_second_task():
        create_link_artifact(
            key="irregular-data",
            link="https://nyc3.digitaloceanspaces.com/my-bucket-name/low_pred_data.csv",
            description="# Low prediction accuracy",
        )

@flow
def my_flow():
    my_first_task()
    my_second_task()

if __name__ == "__main__":
    my_flow()
```

!!! tip Specify multiple artifacts with the same key for artifact lineage
    You can specify multiple artifacts with the same key to more easily track something very specific that you care about, such as irregularities in your data pipeline. 

After running the above flows, you can find your new artifacts in the Artifacts page of the UI. You can click into the "irregular data" artifact and see all versions of it, along with custom descriptions and links to the relevant data.

Here, you'll also be able to view information about your artifact such as its associated flow run or task run id, previous and future versions of the artifact (multiple artifacts can have the same key in order to show lineage), the data you've stored (in this case a markdown-rendered link), an optional markdown description, and when the artifact was created or updated.

To make the links more readable for you and your collaborators, you can pass in a `link_text` argument for your link artifacts:

```python
from prefect import flow
from prefect.artifacts import create_link_artifact

@flow
def my_flow():
    create_link_artifact(
        key="my-important-link",
        link="https://www.prefect.io/",
        link_text="Prefect",
    )

if __name__ == "__main__":
    my_flow()
```
In the above example, the `create_link_artifact` method is used within a flow to create a link artifact with a key of `my-important-link`. The `link` parameter is used to specify the external resource to be linked to, and `link_text` is used to specify the text to be displayed for the link. An optional `description` could also be added for context.
### Creating Markdown Artifacts

To create a markdown artifact, you can use the `create_markdown_artifact()` function.

```python
from prefect import flow, task
from prefect.artifacts import create_markdown_artifact

@task
def markdown_task():
    na_revenue = 500000
    markdown_report = f"""# Sales Report

## Summary

In the past quarter, our company saw a significant increase in sales, with a total revenue of $1,000,000. This represents a 20% increase over the same period last year.

## Sales by Region

| Region        | Revenue |
|:--------------|-------:|
| North America | ${na_revenue:,} |
| Europe        | $250,000 |
| Asia          | $150,000 |
| South America | $75,000 |
| Africa        | $25,000 |

## Top Products

1. Product A - $300,000 in revenue
2. Product B - $200,000 in revenue
3. Product C - $150,000 in revenue

## Conclusion

Overall, these results are very encouraging and demonstrate the success of our sales team in increasing revenue across all regions. However, we still have room for improvement and should focus on further increasing sales in the coming quarter.
"""
    create_markdown_artifact(
        key="gtm-report",
        markdown=markdown_report,
        description="Quarterly Sales Report",
    )

@flow()
def my_flow():
    markdown_task()
    

if __name__ == "__main__":
    my_flow()
```

After running the above flow, you should see your "gtm-report" artifact in the Artifacts page of the UI. As with all artifacts, you'll be able to view the associated flow run or task run id, previous and future versions of the artifact, your rendered markdown data, and your optional markdown description.

### Create Table Artifacts

You can create a table artifact by calling `create_table_artifact()`.

```python
from prefect.artifacts import create_table_artifact

def my_fn():
    highest_churn_possibility = [
       {'customer_id':'12345', 'name': 'John Smith', 'churn_probability': 0.85 }, 
       {'customer_id':'56789', 'name': 'Jane Jones', 'churn_probability': 0.65 } 
    ]

    create_table_artifact(
        key="personalized-reachout",
        table=highest_churn_possibility,
        description= "# Marvin, please reach out to these customers today!"
    )

if __name__ == "__main__":
    my_fn()
```

As you can see, you don't need to create an artifact in a flow run context. You can use it however you like and still get the benefits in the Prefect UI.

## Managing Artifacts

### Reading Artifacts

In the Prefect UI, you can view all of the latest versions of your artifacts and click into a specific artifact to see its lineage over time. Additionally, you can inspect all versions of an artifact with a given key by running:

<div class="terminal">
```bash
$ prefect artifact inspect <my-key>
```
</div>

or view all artifacts by running:

<div class="terminal">
```bash
$ prefect artifact ls
```
</div>

You can also use the [Prefect REST API](https://app.prefect.cloud/api/docs#tag/Artifacts/operation/read_artifacts_api_accounts__account_id__workspaces__workspace_id__artifacts_filter_post) to programmatically filter your results.

### Deleting Artifacts

You can delete an artifact directly from the Artifacts page in the UI. You can also use the CLI to delete specific artifacts with a given key or id:

<div class="terminal">
```bash
$ prefect artifact delete <my-key>
```
</div>

<div class="terminal">
```bash
$ prefect artifact delete --id <my-id>
```
</div>

Alternatively, you can delete artifacts using the [Prefect REST API](https://app.prefect.cloud/api/docs#tag/Artifacts/operation/delete_artifact_api_accounts__account_id__workspaces__workspace_id__artifacts__id__delete).

## Artifacts API

Prefect provides the [Prefect REST API](https://app.prefect.cloud/api/docs#tag/Artifacts) to allow you to create, read, and delete artifacts programmatically. With the Artifacts API, you can automate the creation and management of artifacts as part of your workflow.

For example, to read the 5 most recently created markdown, table, and link artifacts, you can do the following:

```python
import requests

PREFECT_API_URL="https://api.prefect.cloud/api/accounts/abc/workspaces/xyz"
PREFECT_API_KEY="pnu_ghijk"
data = {
    "sort": "CREATED_DESC",
    "limit": 5,
    "artifacts": {
        "key": {
            "exists_": True
        }
    }
}

headers = {"Authorization": f"Bearer {PREFECT_API_KEY}"}
endpoint = f"{PREFECT_API_URL}/artifacts/filter"

response = requests.post(endpoint, headers=headers, json=data)
assert response.status_code == 200
for artifact in response.json():
    print(artifact)
```

If we don't specify a key or that a key must exist, we will also return results (which are a type of key-less artifact).

See the rest of the [Prefect REST API documentation](https://app.prefect.cloud/api/docs#tag/Artifacts) on artifacts for more information!
