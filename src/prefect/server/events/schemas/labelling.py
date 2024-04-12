from typing import Dict, Generic, Iterable, Iterator, List, Optional, Tuple, TypeVar

from prefect.pydantic import HAS_PYDANTIC_V2, USE_PYDANTIC_V2

T = TypeVar("T")


class LabelDiver:
    """The LabelDiver supports templating use cases for any Labelled object, by
    presenting the labels as a graph of objects that may be accessed by attribute.  For
    example:

        diver = LabelDiver({
            'hello.world': 'foo',
            'hello.world.again': 'bar'
        })

        assert str(diver.hello.world) == 'foo'
        assert str(diver.hello.world.again) == 'bar'

    """

    _value: str
    _divers: Dict[str, "LabelDiver"]
    _labels: Dict[str, str]

    def __init__(self, labels: Dict[str, str], value: str = ""):
        self._labels = labels.copy()
        self._value = value

        divers: Dict[str, Dict[str, str]] = {}
        values: Dict[str, str] = {}

        for key, value in labels.items():
            head, _, tail = key.partition(".")
            if tail:
                if head not in divers:
                    divers[head] = {}

                divers[head][tail] = labels[key]
            else:
                values[head] = value

        # start with keys that had sub-divers...
        self._divers: Dict[str, LabelDiver] = {
            k: LabelDiver(v, value=values.pop(k, "")) for k, v in divers.items()
        }
        # ...then mix in any remaining keys that _only_ had values
        self._divers.update(**{k: LabelDiver({}, value=v) for k, v in values.items()})

    def __str__(self) -> str:
        return self._value or ""

    def __repr__(self) -> str:
        return f"LabelDiver(divers={self._divers!r}, value={self._value!r})"

    def __len__(self) -> int:
        return len(self._labels)

    def __iter__(self) -> Iterator[Tuple[str, str]]:
        return iter(self._labels.items())

    def __getitem__(self, key: str) -> str:
        return self._labels[key]

    def __getattr__(self, name: str) -> "LabelDiver":
        if name.startswith("_"):
            raise AttributeError

        try:
            return self._divers[name]
        except KeyError:
            raise AttributeError


if HAS_PYDANTIC_V2 and USE_PYDANTIC_V2:
    from pydantic import RootModel

    class _RootBase(RootModel[Dict[str, T]], Generic[T]):
        root: Dict[str, T]

        @property
        def _root(self) -> Dict[str, T]:
            return self.root

        def __init__(self, __root__: Dict[str, T]):
            super().__init__(root=__root__)
elif HAS_PYDANTIC_V2:
    from pydantic.v1.generics import GenericModel

    class _RootBase(GenericModel, Generic[T]):
        __root__: Dict[str, T]

        @property
        def _root(self) -> Dict[str, T]:
            return self.__root__

else:
    from pydantic.generics import GenericModel

    class _RootBase(GenericModel, Generic[T]):
        __root__: Dict[str, T]

        @property
        def _root(self) -> Dict[str, T]:
            return self.__root__


class Labelled(_RootBase[str], extra="ignore"):
    """An object defined by string labels and values"""

    def keys(self) -> Iterable[str]:
        return self._root.keys()

    def items(self) -> Iterable[Tuple[str, str]]:
        return self._root.items()

    def __getitem__(self, label: str) -> str:
        return self._root[label]

    def __setitem__(self, label: str, value: str) -> str:
        self._root[label] = value
        return value

    def __contains__(self, key: str) -> bool:
        return key in self._root

    def get(self, label: str, default: Optional[str] = None) -> Optional[str]:
        return self._root.get(label, default)

    def as_label_value_array(self) -> List[Dict[str, str]]:
        return [{"label": label, "value": value} for label, value in self.items()]

    @property
    def labels(self) -> LabelDiver:
        return LabelDiver(self._root)

    def has_all_labels(self, labels: Dict[str, str]) -> bool:
        return all(self._root.get(label) == value for label, value in labels.items())
