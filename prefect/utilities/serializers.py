import inspect
import json

import prefect
from prefect.signals import SerializationError
from prefect.utilities import functions
from prefect.utilities.json import (
    JSONCodec, register_json_codec, serialized_name, SERIALIZED_NAME_REGISTRY)


@register_json_codec('__serialized_dict__')
class SerializeAsDict(JSONCodec):
    """
    Serializes an object by storing its class name and __dict__, similar to how
    the builtin copy module works. The object is deserialized by creating a
    new instance of its class, and applying the serialized __dict__.
    """

    def serialize(self):

        if hasattr(self.value, '__getstate__'):
            dct = self.value.__getstate__().copy()
        else:
            dct = self.value.__dict__.copy()

        serialized_value = self.value.serialize()

        get_value_from_serialized = []
        for k, v in list(dct.items()):
            if v == serialized_value.get(k, object()):
                get_value_from_serialized.append(k)
                del dct[k]

        serialized = dict(
            type=type(self.value),
            dict=dct,
            get_value_from_serialized=get_value_from_serialized,
            serialized=serialized_value,
            prefect_version=prefect.__version__)

        return serialized

    @classmethod
    def deserialize(cls, obj):
        instance = object.__new__(obj['type'])
        serialized = obj.get('serialized', {})
        new_dict = obj.get('dict', {})
        for k in obj.get('get_value_from_serialized', []):
            new_dict[k] = serialized.get(k)
        instance.__dict__.update(new_dict)
        instance.after_deserialize(serialized)
        return instance


@register_json_codec('__serialized_init_args__')
class SerializeAsInitArgs(JSONCodec):

    def serialize(self):
        """
        Return a JSON-serializable dictionary that can be reconstructed as this object.
        """
        return dict(
            type=type(self.value),
            serialized=self.value.serialize(),
            init_args=self.value._init_args)

    @classmethod
    def deserialize(cls, obj):
        init_args = obj.get('init_args', {})
        args = init_args.pop('*args', ())
        kwargs = init_args.pop('**kwargs', {})

        instance = obj['type'](*args, **init_args, **kwargs)
        instance.after_deserialize(obj.get('serialized', {}))

        return instance


class SerializableMetaclass(type):

    def __new__(meta, name, bases, class_dict):
        cls = type.__new__(meta, name, bases, class_dict)
        SERIALIZED_NAME_REGISTRY[serialized_name(cls)] = cls
        return cls


class Serializable(metaclass=SerializableMetaclass):
    """
    A class that can serialize itself using its `serializer_class` attribute.
    """

    serializer_class = SerializeAsDict

    def __new__(cls, *args, **kwargs):
        instance = super().__new__(cls)

        if instance.serializer_class == SerializeAsInitArgs:

            signature = inspect.signature(instance.__init__)
            callargs = signature.bind_partial(*args, **kwargs).arguments

            # identify the argument corresponding to **kwargs
            var_k = functions.get_var_kw_arg(instance.__init__)
            callargs['**kwargs'] = callargs.pop(var_k, {})

            # identify the argument corresponding to *args
            var_pos = functions.get_var_pos_arg(instance.__init__)
            callargs['*args'] = callargs.pop(var_pos, {})

            instance._init_args = callargs

        return instance

    def __init__(self):
        pass

    def __eq__(self, other):
        return type(self) == type(other) and self.__json__() == other.__json__()

    def serialize(self):
        """
        A JSON-serializable description of the object that will be passed to
        """
        return {}

    @classmethod
    def deserialize(cls, obj):
        if not isinstance(obj, str):
            obj = json.dumps(obj)
        return json.loads(obj)

    def after_deserialize(self, serialized):
        pass

    def __json__(self):
        return self.serializer_class(self).__json__()


# def serialize_to_encrypted_pickle(obj, encryption_key=None):
#     """
#     Serialize a Python object, optionally encrypting the result with a key

#     Args:
#         obj (object): The object to serialize
#         encryption_key (str): key used to encrypt the serialization
#     """
#     if encryption_key is None:
#         encryption_key = prefect.config.get('security', 'encryption_key')
#     if not encryption_key:
#         raise ValueError("Encryption key not set.")
#     serialized = base64.b64encode(cloudpickle.dumps(obj))
#     serialized = Fernet(encryption_key).encrypt(serialized).decode()
#     return serialized

# def deserialize_from_encrypted_pickle(serialized, encryption_key=None):
#     """
#     Deserialized a Python object.

#     Args:
#         serialized (bytes): serialized Prefect object
#         encryption_key (str): key used to decrypt the serialization
#     """
#     if encryption_key is None:
#         encryption_key = prefect.config.get('security', 'encryption_key')
#     if not encryption_key:
#         raise ValueError("Encryption key not set.")
#     if isinstance(serialized, str):
#         serialized = serialized.encode()
#     serialized = Fernet(encryption_key).decrypt(serialized).decode()
#     return cloudpickle.loads(base64.b64decode(serialized))

# @register_json_codec('__encrypted_pickle__')
# class SerializeAsPickle(JSONCodec):

#     def serialize(self):
#         return {
#             'pickle': serialize_to_encrypted_pickle(self.value),
#             'prefect_version': prefect.__version__
#         }

#     @classmethod
#     def deserialize(cls, obj):
#         """
#         We never automatically unpickle.

#         Call json_unpickle(obj, safe=False) for that behavior.
#         """
#         return obj

#     @classmethod
#     def unsafe_deserialize(cls, obj):
#         return deserialize_from_encrypted_pickle(obj['pickle'])
