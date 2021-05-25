import pytest

from prefect.tasks.gcp.secretmanager import GCPSecret


class TestGCPSecretsTask:
    def test_initialization(self):
        task = GCPSecret("test")
        assert task

    def test_initialization_passes_to_task_constructor(self):
        task = GCPSecret(name="test", tags=["GCP"])
        assert task.name == "test"
        assert task.tags == {"GCP"}

    def test_raises_if_project_not_eventually_provided(self):
        task = GCPSecret(secret_id="sherbet-lemon")

        with pytest.raises(ValueError, match="project ID"):
            task.run()

    def test_raises_if_secret_not_eventually_provided(self):
        task = GCPSecret(project_id="majestic-meerkat")

        with pytest.raises(ValueError, match="secret ID"):
            task.run()
