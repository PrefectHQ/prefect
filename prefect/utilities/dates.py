import datetime
import dateutil

def parse_datetime(dt):
    """
    Parses a string, bytes, float, or datetime object and returns a
    corresponding datetime
    """
    if isinstance(dt, (str, bytes)):
        return dateutil.parser.parse(dt)
    elif isinstance(dt, float):
        return datetime.datetime.fromtimestamp(dt)
    elif isinstance(dt, (datetime.datetime)):
        return dt
    else:
        raise TypeError(
            'Unrecognized datetime input: {}'.format(type(dt).__name__))
