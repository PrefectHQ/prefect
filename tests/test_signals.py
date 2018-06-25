from prefect.signals import PrefectStateException


def test_exceptions_are_displayed_with_messages():
    err = PrefectStateException("you did something incorrectly")
    assert "you did something incorrectly" in repr(err)
    assert "PrefectStateException" in repr(err)
