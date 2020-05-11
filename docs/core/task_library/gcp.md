---
title: GCP
---

# Google Cloud Platform

Tasks that interface with various components of Google Cloud Platform.

## Google Cloud Storage

### GCSDownload <Badge text="task"/>

Task template for downloading data from Google Cloud Storage as a string.

[API Reference](/api/latest/tasks/gcp.html#prefect-tasks-google-storage-gcsdownload)

### GCSUpload <Badge text="task"/>

Task template for uploading data to Google Cloud Storage as a string.

[API Reference](/api/latest/tasks/gcp.html#prefect-tasks-google-storage-gcsupload)

### GCSCopy <Badge text="task"/>

Task template for copying data from one Google Cloud Storage blob to another.

[API Reference](/api/latest/tasks/gcp.html#prefect-tasks-google-storage-gcscopy)

## BigQuery

### BigQueryTask <Badge text="task"/>

Task for executing queries against a Google BigQuery table and (optionally) returning the results.

[API Reference](/api/latest/tasks/gcp.html#prefect-tasks-google-bigquery-bigquery)

### BigQueryStreamingInsert <Badge text="task"/>

Task for insert records in a Google BigQuery table via [the streaming API](https://cloud.google.com/bigquery/streaming-data-into-bigquery).

[API Reference](/api/latest/tasks/gcp.html#prefect-tasks-google-bigquery-bigquerystreaminginsert)

### CreateBigQueryTable <Badge text="task"/>

Task for creating Google BigQuery tables.

[API Reference](/api/latest/tasks/gcp.html#prefect-tasks-google-bigquery-createbigquerytable)

### BigQueryLoadGoogleCloudStorage <Badge text="task"/>

Task for [loading data in a Google BigQuery table](https://cloud.google.com/bigquery/docs/loading-data) via [the Python client](https://googleapis.dev/python/bigquery/latest/generated/google.cloud.bigquery.client.Client.html#google.cloud.bigquery.client.Client.load_table_from_uri).

[API Reference](/api/latest/tasks/gcp.html#prefect-tasks-google-bigquery-bigqueryloadgooglecloudstorage)

### BigQueryLoadFile <Badge text="task"/>

Task for [loading data in a Google BigQuery table](https://cloud.google.com/bigquery/docs/loading-data) via [the Python client](https://googleapis.dev/python/bigquery/latest/generated/google.cloud.bigquery.client.Client.html#google.cloud.bigquery.client.Client.load_table_from_file).

[API Reference](/api/latest/tasks/gcp.html#prefect-tasks-google-bigquery-bigqueryloadfile)