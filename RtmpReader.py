from pyamf import amf0,remoting,amf3, util
from pyamf import *
from rtmplite3 import *
from  RtmpHelpers import *

class RtmpReader:

    rtmpHeaders = {}
    rtmpPackets = {}
    Continue = True
    DefaultChunkSize = 128
    readChunkSize = DefaultChunkSize

    def __init__(self, reader):
        self.reader = reader

    def GetChunkStreamId(self, chunkBasicHeaderByte):
        chunkStreamId = chunkBasicHeaderByte & 0x3F
        # 2 bytes
        if chunkStreamId == 0:
            return self.reader.read_uchar() + 64

        # 3 bytes
        if chunkStreamId == 1:
            return self.reader.read_uchar() + self.reader.read_uchar() * 256 + 64

        return chunkStreamId

    def ReadHeader(self) -> RtmpHeader:
        chunkBasicHeaderByte = self.reader.read_uchar()
        chunkStreamId = self.GetChunkStreamId(chunkBasicHeaderByte)
        # 0 - New, 1 - SameSource, 2 - TimestampAdjustment, 3 - Continuation
        chunkMessageHeaderType = chunkBasicHeaderByte >> 6
        header = RtmpHeader()
        header.StreamId = chunkStreamId
        header.IsTimerRelative = True if chunkMessageHeaderType != ChunkMessageHeaderType.New else False

        previousHeader = RtmpHeader
        if str(chunkStreamId) in self.rtmpHeaders and chunkMessageHeaderType != ChunkMessageHeaderType.New:
            previousHeader = header

        # 11 bytes
        if chunkMessageHeaderType == ChunkMessageHeaderType.New:
            header.Timestamp = self.reader.read_24bit_uint()
            header.PacketLength = self.reader.read_24bit_uint()
            header.MessageType = self.reader.read_uchar()
            self.reader.endian = '<'
            header.MessageStreamId = self.reader.read_long()
            self.reader.endian = '!'

        # 7 bytes
        elif chunkMessageHeaderType == ChunkMessageHeaderType.SameSource:
            header.Timestamp = self.reader.read_24bit_uint()
            header.PacketLength = self.reader.read_24bit_uint()
            header.MessageType = self.reader.read_uchar()
            header.MessageStreamId = previousHeader.MessageStreamId
        # 3 bytes
        elif chunkMessageHeaderType == ChunkMessageHeaderType.TimestampAdjustment:
            header.Timestamp = self.reader.read_24bit_uint()
            header.PacketLength = previousHeader.PacketLength
            header.MessageType = previousHeader.MessageType
            header.MessageStreamId = previousHeader.MessageStreamId
        # 0 bytes
        elif chunkMessageHeaderType == ChunkMessageHeaderType.Continuation:
            header.Timestamp = previousHeader.Timestamp
            header.PacketLength = previousHeader.PacketLength
            header.MessageType = previousHeader.MessageType
            header.MessageStreamId = previousHeader.MessageStreamId
        else:
            raise Exception("Sorry, no numbers below zero")

        if header.Timestamp == 0xFFFFFF:
            header.Timestamp = self.reader.read_long()
        return header

    def ParsePacket(self, packet: RtmpPacket) -> RtmpEvent:
        if packet.Header.MessageType == DataTypes.SET_CHUNK_SIZE:
            pass


    def next(self):
        header = self.ReadHeader()
        self.rtmpHeaders[str(header.StreamId)] = header

        packet = None
        if str(header.StreamId) in self.rtmpPackets or packet == None:
            packet = RtmpPacket(header)
            self.rtmpPackets[str(header.StreamId)] = packet


        remainingMessageLength = packet.Length + (4 if header.Timestamp >= 0xFFFFFF else 0) - packet.CurrentLength
        bytesToRead = min(remainingMessageLength, self.readChunkSize)
        bytes = self.reader._read(bytesToRead)
        packet.AddBytes(bytes)

        if packet.IsComplete():
            del self.rtmpPackets[str(header.StreamId)]






