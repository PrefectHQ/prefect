from prefect.hello_world import hello_flow


def test_hello_flow_defaults(caplog):
    result = hello_flow.run()
    assert result.is_successful()
    assert "Hello World" in caplog.text


def test_hello_flow_with_name(caplog):
    result = hello_flow.run(name="marvin")
    assert result.is_successful()
    assert "Hello Marvin" in caplog.text
