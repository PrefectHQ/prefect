import distributed
import prefect

def Client():
    """
    Get a distributed client for the Prefect cluster
    """
    cluster_address = prefect.config.get('dask', 'cluster_address')
    return distributed.Client(cluster_address)
