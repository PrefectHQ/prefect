import pytest

from prefect.tasks.sendgrid import SendEmail


class TestInitialization:
    def test_inits_with_no_args(self):
        t = SendEmail()
        assert t

    def test_kwargs_get_passed_to_task_init(self):
        t = SendEmail(name="bob", checkpoint=True, tags=["foo"])
        assert t.name == "bob"
        assert t.checkpoint is True
        assert t.tags == {"foo"}

    @pytest.mark.parametrize(
        "attr",
        [
            "from_email",
            "to_emails",
            "subject",
            "html_content",
            "attachment_file_path",
            "sendgrid_secret",
        ],
    )
    def test_initializes_attr_from_kwargs(self, attr):
        task = SendEmail(**{attr: "my-value"})
        assert getattr(task, attr) == "my-value"
