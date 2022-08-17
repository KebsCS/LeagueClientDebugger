from enum import IntEnum

class DataTypes:
    NONE = -1
    SET_CHUNK_SIZE = 1
    ABORT_MESSAGE = 2
    ACKNOWLEDGEMENT = 3
    USER_CONTROL = 4
    WINDOW_ACK_SIZE = 5
    SET_PEER_BANDWIDTH = 6

    AUDIO = 8
    VIDEO = 9

    DATA_AMF3 = 15
    SHARED_OBJECT_AMF3 = 16
    COMMAND_AMF3 = 17

    DATA_AMF0 = 18
    SHARED_OBJECT_AMF0 = 19
    COMMAND_AMF0 = 20

    AGGREGATE = 22

class RtmpHeader:
    PacketLength = 0
    StreamId = 0
    MessageType = 0
    MessageStreamId = 0
    Timestamp = 0
    IsTimerRelative = False

    def GetHeaderLength(self, chunkMessageHeaderType):
        if chunkMessageHeaderType == 0:
            return 11
        elif chunkMessageHeaderType == 1:
            return 7
        elif chunkMessageHeaderType == 2:
            return 3
        elif chunkMessageHeaderType == 3:
            return 0
        else:
            return -1

class ChunkMessageHeaderType(IntEnum):
    New = 0
    SameSource = 1
    TimestampAdjustment = 2
    Continuation = 3

class RtmpEvent:
    Header = RtmpHeader
    Timestamp = 0
    MessageType = 0

    def __init__(self, messageType):
        self.MessageType = messageType

class RtmpPacket:
    Header = RtmpHeader
    Body = RtmpEvent
    Buffer = b''
    Length = 0
    CurrentLength = 0
    def IsComplete(self):
        return self.Length == self.CurrentLength
    def __init__(self, header: RtmpHeader):
        self.Header = header
        self.Length = header.PacketLength

    def AddBytes(self, bytes):
        self.Buffer += bytes
        self.CurrentLength += len(bytes)