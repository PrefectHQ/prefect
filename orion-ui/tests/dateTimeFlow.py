from prefect import flow, task, get_run_logger
import datetime

@task
def log_datetime(datetime):
    logger = get_run_logger()
    logger.log(20, msg=f"Date Time {datetime}")


@flow(name="Date Flow")
def datetime_flow(datetime: datetime.datetime = datetime.datetime.today()):
    if(datetime):
        log_datetime(datetime)
        print(f"DT {datetime}!")