import logging
import sys


def dump_logging_cfg(fh=sys.stdout):
    def dump_filters(filters, indent: str, fh):
        indent += "\t"
        print(f"{indent}{'Filters:':>10}", file=fh)
        for filter in filters:
            pass

    def dump_formatter(formatter, indent, fh):
        if not formatter:
            return
        indent += "\t"
        print(f"{indent}{'Formatter:':>10}", file=fh)
        print(f"{indent}\t{'class:':>10} {formatter.__class__}", file=fh)
        print(f"{indent}\t{'format:':>10} {formatter._fmt}", file=fh)

    def dump_handlers(handlers, indent: str, fh):
        indent += "\t"
        print(f"{indent}{'Handlers:':>10}", file=fh)
        for handler in handlers:
            print(f"\n{indent}\t{'class:':>10} {handler.__class__}", file=fh)
            print(f"{indent}\t{'name:':>10} {handler.name}", file=fh)
            print(f"{indent}\t{'level:':>10} {handler.level}", file=fh)
            dump_filters(handler.filters, indent, fh)
            dump_formatter(handler.formatter, indent, fh)

    mgr = logging.Logger.manager
    indent = "\t"
    print("Loggers: ", file=fh)
    for name, logger in mgr.loggerDict.items():
        # Skip the loggers added by PyCharm when using the debugger, or CloudHandler.
        if name in ("concurrent.futures", "concurrent", "asyncio"):
            continue
        if name.startswith("urllib3") or name.startswith("requests"):
            continue
        print(f"\n{indent}{name}:", file=fh)
        print(f"{indent}\t{'class:':>10} {logger.__class__}", file=fh)
        print(f"{indent}\t{'level:':>10} {logger.level}", file=fh)
        print(f"{indent}\t{'propagate:':>10} {logger.propagate}", file=fh)
        print(f"{indent}\t{'parent:':>10} {logger.parent.name}", file=fh)
        dump_handlers(logger.handlers, indent, fh)
