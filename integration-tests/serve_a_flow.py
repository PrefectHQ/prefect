import signal
from datetime import timedelta
from types import FrameType

from prefect import flow


def _handler(signum: int, frame: FrameType | None):
    raise KeyboardInterrupt("Simulating user interruption")


@flow
def may_i_take_your_hat_sir(item: str):
    assert item == "hat", "I don't know how to do everything"
    return f"May I take your {item}?"


if __name__ == "__main__":
    signal.signal(signal.SIGALRM, _handler)
    # Raise a KeyboardInterrupt after 5 seconds
    signal.alarm(5)
    try:
        may_i_take_your_hat_sir.serve(
            interval=timedelta(seconds=60),
            parameters={"item": "hat"},
        )
    except KeyboardInterrupt as e:
        print(str(e))
    finally:
        signal.alarm(0)
