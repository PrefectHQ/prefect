from unittest.mock import MagicMock
import prefect
from prefect import context
from prefect.tasks.asana import OpenAsanaToDo
from prefect.utilities.configuration import set_temporary_config
import pytest

pytest.importorskip("asana")


class TestInitialization:
    def test_inits_with_no_args(self):
        t = OpenAsanaToDo()
        assert t

    def test_kwargs_get_passed_to_task_init(self):
        t = OpenAsanaToDo(project="project", name="test", notes="foo", token="1234a")
        assert t.project == "project"
        assert t.notes == "foo"

    def test_raises_if_token_not_provided(self):
        task = OpenAsanaToDo(project="12345", name="test", notes="foo")
        with pytest.raises(ValueError, match="token"):
            task.run()

    def test_raises_if_project_name_not_provided(self, monkeypatch):
        task = OpenAsanaToDo(name="test", notes="foo", token="1234a")
        client = MagicMock()
        asana = MagicMock(client=client)
        monkeypatch.setattr("prefect.tasks.asana.asana_task.asana", asana)
        with pytest.raises(ValueError, match="project"):
            task.run()
