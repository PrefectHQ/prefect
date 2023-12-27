"""
The dynamic service loader.
"""

import importlib
from typing import List

from prefect.server.services.loop_service import LoopService


def string_to_loop_service(service_path: str) -> LoopService:
    """
    Given a string representing a LoopService subclass, import the class and return an
    instance of it.

    Args:
        - service_path (str): the path to the LoopService subclass

    Returns:
        - LoopService: an instance of the LoopService subclass
    """
    module_name, class_name = service_path.strip(" ").rsplit(".", 1)
    module = importlib.import_module(module_name)
    return getattr(module, class_name)()


def string_to_loop_services(services_path: str) -> List[LoopService]:
    """
    Converts a string of service paths into a list of LoopService objects.

    Args:
        services_path (str): A string containing multiple service paths separated by a ',' delimiter.

    Returns:
        List[LoopService]: A list of LoopService objects.

    """
    return [
        string_to_loop_service(service_path=service_path)
        for service_path in services_path.split(",")
    ]
