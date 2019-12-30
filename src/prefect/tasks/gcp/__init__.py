"""
Tasks that interface with various components of Google Cloud Platform.

Note that these tasks allow for a wide range of custom usage patterns, such as:

- Initialize a task with all settings for one time use
- Initialize a "template" task with default settings and override as needed
- Create a custom Task that inherits from a Prefect Task and utilizes the Prefect boilerplate
"""
try:

    from prefect.tasks.gcp.storage import GCSDownload, GCSUpload, GCSCopy
    from prefect.tasks.gcp.bigquery import (
        BigQueryTask,
        BigQueryLoadGoogleCloudStorage,
        BigQueryStreamingInsert,
        CreateBigQueryTable,
    )
except ImportError:
    raise ImportError(
        'Using `prefect.tasks.gcp` requires Prefect to be installed with the "gcp" extra.'
    )
