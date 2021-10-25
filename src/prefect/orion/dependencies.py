from dependency_injector import containers, providers
from prefect.orion.utilities.database import Base


class DatabaseContainer(containers.DeclarativeContainer):
    config = providers.Configuration()

    base_model = providers.Object(Base)


from dependency_injector.wiring import Provide, inject

# import sys


@inject
def get_base_model(base_model=Provide[DatabaseContainer.base_model]):
    return base_model


# breakpoint()
# container = DatabaseContainer()
# container.bootstrap()
# from dependency_injector.wiring import register_loader_containers

# register_loader_containers(container)

# container.wire(modules=[sys.modules[__name__]])
Base = get_base_model()
