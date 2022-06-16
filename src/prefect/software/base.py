class Requirement:
    # Implementations are expected to at least contain a name attribute
    name: str

    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, value):
        if not isinstance(value, cls):
            # Attempt to parse the string representation of the input type
            return cls(str(value))
        return value

    def __eq__(self, __o: object) -> bool:
        """
        Requirements are equal if their string specification matches.
        """
        if not isinstance(__o, Requirement):
            raise NotImplementedError()

        return str(self) == str(__o)

    def __repr__(self) -> str:
        return f"{type(self).__name__}({str(self)!r})"
