# Utilities

## JSON Serialization

Prefect provides a number of utilities for serializing Python objects to JSON.

### JSONCodecs

A `JSONCodec` is a class that serializes and deserializes Python objects to a JSON-compatible type.

For example, this is the `JSONCodec` for Python `datetimes`:

```python

@register_json_codec(datetime.datetime)
class DateTimeCodec(JSONCodec[datetime.datetime, str]):
    """
    Serialize/deserialize DateTimes
    """

    codec_key = "datetime"

    def serialize(self) -> str:
        return self.value.isoformat()

    @staticmethod
    def deserialize(obj: str) -> datetime.datetime:
        return dateutil.parser.parse(obj)

```

This allows us to automatically serialize and deserialize `datetimes`:

```python
dt = datetime.datetime(2018, 1, 1)
json_dt = json.dumps(dt)

assert json_dt == '{"//datetime": "2018-01-01T00:00:00"}' # true
assert json.loads(json_dt) == dt # True
```

This can be applied in a recursive manner to serialize classes:

```python
class MyClass(Serializable):
    def __init__(self, x, y):
        self.x = x
        self.y = y

json.dumps(MyClass(1, datetime.datetime(2018, 1, 1)))
```

Resulting in a deserializable JSON object:

```json
{
  "//obj_attrs": {
    "type": {
      "//obj": "__main__.MyClass"
    },
    "attrs": {
      "x": 1,
      "y": {
        "//datetime": "2018-01-01T00:00:00"
      }
    }
  }
}
```
