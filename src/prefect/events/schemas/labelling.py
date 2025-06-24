from typing import Dict, Iterable, Iterator, List, Optional, Tuple

from pydantic import RootModel


class LabelDiver:
    """The LabelDiver supports templating use cases for any Labelled object, by
    presenting the labels as a graph of objects that may be accessed by attribute.  For
    example:

        ```python
        diver = LabelDiver({
            'hello.world': 'foo',
            'hello.world.again': 'bar'
        })

        assert str(diver.hello.world) == 'foo'
        assert str(diver.hello.world.again) == 'bar'
        ```

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


class Labelled(RootModel[Dict[str, str]]):
    def keys(self) -> Iterable[str]:
        return self.root.keys()

    def items(self) -> Iterable[Tuple[str, str]]:
        return self.root.items()

    def __getitem__(self, label: str) -> str:
        return self.root[label]

    def __setitem__(self, label: str, value: str) -> str:
        self.root[label] = value
        return value

    def __contains__(self, key: str) -> bool:
        return key in self.root

    def get(self, label: str, default: Optional[str] = None) -> Optional[str]:
        return self.root.get(label, default)

    def as_label_value_array(self) -> List[Dict[str, str]]:
        return [{"label": label, "value": value} for label, value in self.items()]

    @property
    def labels(self) -> LabelDiver:
        return LabelDiver(self.root)

    def has_all_labels(self, labels: Dict[str, str]) -> bool:
        return all(self.root.get(label) == value for label, value in labels.items())
