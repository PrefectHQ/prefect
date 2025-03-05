import abc
import asyncio
from typing import Any, Optional

from prefect_kubernetes_integration_tests.utils import k8s
from rich.console import Console

from prefect.client.schemas.objects import FlowRun
from prefect.states import StateType

console = Console()


class BaseScenario(abc.ABC):
    """Base class for all test scenarios."""

    name: str = "base"
    description: str = "Base scenario"
    expected_state: Optional[StateType] = None
    work_pool_name: str = "k8s-test"
    cluster_name: str = "prefect-test"

    flow_source: str
    flow_entrypoint: str
    flow_name: str

    def __init__(self, **kwargs: Any) -> None:
        """Initialize scenario with optional overrides."""
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)

        self.flow_run: Optional[FlowRun] = None
        self.job_name: Optional[str] = None
        self.pod_name: Optional[str] = None

    def setup(self) -> None:
        """Setup requirements for the scenario."""
        k8s.ensure_kind_cluster(self.cluster_name)

    @abc.abstractmethod
    async def execute(self) -> bool:
        """Execute the scenario and return if it passed."""
        pass

    def cleanup(self) -> None:
        """Clean up resources after the scenario."""
        pass

    def run(self) -> bool:
        """Run the complete scenario and return whether it passed."""
        console.print(f"[bold]Running scenario: {self.name}[/bold]")
        console.print(f"Description: {self.description}")

        try:
            self.setup()
            return asyncio.run(self.execute())
        finally:
            self.cleanup()
