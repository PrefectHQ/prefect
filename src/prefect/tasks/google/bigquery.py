import json
import uuid

from google.oauth2.service_account import Credentials
from google.cloud import bigquery
from google.cloud.exceptions import NotFound
from typing import List

from prefect import context
from prefect.client import Secret
from prefect.core import Task
from prefect.utilities.tasks import defaults_from_attrs


class BigQueryTask(Task):
    """
    Query can be provided and mapped over via params.
    """

    def __init__(
        self,
        query: str = None,
        query_params: List[tuple] = None,  # 3-tuples
        project: str = None,
        location: str = "US",
        dry_run_max_bytes: int = None,
        credentials_secret: str = None,
        dataset_dest: str = None,
        table_dest: str = None,
        job_config: dict = None,
        **kwargs
    ):
        self.query = query
        self.query_params = query_params
        self.project = project
        self.location = location
        self.dry_run_max_bytes = dry_run_max_bytes
        self.credentials_secret = credentials_secret or "GOOGLE_APPLICATION_CREDENTIALS"
        self.dataset_dest = dataset_dest
        self.table_dest = table_dest
        self.job_config = job_config or {}
        super().__init__(**kwargs)

    @defaults_from_attrs(
        "query",
        "query_params",
        "project",
        "location",
        "dry_run_max_bytes",
        "credentials_secret",
        "dataset_dest",
        "table_dest",
        "job_config",
    )
    def run(
        self,
        query: str = None,
        query_params: List[tuple] = None,  # 3-tuples
        project: str = None,
        location: str = "US",
        dry_run_max_bytes: int = None,
        credentials_secret: str = None,
        dataset_dest: str = None,
        table_dest: str = None,
        job_config: dict = None,
    ):
        """
        Run method for this Task.  Invoked by _calling_ this Task within a Flow context, after initialization.
        """
        ## check for any argument inconsistencies
        if query is None:
            raise ValueError("No query not provided.")
        if sum([dataset_dest is None, table_dest is None]) == 1:
            raise ValueError(
                "Both `dataset_dest` and `table_dest` must be provided if writing to a destination table."
            )

        ## create client
        creds = json.loads(Secret(credentials_secret).get())
        credentials = Credentials.from_service_account_info(creds)
        project = project or credentials.project_id
        client = bigquery.Client(project=project, credentials=credentials)

        ## setup jobconfig
        job_config = bigquery.QueryJobConfig(**job_config)

        ## perform dry_run if requested
        if dry_run_max_bytes is not None:
            old_info = dict(
                dry_run=job_config.dry_run, use_query_cache=job_config.use_query_cache
            )
            job_config.dry_run = True
            job_config.use_query_cache = False
            query_job = client.query(query, location=location, job_config=job_config)
            if query_job.total_bytes_processed > dry_run_max_bytes:
                raise ValueError(
                    "Query will process {0} bytes which is above the set maximum of {1} for this task.".format(
                        query_job.total_bytes_processed, dry_run_max_bytes
                    )
                )
            job_config.dry_run = old_info["dry_run"]
            job_config.use_query_cache = old_info["use_query_cache"]

        ## if writing to a destination table
        if dataset_dest is not None:
            table_ref = client.dataset(dataset_dest).table(table_dest)
            job_config.destination = table_ref

        query_job = client.query(query, location=location, job_config=job_config)
        return query_job.result()
