import prefect
import logging

class Runner:

    def __init__(self, executor=None, logger_name=None, progress_fn=None):
        if executor is None:
            executor = prefect.runners.executors.default_executor()
        self.executor = executor
        self.logger = logging.getLogger(logger_name or type(self).__name__)
        if progress_fn:
            self.record_progress = progress_fn

    def record_progress(self, progress):
        self.logger.info(f'PROGRESS: {progress}')
