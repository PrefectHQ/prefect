import argparse

from prefect_kubernetes_integration_tests.scenarios.base import BaseScenario
from prefect_kubernetes_integration_tests.scenarios.eviction import PodEvictionScenario
from rich.console import Console

from prefect.cli._utilities import exit_with_error

console = Console()

SCENARIOS: dict[str, type[BaseScenario]] = {
    "eviction": PodEvictionScenario,
    # Add more scenarios here
}


def main():
    parser = argparse.ArgumentParser(description="Run Kubernetes integration tests")
    parser.add_argument(
        "scenarios",
        nargs="*",
        help="Scenarios to run (default: all)",
        choices=list(SCENARIOS.keys()) + ["all"],
    )
    parser.add_argument("--cluster", default="prefect-test", help="Kind cluster name")
    parser.add_argument(
        "--work-pool", default="k8s-test", help="Prefect work pool name"
    )

    args = parser.parse_args()

    # Determine which scenarios to run
    if not args.scenarios or "all" in args.scenarios:
        selected_scenarios = list(SCENARIOS.values())
    else:
        selected_scenarios = [SCENARIOS[name] for name in args.scenarios]

    results: dict[str, bool] = {}
    for scenario_class in selected_scenarios:
        scenario = scenario_class(
            cluster_name=args.cluster, work_pool_name=args.work_pool
        )
        results[scenario.name] = scenario.run()

    # Print summary
    console.print("\n[bold]Test Summary:[/bold]")
    for name, passed in results.items():
        status = "[green]PASSED[/green]" if passed else "[red]FAILED[/red]"
        console.print(f"{name}: {status}")

    if not all(results.values()):
        exit_with_error(f"Some tests failed: {results}")


if __name__ == "__main__":
    main()
