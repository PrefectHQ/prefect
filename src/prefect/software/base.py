from typing import Iterable, List, Optional


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

    def __eq__(self, other: object) -> bool:
        """
        Requirements are equal if their string specification matches.
        """
        if not isinstance(other, Requirement):
            return NotImplemented

        return str(self) == str(other)

    def __repr__(self) -> str:
        return f"{type(self).__name__}({str(self)!r})"


def remove_duplicate_requirements(
    constant: Iterable[Requirement], to_deduplicate: Iterable[Requirement]
) -> List[Requirement]:
    """
    Returns a list of requirements that excludes requirements already specified
    in the first iterable.
    """
    constant_names = {req.name for req in constant}
    return [req for req in to_deduplicate if req.name not in constant_names]


def pop_requirement_by_name(
    requirements: List[Requirement], name: str
) -> Optional[Requirement]:
    for index, requirement in enumerate(requirements):
        if requirement.name == name:
            requirements.pop(index)
            return requirement
    return None
