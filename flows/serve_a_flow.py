import signal
import tempfile
from datetime import timedelta
from pathlib import Path

from prefect import flow
from prefect.settings import PREFECT_RUNNER_POLL_FREQUENCY, temporary_settings


@flow
def may_i_take_your_hat_sir(item: str, counter_dir: Path):
    assert item == "hat", "I don't know how to do everything"
    (counter_dir / f"{id(may_i_take_your_hat_sir)}.txt").touch()
    return f"May I take your {item}?"


def _handler(signum, frame):
    raise KeyboardInterrupt("Simulating user interruption")


def count_runs(counter_dir: Path):
    return len(list(counter_dir.glob("*.txt")))


if __name__ == "__main__":
    TIMEOUT: int = 15
    INTERVAL_SECONDS: int = 3

    MINIMUM_EXPECTED_N_FLOW_RUNS: int = 3

    signal.signal(signal.SIGALRM, _handler)
    signal.alarm(TIMEOUT)

    with tempfile.TemporaryDirectory() as tmp_dir:
        counter_dir = Path(tmp_dir) / "flow_run_counter"
        counter_dir.mkdir(exist_ok=True)

        with temporary_settings({PREFECT_RUNNER_POLL_FREQUENCY: 1}):
            try:
                may_i_take_your_hat_sir.serve(
                    interval=timedelta(seconds=INTERVAL_SECONDS),
                    parameters={"item": "hat", "counter_dir": counter_dir},
                )
            except KeyboardInterrupt as e:
                print(str(e))
            finally:
                signal.alarm(0)

        actual_run_count = count_runs(counter_dir)

        assert actual_run_count >= MINIMUM_EXPECTED_N_FLOW_RUNS, (
            f"Expected at least {MINIMUM_EXPECTED_N_FLOW_RUNS} flow runs, got {actual_run_count}"
        )

        print(f"Successfully completed and audited {actual_run_count} flow runs")
