import logging.config
import sys
from datetime import datetime
from pathlib import Path

import yaml

from redactor.tasks import task_plain_message


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


def clear_logging_cfg():
    mgr = logging.Logger.manager
    # Skip the loggers added by PyCharm when using the debugger.
    logger_names = [
        name
        for name in mgr.loggerDict
        if name not in ("concurrent.futures", "concurrent", "asyncio")
    ]
    for name in logger_names:
        del mgr.loggerDict[name]


default_factory = logging.getLogRecordFactory()
context = dict()


def logging_cfg(cfg_file: str):
    clear_logging_cfg()
    ctx = {"flow_name": "Redactor", "started": datetime.now(), "redactor_root": "/tmp"}

    def context_factory(*args, **kwargs):
        record = default_factory(*args, **kwargs)
        for key, value in ctx.items():
            setattr(record, key, value)
        return record

    with Path(cfg_file).open("rt") as fh:
        cfg = yaml.safe_load(fh)

    cur_factory = logging.getLogRecordFactory()
    if cur_factory == default_factory:
        logging.setLogRecordFactory(context_factory)

    logging.config.dictConfig(cfg)


def test_logging_setup_teardown():
    logging_cfg("setup_teardown_logging.yml")
    task_plain_message()


def test_file_redactor():
    logging_cfg("filename_redactor_logging.yml")
    dump_logging_cfg()
    task_plain_message()
