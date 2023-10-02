import datetime

import pendulum


class DateTimeTZ(pendulum.DateTime):
    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v):
        if isinstance(v, str):
            return pendulum.parse(v)
        elif isinstance(v, datetime.datetime):
            return pendulum.instance(v)
        else:
            raise ValueError("Unrecognized datetime.")
