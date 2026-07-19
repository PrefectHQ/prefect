"""
Unit tests for prefect_openlineage facets module.

Tests cover custom Prefect deployment facet definition and properties.
"""

from prefect_openlineage.facets.run_facets import PrefectDeploymentRunFacet

# ========== Tests for PrefectDeploymentRunFacet initialization ==========


def test_prefect_deployment_run_facet_initialization():
    """Test creation of PrefectDeploymentRunFacet with valid parameters."""
    facet = PrefectDeploymentRunFacet(
        deploymentId="dep-123",
        created="2026-07-05T08:05:01.001Z",
        updated="2026-07-05T08:06:02.100Z",
        name="test_deploy",
    )

    assert facet.deploymentId == "dep-123"
    assert facet.created == "2026-07-05T08:05:01.001Z"
    assert facet.updated == "2026-07-05T08:06:02.100Z"
    assert facet.name == "test_deploy"


def test_prefect_deployment_run_facet_attributes():
    """Test that all attributes are correctly stored."""
    deploymentId = "dep-456"
    created = "2026-07-04T10:00:00Z"
    updated = "2026-07-05T15:30:00Z"
    name = "my_deployment"

    facet = PrefectDeploymentRunFacet(
        deploymentId=deploymentId, created=created, updated=updated, name=name
    )

    assert facet.deploymentId == deploymentId
    assert facet.created == created
    assert facet.updated == updated
    assert facet.name == name


def test_prefect_deployment_run_facet_schema():
    """Test that facet provides a schema."""
    facet = PrefectDeploymentRunFacet(
        deploymentId="dep-123",
        created="2026-07-05T08:05:01.001Z",
        updated="2026-07-05T08:06:02.100Z",
        name="test_deploy",
    )

    schema = facet._get_schema()
    assert isinstance(schema, str)
    assert len(schema) > 0


def test_prefect_deployment_run_facet_producer():
    """Test that facet provides a producer."""
    facet = PrefectDeploymentRunFacet(
        deploymentId="dep-123",
        created="2026-07-05T08:05:01.001Z",
        updated="2026-07-05T08:06:02.100Z",
        name="test_deploy",
    )

    producer = facet._get_producer()
    assert isinstance(producer, str)
    assert "prefect" in producer.lower()
    assert "github" in producer.lower()


def test_prefect_deployment_run_facet_schema_url():
    """Test that schema URL is correctly formatted."""
    facet = PrefectDeploymentRunFacet(
        deploymentId="dep-123",
        created="2026-07-05T08:05:01.001Z",
        updated="2026-07-05T08:06:02.100Z",
        name="test_deploy",
    )

    schema = facet._get_schema()
    assert schema.startswith("https://")
    assert "openlineage" in schema.lower()


def test_prefect_deployment_run_facet_producer_url():
    """Test that producer URL is correctly formatted."""
    facet = PrefectDeploymentRunFacet(
        deploymentId="dep-123",
        created="2026-07-05T08:05:01.001Z",
        updated="2026-07-05T08:06:02.100Z",
        name="test_deploy",
    )

    producer = facet._get_producer()
    assert producer.startswith("https://")


def test_prefect_deployment_run_facet_empty_deployment_id():
    """Test facet creation with empty deployment ID."""
    facet = PrefectDeploymentRunFacet(
        deploymentId="",
        created="2026-07-05T08:05:01.001Z",
        updated="2026-07-05T08:06:02.100Z",
        name="test_deploy",
    )

    assert facet.deploymentId == ""


def test_prefect_deployment_run_facet_none_values():
    """Test facet creation with None values (if allowed)."""
    facet = PrefectDeploymentRunFacet(
        deploymentId="dep-123", created=None, updated=None, name="test_deploy"
    )

    assert facet.deploymentId == "dep-123"
    assert facet.created is None
    assert facet.updated is None
    assert facet.name == "test_deploy"


def test_prefect_deployment_run_facet_is_base_facet():
    """Test that PrefectDeploymentRunFacet is a BaseFacet."""
    from openlineage.client.facet import BaseFacet

    facet = PrefectDeploymentRunFacet(
        deploymentId="dep-123",
        created="2026-07-05T08:05:01.001Z",
        updated="2026-07-05T08:06:02.100Z",
        name="test_deploy",
    )

    assert isinstance(facet, BaseFacet)


def test_prefect_deployment_run_facet_multiple_instances():
    """Test creating multiple independent facet instances."""
    facet1 = PrefectDeploymentRunFacet(
        deploymentId="dep-123",
        created="2026-07-05T08:05:01.001Z",
        updated="2026-07-05T08:06:02.100Z",
        name="deploy_1",
    )

    facet2 = PrefectDeploymentRunFacet(
        deploymentId="dep-456",
        created="2026-07-06T09:00:00.000Z",
        updated="2026-07-06T10:00:00.000Z",
        name="deploy_2",
    )

    assert facet1.deploymentId != facet2.deploymentId
    assert facet1.name != facet2.name
    assert facet1.created != facet2.created


def test_prefect_deployment_run_facet_special_characters():
    """Test facet creation with special characters in values."""
    facet = PrefectDeploymentRunFacet(
        deploymentId="dep-123-@#$%",
        created="2026-07-05T08:05:01.001Z",
        updated="2026-07-05T08:06:02.100Z",
        name="test_deploy-@#$%",
    )

    assert "@#$%" in facet.deploymentId
    assert "@#$%" in facet.name


def test_prefect_deployment_run_facet_long_strings():
    """Test facet creation with very long string values."""
    long_id = "dep-" + "x" * 1000
    long_name = "deploy_" + "y" * 1000

    facet = PrefectDeploymentRunFacet(
        deploymentId=long_id,
        created="2026-07-05T08:05:01.001Z",
        updated="2026-07-05T08:06:02.100Z",
        name=long_name,
    )

    assert facet.deploymentId == long_id
    assert facet.name == long_name
