from prefect_dbt.cloud.jobs import trigger_dbt_cloud_job_run_and_wait_for_completion

from prefect.deployments.runner import EntrypointType

if __name__ == "__main__":
    trigger_dbt_cloud_job_run_and_wait_for_completion.deploy(
        name="test-deploy-from-module",
        work_pool_name="olympic",
        entrypoint_type=EntrypointType.MODULE_PATH,
    )
