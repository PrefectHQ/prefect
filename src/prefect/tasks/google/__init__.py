"""
Tasks that interface with various components of Google Cloud Platform.

Note that these tasks allow for a wide range of custom usage patterns, such as:

- Initialize a task with all settings for one time use
- Initialize a "template" task with default settings and override as needed
- Create a custom Task that inherits from a Prefect Task and utilizes the Prefect boilerplate
"""
import warnings

warnings.warn(
    "DEPRECATED: prefect.tasks.google is deprecated, use prefect.tasks.gcp instead",
    UserWarning,
    stacklevel=2,
)

from prefect.tasks.gcp.storage import GCSDownload, GCSUpload, GCSCopy
from prefect.tasks.gcp.bigquery import (
    BigQueryTask,
    BigQueryLoadGoogleCloudStorage,
    BigQueryStreamingInsert,
    CreateBigQueryTable,
)
