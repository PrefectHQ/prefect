import logging


class GriffeParseTypeAnnotationFilter(logging.Filter):
    def filter(self, rec):
        if "No type or annotation for parameter" in rec.msg:
            return 0
        return 1
