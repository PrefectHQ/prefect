---
title: GCP
---

# Google Cloud Platform

Tasks which interface with various components of Google Cloud Platform.

Tasks in this collection require a Prefect Secret called `"GOOGLE_APPLICATION_CREDENTIALS"` which contains
valid Google Credentials in a JSON document.

## Google Cloud Storage

### GCSDownload <Badge text="task"/>

Task template for downloading data from Google Cloud Storage as a string.

[API Reference](/api/unreleased/tasks/google.html#prefect-tasks-google-storage-gcsdownloadtask)


### GCSUpload <Badge text="task"/>

Task template for uploading data to Google Cloud Storage as a string.

[API Reference](/api/unreleased/tasks/google.html#prefect-tasks-google-storage-gcsuploadtask)


## BigQuery

### BigQueryTask <Badge text="task"/>

Task for executing queries against a Google BigQuery table and (optionally) returning the results.

[API Reference](/api/unreleased/tasks/google.html#prefect-tasks-google-bigquery-bigquerytask)


### BigQueryStreamingInsert <Badge text="task"/>

Task for insert records in a Google BigQuery table via [the streaming API](https://cloud.google.com/bigquery/streaming-data-into-bigquery).

[API Reference](/api/unreleased/tasks/google.html#prefect-tasks-google-bigquery-bigquerystreaminginserttask)

### CreateBigQueryTable <Badge text="task"/>

Task for creating Google BigQuery tables.

[API Reference](/api/unreleased/tasks/google.html#prefect-tasks-google-bigquery-createbigquerytable)
