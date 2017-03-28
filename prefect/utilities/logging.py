import logging


class LoggingMixin:
    """
    Class with a .logger property preconfigured to use the class name
    """

    @property
    def logger(self):
        if hasattr(self, '_logger'):
            return self._logger
        else:
            self._logger = logging.root.getChild(type(self).__name__)
            return self._logger
