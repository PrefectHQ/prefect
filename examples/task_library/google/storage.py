"""
This example illustrates the use of Prefect's Google Cloud Storage tasks.

Each task is instantiated as a template in order to demonstrate how arguments can be
passed either at initialization or when building the flow.
"""
import json

from prefect import Flow
from prefect.tasks.gcp.storage import GCSCopy, GCSDownload, GCSUpload

BUCKET = "gcs-bucket"
BLOB = "path/to/blob"
DATA = json.dumps([1, 2, 3])

# create task templates
upload_template = GCSUpload(bucket=BUCKET, blob=BLOB, credentials_secret="GCS_CREDS")
download_template = GCSDownload(
    bucket=BUCKET, blob=BLOB, credentials_secret="GCS_CREDS"
)
copy_template = GCSCopy(
    source_bucket=BUCKET,
    source_blob=BLOB,
    dest_bucket=BUCKET,
    credentials_secret="GCS_CREDS",
)

with Flow("GCS Example") as flow:
    # upload with default settings
    upl = upload_template(data=DATA)
    dwl = download_template(upstream_tasks=[upl])

    # upload to new blob and download it
    upl_new = upload_template(data=DATA, blob="another/blob")
    dwl_new = download_template(blob=upl_new)

    # copy the default blob twice
    cp_1 = copy_template(dest_blob="yet/another/blob", upstream_tasks=[upl])
    cp_2 = copy_template(source_blob=cp_1, dest_blob="one/last/blob")

    # download the new blob
    dwl_new = download_template(blob=cp_2)
