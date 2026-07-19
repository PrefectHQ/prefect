import attr
from openlineage.client.facet import BaseFacet


@attr.define
class PrefectDeploymentRunFacet(BaseFacet):
    deploymentId: str
    created: str
    updated: str
    name: str

    def __init__(self, deploymentId, created, updated, name):
        super().__init__()
        self.deploymentId = deploymentId
        self.created = created
        self.updated = updated
        self.name = name

    @staticmethod
    def _get_schema() -> str:
        """Return the schema URL for the PrefectDeploymentRunFacet."""
        return "https://raw.githubusercontent.com/PrefectHQ/prefect/main/src/integrations/prefect-openlineage/prefect_openlineage/facets/PrefectDeploymentRunFacet.json"

    @staticmethod
    def _get_producer() -> str:
        """Return the producer URL for the PrefectDeploymentRunFacet."""
        return (
            "https://github.com/prefectHQ/prefect/src/integrations/prefect-openlineage"
        )
