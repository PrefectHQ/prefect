"""
Tasks that interface with various components of Google Cloud Platform.

Tasks in this collection require a Prefect Secret called `"GOOGLE_APPLICATION_CREDENTIALS"` that contains
valid Google Credentials in a JSON document.

Note that these tasks allow for a wide range of custom usage patterns, such as:

- Initialize a task with all settings for one time use
- Initialize a "template" task with default settings and override as needed
- Create a custom Task that inherits from a Prefect Task and utilizes the Prefect boilerplate
"""
try:

    from prefect.tasks.google.storage import GCSDownload, GCSUpload, GCSCopy
    from prefect.tasks.google.bigquery import (
        BigQueryTask,
        BigQueryStreamingInsert,
        CreateBigQueryTable,
    )
except ImportError:
    raise ImportError(
        'Using `prefect.tasks.google` requires Prefect to be installed with the "google" extra.'
    )
