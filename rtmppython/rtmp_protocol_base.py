# Source code taken from rtmpy project (http://rtmpy.org/):
# rtmpy/protocol/handshake.py
# rtmpy/protocol/rtmp/header.py

import time

HANDSHAKE_LENGTH = 1536

class Packet(object):
    """
    A handshake packet.

    @ivar first: The first 4 bytes of the packet, represented as an unsigned
        long.
    @type first: 32bit unsigned int.
    @ivar second: The second 4 bytes of the packet, represented as an unsigned
        long.
    @type second: 32bit unsigned int.
    @ivar payload: A blob of data which makes up the rest of the packet. This
        must be C{HANDSHAKE_LENGTH} - 8 bytes in length.
    @type payload: C{str}
    @ivar timestamp: Timestamp that this packet was created (in milliseconds).
    @type timestamp: C{int}
    """

    first = None
    second = None
    payload = None
    timestamp = None

    def __init__(self, **kwargs):
        timestamp = kwargs.get('timestamp', None)

        if timestamp is None:
            kwargs['timestamp'] = int(time.time())

        self.__dict__.update(kwargs)

    def encode(self, buffer):
        """
        Encodes this packet to a stream.
        """
        buffer.write_ulong(self.first or 0)
        buffer.write_ulong(self.second or 0)

        buffer.write(self.payload)

    def decode(self, buffer):
        """
        Decodes this packet from a stream.
        """
        self.first = buffer.read_ulong()
        self.second = buffer.read_ulong()

        self.payload = buffer.read(HANDSHAKE_LENGTH - 8)

def header_decode(stream):
    """
    Reads a header from the incoming stream.

    A header can be of varying lengths and the properties that get updated
    depend on the length.

    @param stream: The byte stream to read the header from.
    @type stream: C{pyamf.util.BufferedByteStream}
    @return: The read header from the stream.
    @rtype: L{Header}
    """
    # read the size and channelId
    channelId = stream.read_uchar()
    bits = channelId >> 6
    channelId &= 0x3f

    if channelId == 0:
        channelId = stream.read_uchar() + 64

    if channelId == 1:
        channelId = stream.read_uchar() + 64 + (stream.read_uchar() << 8)

    header = Header(channelId)

    if bits == 3:
        return header

    header.timestamp = stream.read_24bit_uint()

    if bits < 2:
        header.bodyLength = stream.read_24bit_uint()
        header.datatype = stream.read_uchar()

    if bits < 1:
        # streamId is little endian
        stream.endian = '<'
        header.streamId = stream.read_ulong()
        stream.endian = '!'

        header.full = True

    if header.timestamp == 0xffffff:
        header.timestamp = stream.read_ulong()

    return header

def header_encode(stream, header, previous=None):
    """
    Encodes a RTMP header to C{stream}.

    We expect the stream to already be in network endian mode.

    The channel id can be encoded in up to 3 bytes. The first byte is special as
    it contains the size of the rest of the header as described in
    L{getHeaderSize}.

    0 >= channelId > 64: channelId
    64 >= channelId > 320: 0, channelId - 64
    320 >= channelId > 0xffff + 64: 1, channelId - 64 (written as 2 byte int)

    @param stream: The stream to write the encoded header.
    @type stream: L{util.BufferedByteStream}
    @param header: The L{Header} to encode.
    @param previous: The previous header (if any).
    """
    if previous is None:
        size = 0
    else:
        size = min_bytes_required(header, previous)

    channelId = header.channelId

    if channelId < 64:
        stream.write_uchar(size | channelId)
    elif channelId < 320:
        stream.write_uchar(size)
        stream.write_uchar(channelId - 64)
    else:
        channelId -= 64

        stream.write_uchar(size + 1)
        stream.write_uchar(channelId & 0xff)
        stream.write_uchar(channelId >> 0x08)

    if size == 0xc0:
        return

    if size <= 0x80:
        if header.timestamp >= 0xffffff:
            stream.write_24bit_uint(0xffffff)
        else:
            stream.write_24bit_uint(header.timestamp)

    if size <= 0x40:
        stream.write_24bit_uint(header.bodyLength)
        stream.write_uchar(header.datatype)

    if size == 0:
        stream.endian = '<'
        stream.write_ulong(header.streamId)
        stream.endian = '!'

    if size <= 0x80:
        if header.timestamp >= 0xffffff:
            stream.write_ulong(header.timestamp)

class Header(object):
    """
    An RTMP Header. Holds contextual information for an RTMP Channel.
    """

    __slots__ = ('streamId', 'datatype', 'timestamp', 'bodyLength',
        'channelId', 'full')

    def __init__(self, channelId, timestamp=-1, datatype=-1,
                 bodyLength=-1, streamId=-1, full=False):
        self.channelId = channelId
        self.timestamp = timestamp
        self.datatype = datatype
        self.bodyLength = bodyLength
        self.streamId = streamId
        self.full = full

    def __repr__(self):
        attrs = []

        for k in self.__slots__:
            v = getattr(self, k, None)

            if v == -1:
                v = None

            attrs.append('%s=%r' % (k, v))

        return '<%s.%s %s at 0x%x>' % (
            self.__class__.__module__,
            self.__class__.__name__,
            ' '.join(attrs),
            id(self))

def min_bytes_required(old, new):
    """
    Returns the number of bytes needed to de/encode the header based on the
    differences between the two.

    Both headers must be from the same channel.

    @type old: L{Header}
    @type new: L{Header}
    """
    if old is new:
        return 0xc0

    if old.channelId != new.channelId:
        raise HeaderError('channelId mismatch on diff old=%r, new=%r' % (
            old, new))

    if old.streamId != new.streamId:
        return 0 # full header

    if old.datatype == new.datatype and old.bodyLength == new.bodyLength:
        if old.timestamp == new.timestamp:
            return 0xc0

        return 0x80

    return 0x40
