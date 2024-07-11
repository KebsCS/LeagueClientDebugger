from rtmp.ByteStreamReader import ByteStreamReader
from rtmp.Amf3 import Amf3Decoder, TypedObject, Amf3Date, Amf3Encoder

TYPE_NUMBER = b'\x00'
TYPE_BOOL = b'\x01'
TYPE_STRING = b'\x02'
TYPE_OBJECT = b'\x03'
TYPE_MOVIECLIP = b'\x04'
TYPE_NULL = b'\x05'
TYPE_UNDEFINED = b'\x06'
TYPE_REFERENCE = b'\x07'
TYPE_MIXEDARRAY = b'\x08'
TYPE_OBJECTTERM = b'\x09'
TYPE_ARRAY = b'\x0A'
TYPE_DATE = b'\x0B'
TYPE_LONGSTRING = b'\x0C'
TYPE_UNSUPPORTED = b'\x0D'
TYPE_RECORDSET = b'\x0E'
TYPE_XML = b'\x0F'
TYPE_TYPEDOBJECT = b'\x10'
TYPE_AMF3 = b'\x11'


class Amf0Undefined(object):
    def __repr__(self):
        return "'AMF0_UNDEFINED'"

    def __str__(self):
        return "AMF0_UNDEFINED"

    def to_json(self):
        return str(self)

    def __nonzero__(self):
        return False


class ASObject(dict):
    pass


class MixedArray(dict):
    pass


class Amf0Amf3(object):
    def __init__(self, value):
        self.value = value

    def __repr__(self):
        return self.value.__repr__()

    def to_json(self):
        if hasattr(self.value, 'to_json'):
            return self.value.to_json()
        return self.value


class Amf0Date(Amf3Date):
    def __init__(self, date, timezone):
        super().__init__(timezone, date)
        self.timezone = timezone


class Amf0Decoder:
    known_objects = []

    def __init__(self, buffer: bytes):
        self.stream = ByteStreamReader(buffer)

    def decode(self):
        data = self.stream.read(1)
        if data == TYPE_NUMBER:
            return self.read_number()
        elif data == TYPE_BOOL:
            return self.read_boolean()
        elif data == TYPE_STRING:
            return self.read_string()
        elif data == TYPE_OBJECT:
            return self.read_object()
        elif data == TYPE_NULL:
            return self.read_null()
        elif data == TYPE_UNDEFINED:
            return self.read_undefined()
        elif data == TYPE_REFERENCE:
            return self.read_reference()
        elif data == TYPE_MIXEDARRAY:
            return self.read_mixed_array()
        elif data == TYPE_ARRAY:
            return self.read_list()
        elif data == TYPE_DATE:
            return self.read_date()
        elif data == TYPE_LONGSTRING:
            return self.read_long_string()
        elif data == TYPE_UNSUPPORTED:
            return self.read_null()
        elif data == TYPE_XML:
            return self.read_XML()
        elif data == TYPE_TYPEDOBJECT:
            return self.read_typed_object()
        elif data == TYPE_AMF3:
            return self.read_AMF3()
        else:
            raise ValueError("Unknown amf0 type")

    def read_number(self):
        return _check_for_int(self.stream.read_double())

    def read_boolean(self):
        return bool(self.stream.read_uchar())

    def read_string(self, bytes=False):
        length = self.stream.read_ushort()
        b = self.stream.read(length)

        if bytes:
            return b

        return b.decode('utf-8')

    def read_null(self):
        return None

    def read_undefined(self):
        return Amf0Undefined()

    def read_mixed_array(self):
        length = self.stream.read_ulong()
        result = MixedArray()
        for i in range(0, length):
            key = self.read_string()
            result[key] = self.decode()

        Amf0Decoder.known_objects.append(result.values())

    def read_list(self):
        obj = []
        l = self.stream.read_ulong()

        for i in range(l):
            obj.append(self.decode())

        return obj

    def read_typed_object(self):
        object_name = self.read_string()
        object_value = self.read_object()
        typed_object = TypedObject(object_name, object_value)

        return typed_object

    def read_AMF3(self):
        self.stream.remove_already_read()
        amf3Decoder = Amf3Decoder(self.stream.data)
        decoded = amf3Decoder.decode()
        self.stream.offset += amf3Decoder.stream.offset
        return Amf0Amf3(decoded)

    def read_object(self):
        obj = ASObject()

        key = self.read_string(True)
        key = key.decode() if isinstance(key, bytes) else key

        while self.stream.peek(1) != TYPE_OBJECTTERM:
            obj[key] = self.decode()
            key = self.read_string(True)
            key = key.decode() if isinstance(key, bytes) else key

        # discard the end marker (TYPE_OBJECTTERM)
        self.stream.read(1)
        return obj

    def read_reference(self):
        idx = self.stream.read_ushort()
        try:
            return Amf0Decoder.known_objects[idx]
        except IndexError:
            raise IndexError("Unknown afm0 object reference")

    def read_date(self):
        date = self.stream.read_double()
        timezone = self.stream.read_short()

        return Amf0Date(date, timezone)

    def read_long_string(self):
        length = self.stream.read_ulong()
        b = self.stream.read(length)
        return b.decode('utf-8')

    def read_XML(self):
        raise NotImplementedError("Amf0 unsupported xml reading")


