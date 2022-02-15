import pytest

from src.prefect.tasks.aws.parameter_store_manager import AWSParametersManager

pytest.importorskip("boto3")


class TestAWSParameterManager:
    def test_initialization(self):
        AWSParametersManager("test")

    def test_initialization_passes_to_task_constructor(self):
        task = AWSParametersManager(name="test", tags=["AWS"])
        assert task.name == "test"
        assert task.tags == {"AWS"}

    def test_raises_if_parameter_name_not_eventually_provided(self):
        task = AWSParametersManager()

        with pytest.raises(ValueError, match="parameter"):
            task.run()
