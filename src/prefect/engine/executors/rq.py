import time
from typing import Any, Callable, Iterable, List

from redis import Redis
import rq

from prefect.engine.executors.base import Executor

class RQExecutor(Executor):
    def __init__(self, 
                 connection: Redis, 
                 queue_name: str = "default", 
                 timeout : int = 180):
        self.connection = connection
        self.queue_name = queue_name
        self.timeout = timeout
        super().__init__()
    
    def submit(self, fn, *args, **kwargs):
        q = self.queue()
        future = q.enqueue(fn, args, kwargs)
        return future
    
    def map(self, fn, *args):
        futures = [self.queue().enqueue(fn, args=(*arg,)) for arg in args]
        return futures
    
    
    def wait(self, futures):
        if futures:
            while True:
                if all(f.is_finished for f in futures):
                    break
                elif any(f.is_failed for f in futures):
                    raise Exception
                else:
                    time.sleep(0.05)
            return [f.result for f in futures]
        return futures 
    
    def queue(self, maxsize: int = 0) -> rq.Queue:
        return rq.Queue(self.queue_name, 
                        default_timeout=self.timeout, 
                        connection=self.connection)
