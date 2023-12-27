"""
The dynamic service loader.
"""

import importlib
from typing import List, Optional

from prefect.logging import get_logger
from prefect.server.services.loop_service import LoopService

logger = get_logger("server")


def string_to_loop_service(service_path: str) -> Optional[LoopService]:
    """
    Given a string representing a LoopService subclass, import the class and return an
    instance of it.

    Args:
        - service_path (str): the path to the LoopService subclass

    Returns:
        - LoopService: an instance of the LoopService subclass
    """
    module_name, class_name = service_path.strip(" ").rsplit(".", 1)
    try:
        module = importlib.import_module(module_name)
        instance = getattr(module, class_name)()
        return instance
    except:  # noqa: E722
        logger.error(f"Failed to initialize the instance of the service {service_path}")
        return None


def string_to_loop_services(services_path: str) -> List[LoopService]:
    """
    Converts a string of service paths into a list of LoopService objects.
    This only return the services that implement the LoopService interface. Service that don't implement it are excluded from the list

    Args:
        services_path (str): A string containing multiple service paths separated by a ',' delimiter.

    Returns:
        List[LoopService]: A list of LoopService objects.

    """
    services = []
    for service_path in services_path.split(","):
        service = string_to_loop_service(service_path=service_path)
        if not service:
            continue

        if not isinstance(service, LoopService):
            logger.error(f"Service {service_path} is not a LoopService")
            continue

        services.append(service)

    return services
