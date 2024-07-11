import datetime
from rtmp.ByteStreamReader import ByteStreamReader

TYPE_UNDEFINED = b'\x00'
TYPE_NULL = b'\x01'
TYPE_BOOL_FALSE = b'\x02'
TYPE_BOOL_TRUE = b'\x03'
TYPE_INTEGER = b'\x04'
TYPE_NUMBER = b'\x05'
TYPE_STRING = b'\x06'
TYPE_XML = b'\x07'
TYPE_DATE = b'\x08'
TYPE_ARRAY = b'\x09'
TYPE_OBJECT = b'\x0A'
TYPE_XMLSTRING = b'\x0B'
TYPE_BYTEARRAY = b'\x0C'
TYPE_DICTIONARY = b'\x11'

MAX_29B_INT = 0x0FFFFFFF
MIN_29B_INT = -0x10000000

ENCODED_INT_CACHE = {}


class Amf3Undefined(object):
    def __repr__(self):
        return "'AMF3_UNDEFINED'"

    def __str__(self):
        return "AMF3_UNDEFINED"

    def to_json(self):
        return str(self)

    def __nonzero__(self):
        return False


class Amf3Date(object):
    def __init__(self, ref, date):
        self.ref = ref
        self.date = date

    def to_json(self):
        def get_datetime(secs):
            if secs < 0:
                return datetime.datetime(1970, 1, 1) + datetime.timedelta(seconds=secs)

            return datetime.datetime.utcfromtimestamp(secs)
        return get_datetime(self.date / 1000.0).strftime('%Y-%m-%dT%H:%M:%S.%f')

    def __repr__(self):
        return str(self.to_json())


