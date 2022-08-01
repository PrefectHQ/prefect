"""
prefect config set PREFECT_LOGGING_LEVEL=DEBUG
"""
from prefect import flow, get_run_logger

purpose = """
The purpose of this flow is make sure that all logs are working
as expected. 

Expected behavior: there should be logs for:
- info
- debug
- warning (2x)
- error
- debug
- critical
- info (3x)
"""


@flow
def log_levels_flow():
    logger = get_run_logger()
    logger.info(purpose)

    logger.info("Preparing for warp 9")
    logger.debug("Warp drive temperature: 200°C")
    logger.warning("Enemy vessel detected")
    logger.warning("Incoming photon torpedo")
    logger.error("Evasive maneuvers failed!")
    logger.debug("Warp drive temperature: 535°C")
    logger.critical("Fire detected in engine room!")
    logger.info("Warp drive engaged")
    logger.info("Traveled 1,442,442 km at warp 9")
    logger.info("Warp drive disengaged")


if __name__ == "__main__":
    log_levels_flow()