class Amf0Encoder:
    def __init__(self):
        self.stream = ByteStreamReader()

    def encode(self, obj):
        # missing types: reference
        t = type(obj)
        if obj is None or t is None:
            self.write_null()
        elif t in (int, float):
            self.write_number(obj)
        elif t is bool:
            self.write_boolean(obj)
        elif t is str or issubclass(t, str):
            self.write_string(obj)
        elif t is ASObject or issubclass(t, ASObject):
            self.write_object(obj)
        elif t is Amf0Undefined:
            self.write_undefined()
        elif t is MixedArray:
            self.write_mixed_array(obj)
        elif t in (list, tuple, set, frozenset):
            self.write_list(obj)
        elif t is Amf0Date:
            self.write_date(obj)
        elif t is TypedObject:
            self.write_typed_object(obj)
        elif t is Amf0Amf3:
            self.write_AMF3(obj)
        else:
            raise ValueError(f"Unimplemented amf0 encode {t}")

    def write_number(self, n):
        self.stream.write(TYPE_NUMBER)
        self.stream.write_double(float(n))

    def write_boolean(self, b):
        self.stream.write(TYPE_BOOL)

        if b:
            self.stream.write_uchar(1)
        else:
            self.stream.write_uchar(0)

    def write_string(self, u: str):
        s = u.encode('utf-8')
        l = len(s)

        if l > 0xffff:
            self.stream.write(TYPE_LONGSTRING)
        else:
            self.stream.write(TYPE_STRING)

        if l > 0xffff:
            self.stream.write_ulong(l)
        else:
            self.stream.write_ushort(l)

        self.stream.write(s)

    def write_string_key(self, u: str):
        s = u.encode('utf-8')
        l = len(s)

        if l > 0xffff:
            self.stream.write_ulong(l)
        else:
            self.stream.write_ushort(l)

        self.stream.write(s)

    def write_object(self, o: ASObject):
        self.stream.write(TYPE_OBJECT)
        for key in o.keys():
            self.write_string_key(key)
            self.encode(o[key])

        self.stream.write_uchar(0x00)
        self.stream.write_uchar(0x00)
        self.stream.write_uchar(0x09)

    def write_null(self):
        self.stream.write(TYPE_NULL)

    def write_undefined(self):
        self.stream.write(TYPE_UNDEFINED)

    def write_mixed_array(self, o: MixedArray):
        self.stream.write(TYPE_MIXEDARRAY)
        self.stream.write_ulong(len(o))

        for key in o.keys():
            self.write_string_key(key)
            self.encode(o[key])

        self.stream.write_uchar(0x00)
        self.stream.write_uchar(0x00)
        self.stream.write_uchar(0x09)

    def write_list(self, l):
        self.stream.write(TYPE_ARRAY)
        self.stream.write_ulong(len(l))

        for data in l:
            self.encode(data)

    def write_date(self, d: Amf0Date):
        self.stream.write(TYPE_DATE)
        self.stream.write_double(d.date)
        self.stream.write_short(d.timezone)

    def write_typed_object(self, o: TypedObject):
        self.stream.write(TYPE_TYPEDOBJECT)
        self.write_string_key(o.name)

        for key in o.keys():
            self.write_string_key(key)
            self.encode(o[key])

        self.stream.write_uchar(0x00)
        self.stream.write_uchar(0x00)
        self.stream.write_uchar(0x09)

    def write_AMF3(self, o: Amf0Amf3):
        self.stream.write(TYPE_AMF3)
        amf3Encoder = Amf3Encoder()
        amf3Encoder.encode(o.value)
        self.stream.append(amf3Encoder.stream.data)


def _check_for_int(x):
    """
    This is a compatibility function that takes a C{float} and converts it to
    an C{int} if the values are equal.
    """
    try:
        y = int(x)
    except (OverflowError, ValueError):
        pass
    else:
        # There is no way in AMF0 to distinguish between integers and floats
        if x == x and y == x:
            return y

    return x