class TypedObject(dict):
    def __init__(self, name="", data=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.name = name
        if data is not None:
            self.update(data)

    def to_json(self):
        attrs = {}
        if self.name:
            attrs['__class'] = self.name

        for k, v in self.items():
            attrs[k] = v

        return attrs

    def __repr__(self):
        repr(self.to_json())


class ByteArray(object):
    def __init__(self, data):
        self.data = data


class ClassDefinition(object):
    def __init__(self, externalizable, encoding, properties, name):
        self.externalizable = externalizable
        self.encoding = encoding
        self.static_properties = properties
        self.name = name


class Amf3Decoder:
    known_objects = []
    known_strings = []
    known_classes = []

    def __init__(self, buffer: bytes):
        self.stream = ByteStreamReader(buffer)

    def decode(self):
        data = self.stream.read(1)
        if data == TYPE_UNDEFINED:
            return self.read_undefined()
        elif data == TYPE_NULL:
            return self.read_null()
        elif data == TYPE_BOOL_FALSE:
            return self.read_false()
        elif data == TYPE_BOOL_TRUE:
            return self.read_true()
        elif data == TYPE_INTEGER:
            return self.read_integer()
        elif data == TYPE_NUMBER:
            return self.read_number()
        elif data == TYPE_STRING:
            return self.read_string()
        elif data == TYPE_XML:
            return self.read_XML()
        elif data == TYPE_DATE:
            return self.read_date()
        elif data == TYPE_ARRAY:
            return self.read_array()
        elif data == TYPE_OBJECT:
            return self.read_object()
        elif data == TYPE_XMLSTRING:
            return self.read_XML()
        elif data == TYPE_BYTEARRAY:
            return self.read_byte_array()
        elif data == TYPE_DICTIONARY:
            return self.read_dictionary()
        else:
            raise ValueError("Unknown amf3 type")

    def read_undefined(self):
        return Amf3Undefined()

    def read_null(self):
        return None

    def read_false(self):
        return False

    def read_true(self):
        return True

    def read_integer(self, signed=True):
        return decode_int(self.stream, signed)

    def read_number(self):
        return self.stream.read_double()

    def read_string(self):
        type = decode_int(self.stream, False)
        if type & 0x01 != 0:
            length = type >> 1
            if length == 0:
                return ""
            string = self.stream.read(length).decode('utf-8')
            Amf3Decoder.known_strings.append(string)
            return string
        else:
            return Amf3Decoder.known_strings[type >> 1]

    def read_XML(self):
        raise NotImplementedError("Amf3 unsupported xml reading")

    def read_date(self):
        ref = decode_int(self.stream, False)
        return Amf3Date(ref, self.stream.read_double())

    def read_array(self):
        type = decode_int(self.stream, False)
        if type & 0x01 == 0:
            return Amf3Decoder.known_objects[type >> 1]

        size = type >> 1
        key = self.read_string()
        if key == '' or not key:
            result = []

            for i in range(size):
                result.append(self.decode())
            return result
        else:
            raise NotImplementedError("Amf3 mixed arrays are not supported")


    def read_object(self):
        type = self.read_integer(False)
        if type & 0x01 == 0:
            return Amf3Decoder.known_objects[type >> 1]

        should_define = (type >> 1) & 0x01
        if should_define:
            externalizable = ((type >> 2) & 0x01) != 0
            encoding = (type >> 2) & 0x03
            properties = []
            name = self.read_string()

            for i in range(type >> 4):
                properties.append(self.read_string())
            class_definition = ClassDefinition(externalizable, encoding, properties, name)
            Amf3Decoder.known_classes.append(class_definition)
        else:
            class_definition = Amf3Decoder.known_classes[type]

        typed_object = TypedObject(class_definition.name)
        for i in range(len(class_definition.static_properties)):
            property_name = class_definition.static_properties[i]
            typed_object[property_name] = self.decode()

        if class_definition.encoding == 0x02:
            while True:
                key = self.read_string()
                if key == '' or not key:
                    break
                typed_object[key] = self.decode()

        Amf3Decoder.known_objects.append(typed_object)
        return typed_object

    def read_byte_array(self):
        type = self.read_integer(False)
        if type & 0x01 == 0:
            return Amf3Decoder.known_objects[type >> 1]

        buffer = self.stream.read(type >> 1)
        arr = ByteArray(buffer)
        Amf3Decoder.known_objects.append(arr)
        return arr

    def read_dictionary(self):
        raise NotImplementedError("Amf3 dictionary is not supported")


class Amf3Encoder:
    def __init__(self):
        self.stream = ByteStreamReader()

    def encode(self, obj):
        t = type(obj)
        if obj is None or t is None:
            self.write_null()
        elif t is Amf3Undefined:
            self.write_undefined()
        elif t is bool:
            self.write_boolean(obj)
        elif t is int:
            self.write_integer(obj)
        elif t is float:
            self.write_number(obj)
        elif t is str or issubclass(t, str):
            self.write_string(obj)
        elif t is Amf3Date:
            self.write_date(obj)
        elif t in (list, tuple, set, frozenset):
            self.write_list(obj)
        elif t is TypedObject:
            self.write_object(obj)
        else:
            raise ValueError(f"Unimplemented amf3 encode {t}")

    def write_null(self):
        self.stream.write(TYPE_NULL)

    def write_undefined(self):
        self.stream.write(TYPE_UNDEFINED)

    def write_boolean(self, b):
        if b is True:
            self.stream.write(TYPE_BOOL_TRUE)
        elif b is False:
            self.stream.write(TYPE_BOOL_FALSE)
        else:
            raise ValueError(f"Amf3 bool not true or false {b}")

    def write_integer(self, n):

        if n < MIN_29B_INT or n > MAX_29B_INT:
            self.write_number(float(n))
            return

        self.stream.write(TYPE_INTEGER)
        self.stream.write(encode_int(n))

    def write_number(self, n):
        self.stream.write(TYPE_NUMBER)
        self.stream.write_double(float(n))

    def write_string(self, u: str):
        s = u.encode('utf-8')

        self.stream.write(TYPE_STRING)
        self.stream.write(encode_int((len(s) << 1) | 0x01))
        self.stream.write(s)

    def write_date(self, d: Amf3Date):
        self.stream.write(TYPE_DATE)
        self.stream.write(encode_int(d.ref))    # todo idk if date encode/decode is right
        self.stream.write_double(d.date)

    def write_list(self, n):
        self.stream.write(TYPE_ARRAY)
        self.stream.write(encode_int((len(n) << 1) | 0x01))
        self.stream.write(b'\x01')

        [self.encode(x) for x in n]

    def write_object(self, o: TypedObject):
        self.stream.write(TYPE_OBJECT)

        if o.name is None or o.name == "":
            self.stream.write(b'\x0b')
            self.stream.write(b'\x01')
            for key in o.keys():
                obj = o.get(key)
                s = str(key).encode('utf-8')
                self.stream.write(encode_int((len(s) << 1) | 0x01))
                self.stream.write(s)
                self.encode(obj)
            self.stream.write(b'\x01')
        else:
            self.stream.write(encode_int(len(o) << 4 | 3))
            s = str(o.name).encode('utf-8')
            self.stream.write(encode_int((len(s) << 1) | 0x01))
            self.stream.write(s)
            l = []
            for key in o.keys():
                s = str(key).encode('utf-8')
                self.stream.write(encode_int((len(s) << 1) | 0x01))
                self.stream.write(s)
                l.append(key)
            for k in l:
                obj = o.get(k)
                self.encode(obj)


def encode_int(n):
    global ENCODED_INT_CACHE

    try:
        return ENCODED_INT_CACHE[n]
    except KeyError:
        pass

    if n < MIN_29B_INT or n > MAX_29B_INT:
        raise OverflowError("Out of range")

    if n < 0:
        n += 0x20000000

    data = b''
    real_value = None

    if n > 0x1fffff:
        real_value = n
        n >>= 1
        data += bytes([0x80 | ((n >> 21) & 0xff)])

    if n > 0x3fff:
        data += bytes([0x80 | ((n >> 14) & 0xff)])

    if n > 0x7f:
        data += bytes([0x80 | ((n >> 7) & 0xff)])

    if real_value is not None:
        n = real_value

    if n > 0x1fffff:
        data += bytes([n & 0xff])
    else:
        data += bytes([n & 0x7f])

    ENCODED_INT_CACHE[n] = data

    return data


def decode_int(stream, signed=False):
    n = result = 0
    b = stream.read_uchar()

    while b & 0x80 != 0 and n < 3:
        result <<= 7
        result |= b & 0x7f
        b = stream.read_uchar()
        n += 1

    if n < 3:
        result <<= 7
        result |= b
    else:
        result <<= 8
        result |= b

        if result & 0x10000000 != 0:
            if signed:
                result -= 0x20000000
            else:
                result <<= 1
                result += 1

    return result
