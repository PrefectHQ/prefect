from prefect.cli._types import PrefectTyper
from prefect.cli.root import app
from prefect.testing.cli import invoke_and_assert


class TestPrefectTyper:
    singular_subcommand = PrefectTyper(name="singular-subcommand")
    pluralized_subcommand = PrefectTyper(name="pluralized-subcommand")
    app.add_typer(singular_subcommand)
    app.add_typer(
        pluralized_subcommand, pluralization_string="pluralized-subcommands"
    )

    def test_pluralized_subcommands_have_multiple_valid_invocations(self):
        invoke_and_assert(["pluralized-subcommand", "--help"], expected_code=0)
        invoke_and_assert(["pluralized-subcommands", "--help"], expected_code=0)

    def test_unpluralized_subcommands_have_one_invocation(self):
        invoke_and_assert(["singular-subcommand", "--help"], expected_code=0)
        invoke_and_assert(["singular-subcommands", "--help"], expected_code=2)

        app.add_typer(
            self.singular_subcommand, pluralization_string="singular-subcommands"
        )
        invoke_and_assert(["singular-subcommands", "--help"], expected_code=0)

    def test_registering_a_command_is_propogated_properly(self):
        @self.pluralized_subcommand.command()
        def exists():
            print("hello")

        invoke_and_assert(
            ["pluralized-subcommand", "exists"],
            expected_output_contains="hello",
            expected_code=0,
        )
        invoke_and_assert(
            ["pluralized-subcommands", "exists"],
            expected_output_contains="hello",
            expected_code=0,
        )
