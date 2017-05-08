from concurrent.futures import Future
from contextlib import contextmanager
import distributed
from distributed import worker_client
import prefect

_LOCAL_CLUSTER = None


def running_in_cluster():
    """
    Returns True if the current thread is running inside a distributed cluster
    and False otherwise.
    """
    return hasattr(distributed.worker.thread_state, 'execution_state')


@contextmanager
def client(address=None, separate_thread=False):
    """
    Context manager that returns a Distributed client.

    Depending on how this function is called,
        1. A standard Distributed client. This will be returned if 1) an
            address is provided or 2) this function is called from outside
            a Distributed cluster.
        2. A Distributed worker_client. This will be returned if the function
            is called from inside a Distributed cluster (unless an address is
            provided).
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

    Args:
        address (str): if provided, a Client will be returned that connects
            to that address. If None, the address will be read from the Prefect
            configuration (unless called from inside an existing cluster). If
            'local' or 'localcluster', a LocalCluster is started and maintained
            for the life of this Prefect process. Other Prefect processes can
            NOT discover the local cluster, but it will be reused within this
            process.

        separate_thread (bool): if a worker_client is returned, this determines
            whether it secedes from the threadpool or not. Has no effect
            otherwise.
    """

    global _LOCAL_CLUSTER

    # return a worker client is we are running in the cluster
    # and no address is provided OR if the provided address is the cluster
    if running_in_cluster():
        s_addr = distributed.worker.thread_state.execution_state['scheduler']
        if address is None or address.lower() == s_addr.lower():
            with worker_client(separate_thread=separate_thread) as client:
                yield client
                return

    # otherwise connect to the supplied address
    if address is None:
        address = prefect.config.get('cluster', 'address')
    elif address.lower() in ('local', '', 'localcluster'):
        if _LOCAL_CLUSTER is None:
            _LOCAL_CLUSTER = distributed.LocalCluster()
        address = _LOCAL_CLUSTER.scheduler.address
    with distributed.Client(address) as client:
        yield client
        return
