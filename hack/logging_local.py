import prefect
from prefect import task, Flow


@task
def local_log_1():
    logger = prefect.context.get("logger")
    logger.info("SSN: 123-45-6789, Phone: 555-555-1212")


def register():
    with Flow("local-logging") as flow:
        local_log_1()

    flow.register(project_name="local-only")
    # flow.run()


if __name__ == "__main__":
    register()
