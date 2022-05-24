from prefect.testing.cli import invoke_and_assert


class MockClient:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *args, **kwargs):
        pass

    async def delete_flow_run_by_id(self, *args):
        pass


def get_mock_client(*args, **kwargs):
    """Used to patch `get_client` calls"""
    return MockClient()


def test_delete_flow_run_fails_correctly():
    UUID_404_input = "ccb86ed0-e824-4d8b-b825-880401320e41"
    UUID_404_output = "Flow run UUID('ccb86ed0-e824-4d8b-b825-880401320e41') not found!"
    invoke_and_assert(
        command=["flow-run", "delete", UUID_404_input],
        expected_output=UUID_404_output,
        expected_code=1,
    )


def test_delete_flow_run_succeeds(monkeypatch):
    monkeypatch.setattr("prefect.cli.flow_run.get_client", get_mock_client)
    good_input = "a9ea6c01-d2ee-401d-8716-3f0500caa1b3"
    good_output = (
        "Successfully deleted flow run UUID('a9ea6c01-d2ee-401d-8716-3f0500caa1b3')."
    )

    invoke_and_assert(
        command=["flow-run", "delete", good_input],
        expected_output=good_output,
        expected_code=0,
    )
