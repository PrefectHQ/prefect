"""
Require a service account.  Recommend a defaultproject.
Save blob in secret.  Default name.
"""
import prefect.tasks.google.storage

from prefect.tasks.google.storage import GoogleCloudStorageTask
