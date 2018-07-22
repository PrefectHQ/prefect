from prefect.engine.signals import PrefectStateSignal


def test_exceptions_are_displayed_with_messages():
    err = PrefectStateSignal("you did something incorrectly")
    assert "you did something incorrectly" in repr(err)
    assert "PrefectStateSignal" in repr(err)

