import logging.config
import sys
from datetime import datetime
from pathlib import Path

import yaml

from redactor.tasks import task_plain_message, task_uncaught_exception, task_runner


def dump_logging_cfg(fh=sys.stdout):
    def dump_filters(filters, indent: str, fh):
        indent += "\t"
        print(f"{indent}{'Filters:':>10}", file=fh)
        for filter in filters:
            pass

    def dump_formatter(formatter, indent, fh):
        indent += "\t"
        print(f"{indent}{'Formatter:':>10}", file=fh)
        print(f"{indent}\t{'format:':>10} {formatter._fmt}", file=fh)

    def dump_handlers(handlers, indent: str, fh):
        indent += "\t"
        print(f"{indent}{'Handlers:':>10}", file=fh)
        for handler in handlers:
            print(f"{indent}\t{'class:':>10} {handler.__class__}", file=fh)
            print(f"{indent}\t{'name:':>10} {handler.name}", file=fh)
            print(f"{indent}\t{'level:':>10} {handler.level}", file=fh)
            dump_filters(handler.filters, indent, fh)
            dump_formatter(handler.formatter, indent, fh)

    mgr = logging.Logger.manager
    indent = "\t"
    print("Loggers: ")
    for name, logger in mgr.loggerDict.items():
        # Skip the loggers added by PyCharm when using the debugger.
        if name in ("concurrent.futures", "concurrent", "asyncio"):
            continue
        print(f"{indent}{name}:", file=fh)
        print(f"{indent}\t{'level:':>10} {logger.level}", file=fh)
        print(f"{indent}\t{'propagate:':>10} {logger.propagate}", file=fh)
        dump_handlers(logger.handlers, indent, fh)


def clear_handlers_cfg():
    mgr = logging.Logger.manager
    for name, logger in mgr.loggerDict.items():
        # Skip the loggers added by PyCharm when using the debugger.
        if name in ("concurrent.futures", "concurrent", "asyncio"):
            continue
        logger.handlers = []


default_factory = logging.getLogRecordFactory()


def fake_prefect_logging_cfg():
    ctx = {"flow_name": "Redactor", "started": datetime.now(), "redactor_root": "/tmp"}

    def context_factory(*args, **kwargs):
        record = default_factory(*args, **kwargs)
        # Add the context to the log record to use in the formatter.
        for key, value in ctx.items():
            setattr(record, key, value)
        return record

    cur_factory = logging.getLogRecordFactory()
    if cur_factory == default_factory:
        logging.setLogRecordFactory(context_factory)


def logging_cfg(cfg_file: str):
    clear_handlers_cfg()
    fake_prefect_logging_cfg()
    with Path(cfg_file).open("rt") as fh:
        cfg = yaml.safe_load(fh)

    logging.config.dictConfig(cfg)


def test_file_redactor():
    logging_cfg("filename_redactor_logging.yml")
    print()
    task_plain_message()


def test_exc_redactor():
    logging_cfg("filename_redactor_logging.yml")
    print()
    task_runner(task_uncaught_exception)
