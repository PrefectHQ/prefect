from typing import TYPE_CHECKING, overload
from prefect.cli.transfer._migratable_resources.base import (
    MigratableProtocol,
    MigratableType,
)


if TYPE_CHECKING:
    from prefect.client.schemas.objects import (
        BlockDocument,
        BlockSchema,
        BlockType,
        Flow,
        WorkPool,
        WorkQueue,
        Variable,
    )
    from prefect.client.schemas.responses import (
        DeploymentResponse,
        GlobalConcurrencyLimitResponse,
    )
    from prefect.events.schemas.automations import Automation

    from prefect.cli.transfer._migratable_resources.blocks import (
        MigratableBlockDocument,
        MigratableBlockSchema,
        MigratableBlockType,
    )
    from prefect.cli.transfer._migratable_resources.concurrency_limits import (
        MigratableGlobalConcurrencyLimit,
    )
    from prefect.cli.transfer._migratable_resources.deployments import (
        MigratableDeployment,
    )
    from prefect.cli.transfer._migratable_resources.flows import MigratableFlow
    from prefect.cli.transfer._migratable_resources.variables import MigratableVariable
    from prefect.cli.transfer._migratable_resources.work_pools import MigratableWorkPool
    from prefect.cli.transfer._migratable_resources.work_queues import (
        MigratableWorkQueue,
    )
    from prefect.cli.transfer._migratable_resources.automations import (
        MigratableAutomation,
    )


@overload
async def construct_migratable_resource(obj: "WorkPool") -> "MigratableWorkPool": ...
@overload
async def construct_migratable_resource(obj: "WorkQueue") -> "MigratableWorkQueue": ...
@overload
async def construct_migratable_resource(
    obj: "DeploymentResponse",
) -> "MigratableDeployment": ...
@overload
async def construct_migratable_resource(obj: "Flow") -> "MigratableFlow": ...
@overload
async def construct_migratable_resource(obj: "BlockType") -> "MigratableBlockType": ...
@overload
async def construct_migratable_resource(
    obj: "BlockSchema",
) -> "MigratableBlockSchema": ...
@overload
async def construct_migratable_resource(
    obj: "BlockDocument",
) -> "MigratableBlockDocument": ...
@overload
async def construct_migratable_resource(
    obj: "Automation",
) -> "MigratableAutomation": ...
@overload
async def construct_migratable_resource(
    obj: "GlobalConcurrencyLimitResponse",
) -> "MigratableGlobalConcurrencyLimit": ...
@overload
async def construct_migratable_resource(obj: "Variable") -> "MigratableVariable": ...


async def construct_migratable_resource(
    obj: MigratableType,
) -> MigratableProtocol:
    from prefect.client.schemas.objects import (
        BlockDocument,
        BlockSchema,
        BlockType,
        Flow,
        WorkPool,
        WorkQueue,
    )
    from prefect.client.schemas.responses import (
        DeploymentResponse,
        GlobalConcurrencyLimitResponse,
    )
    from prefect.events.schemas.automations import Automation

    from prefect.cli.transfer._migratable_resources.blocks import (
        MigratableBlockDocument,
        MigratableBlockSchema,
        MigratableBlockType,
    )
    from prefect.cli.transfer._migratable_resources.concurrency_limits import (
        MigratableGlobalConcurrencyLimit,
    )
    from prefect.cli.transfer._migratable_resources.deployments import (
        MigratableDeployment,
    )
    from prefect.cli.transfer._migratable_resources.flows import MigratableFlow
    from prefect.cli.transfer._migratable_resources.variables import MigratableVariable
    from prefect.cli.transfer._migratable_resources.work_pools import MigratableWorkPool
    from prefect.cli.transfer._migratable_resources.work_queues import (
        MigratableWorkQueue,
    )
    from prefect.cli.transfer._migratable_resources.automations import (
        MigratableAutomation,
    )

    if isinstance(obj, WorkPool):
        return await MigratableWorkPool.construct(obj)
    elif isinstance(obj, WorkQueue):
        return await MigratableWorkQueue.construct(obj)
    elif isinstance(obj, DeploymentResponse):
        return await MigratableDeployment.construct(obj)
    elif isinstance(obj, Flow):
        return await MigratableFlow.construct(obj)
    elif isinstance(obj, BlockType):
        return await MigratableBlockType.construct(obj)
    elif isinstance(obj, BlockSchema):
        return await MigratableBlockSchema.construct(obj)
    elif isinstance(obj, BlockDocument):
        return await MigratableBlockDocument.construct(obj)
    elif isinstance(obj, Automation):
        return await MigratableAutomation.construct(obj)
    elif isinstance(obj, GlobalConcurrencyLimitResponse):
        return await MigratableGlobalConcurrencyLimit.construct(obj)
    else:
        return await MigratableVariable.construct(obj)
