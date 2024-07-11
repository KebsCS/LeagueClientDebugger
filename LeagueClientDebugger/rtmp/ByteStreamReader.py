import struct

SYSTEM_ENDIAN = None


class ByteStreamReader:
    #: Network byte order
    ENDIAN_NETWORK = "!"

    #: Native byte order
    ENDIAN_NATIVE = "@"

    #: Little endian
    ENDIAN_LITTLE = "<"

    #: Big endian
    ENDIAN_BIG = ">"

    __endian = ENDIAN_NETWORK

    @property
    def endian(self):
        return self.__endian

    @endian.setter
    def endian(self, value):
        self.__endian = value.decode('utf-8') if isinstance(value, bytes) else value

    def _is_big_endian(self):
        if self.endian == ByteStreamReader.ENDIAN_NATIVE:
            return SYSTEM_ENDIAN == ByteStreamReader.ENDIAN_BIG

        return self.endian in (
            ByteStreamReader.ENDIAN_BIG,
            ByteStreamReader.ENDIAN_NETWORK
        )

    def __init__(self, data=b''):
        self.data = data
        self.offset = 0

    def __len__(self):
        return len(self.data)

    def at_eof(self):
        return self.offset == len(self.data)

    def append(self, data: bytes):
        self.data += data

    def write(self, data: bytes):
        self.append(data)

    def remove_already_read(self):
        self.data = self.data[self.offset:]
        self.offset = 0

    def peek(self, length=1):
        return self.data[self.offset:self.offset + length]

    def read(self, length):
        chunk = self.data[self.offset:self.offset + length]
        self.offset += length
        return chunk

    def read_uchar(self):
        return ord(self.read(1))

    def write_uchar(self, c):
        if type(c) != int:
            raise TypeError('expected an int (got:%r)' % type(c))

        if not 0 <= c <= 255:
            raise OverflowError("Not in range, %d" % c)

        self.write(struct.pack("B", c))

    def read_char(self):
        """
        Reads a C{char} from the stream.
        """
        return struct.unpack("b", self.read(1))[0]

    def write_char(self, c):
        if type(c) != int:
            raise TypeError('expected an int (got:%r)' % type(c))

        if not -128 <= c <= 127:
            raise OverflowError("Not in range, %d" % c)

        self.write(struct.pack("b", c))

    def read_ushort(self):
        return struct.unpack("%sH" % self.endian, self.read(2))[0]

    def write_ushort(self, s):
        if type(s) != int:
            raise TypeError('expected an int (got:%r)' % (type(s),))

        if not 0 <= s <= 65535:
            raise OverflowError("Not in range, %d" % s)

        self.write(struct.pack("%sH" % self.endian, s))

    def read_short(self):
        return struct.unpack("%sh" % self.endian, self.read(2))[0]

    def write_short(self, s):
        if type(s) != int:
            raise TypeError('expected an int (got:%r)' % (type(s),))

        if not -32768 <= s <= 32767:
            raise OverflowError("Not in range, %d" % s)

        self.write(struct.pack("%sh" % self.endian, s))

    def read_ulong(self):
        return struct.unpack("%sL" % self.endian, self.read(4))[0]

    def write_ulong(self, l):
        if type(l) != int:
            raise TypeError('expected an int (got:%r)' % (type(l),))

        if not 0 <= l <= 4294967295:
            raise OverflowError("Not in range, %d" % l)

        self.write(struct.pack("%sL" % self.endian, l))

    def read_long(self):
        return struct.unpack("%sl" % self.endian, self.read(4))[0]

    def write_long(self, l):
        if type(l) != int:
            raise TypeError('expected an int (got:%r)' % (type(l),))

        if not -2147483648 <= l <= 2147483647:
            raise OverflowError("Not in range, %d" % l)

        self.write(struct.pack("%sl" % self.endian, l))

    def read_24bit_uint(self):
        order = None

        if not self._is_big_endian():
            order = [0, 8, 16]
        else:
            order = [16, 8, 0]

        n = 0

        for x in order:
            n += (self.read_uchar() << x)

        return n

    def write_24bit_uint(self, n):
        if type(n) != int:
            raise TypeError('expected an int (got:%r)' % (type(n),))

        if not 0 <= n <= 0xffffff:
            raise OverflowError("n is out of range")

        order = None

        if not self._is_big_endian():
            order = [0, 8, 16]
        else:
            order = [16, 8, 0]

        for x in order:
            self.write_uchar((n >> x) & 0xff)

    def read_24bit_int(self):
        n = self.read_24bit_uint()

        if n & 0x800000 != 0:
            # the int is signed
            n -= 0x1000000

        return n

    def write_24bit_int(self, n):
        if type(n) != int:
            raise TypeError('expected an int (got:%r)' % (type(n),))

        if not -8388608 <= n <= 8388607:
            raise OverflowError("n is out of range")

        order = None

        if not self._is_big_endian():
            order = [0, 8, 16]
        else:
            order = [16, 8, 0]

        if n < 0:
            n += 0x1000000

        for x in order:
            self.write_uchar((n >> x) & 0xff)

    def read_double(self):
        return struct.unpack("%sd" % self.endian, self.read(8))[0]

    def write_double(self, d):
        if not type(d) is float:
            raise TypeError('expected a float (got:%r)' % (type(d),))

        self.write(struct.pack("%sd" % self.endian, d))

    def read_float(self):
        return struct.unpack("%sf" % self.endian, self.read(4))[0]

    def write_float(self, f):
        if type(f) is not float:
            raise TypeError('expected a float (got:%r)' % (type(f),))

        self.write(struct.pack("%sf" % self.endian, f))

    def read_utf8_string(self, length):
        s = struct.unpack("%s%ds" % (
            self.endian, length),
                          self.read(length)
                          )

        return s[0].decode('utf-8')

    def write_utf8_string(self, u):
        if not isinstance(u, tuple([str, bytes])):
            raise TypeError('Expected %r, got %r' % (tuple([str, bytes]), u))

        bytes = u

        if isinstance(bytes, str):
            bytes = u.encode("utf8")

        self.write(struct.pack("%s%ds" % (self.endian, len(bytes)), bytes))

if struct.pack('@H', 1)[0] == '\x01':
    SYSTEM_ENDIAN = ByteStreamReader.ENDIAN_LITTLE
else:
    SYSTEM_ENDIAN = ByteStreamReader.ENDIAN_BIG