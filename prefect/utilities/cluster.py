from concurrent.futures import Future
from contextlib import contextmanager
import distributed
import prefect

_LOCAL_CLUSTER = None


def running_in_cluster():
    """
    Returns True if the current thread is running inside a distributed cluster
    and False otherwise.
    """
    return hasattr(distributed.worker.thread_state, 'execution_state')


@contextmanager
def client(debug=False):
    """
    Context manager that returns a Distributed client.

    There are a few types of clients that can be returned:
        1. If the context is entered from an existing cluster worker,
            a worker_client is returned and closed when the context exits.
        2. If the context is entered outside the cluster a standard Client is
            returned and closed when the context exits. If the specified
            cluster address is "local" or missing, a LocalCluster is started
            and maintained for the life of this Prefect process. Note that
            other Prefect processes will NOT automatically discover the
            LocalCluster.

    If the context is entered from inside the cluster, a worker_client is
    yielded; otherwise a standard Client is yielded.
    """

    global _LOCAL_CLUSTER
    address = prefect.config.get('cluster', 'address')

    if running_in_cluster():
        with distributed.worker_client() as client:
            yield client
    else:
        if address.lower() in ('none', 'local', '', 'localcluster'):
            if _LOCAL_CLUSTER is None:
                _LOCAL_CLUSTER = distributed.LocalCluster()
            address = _LOCAL_CLUSTER.scheduler.address
        with distributed.Client(address) as client:
            yield client
