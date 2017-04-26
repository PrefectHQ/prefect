from contextlib import contextmanager
import distributed
import prefect

def running_in_cluster():
    """
    Returns True if the current thread is running inside a distributed cluster
    and False otherwise.
    """
    return hasattr(distributed.worker.thread_state, 'execution_state')

@contextmanager
def client():
    """
    Context manager that returns a Distributed client.

    If the context is entered from inside the cluster, a worker_client is
    yielded; otherwise a standard Client is yielded.
    """
    if running_in_cluster():
        with distributed.worker_client() as client:
            yield client
    else:
        address = prefect.config.get('cluster', 'address')
        with distributed.Client(address) as client:
            yield client
