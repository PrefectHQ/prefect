"""
Tasks which interface with various components of Google Cloud Storage.

Note that these tasks allow for a wide range of custom usage patterns, such as:

- Initialize a task with all settings for one time use
- Initialize a "template" task with default settings and override as needed
- Create a custom Task which inherits from a Prefect Task and utilizes the Prefect boilerplate
"""
try:
    import prefect.tasks.google.storage

    from prefect.tasks.google.storage import GCSDownload, GCSUpload
    from prefect.tasks.google.bigquery import BigQueryTask, BigQueryStreamingInsert
except ImportError:
    raise ImportError(
        'Using `prefect.tasks.google` requires Prefect to be installed with the "google" extra.'
    )
