import prefect
from prefect import task, Flow


@task
def redacted_log():
    logger = prefect.context.get("logger")
    logger.info("SSN: 123-45-6789")


@task
def redacted_exception():
    1 / 0


def build_flow():
    with Flow("Redacted") as flow:
        redacted_log()
        redacted_exception()
    return flow


if __name__ == "__main__":
    flow = build_flow()
    # flow.run()
    flow.register(project_name="local-only")
