import asyncio, ssl, pyamf, datetime
import pyamf.flex
import pyamf.amf0
from pyamf.flex import messaging
from UiObjects import *

from json import JSONEncoder

def _default(self, obj):
    if isinstance(obj, datetime.datetime):
        return obj.strftime('%Y-%m-%dT%H:%M:%S.%f')
    return getattr(obj.__class__, "to_json", _default.default)(obj)

_default.default = JSONEncoder().default
JSONEncoder.default = _default

# League client is connected to ProtocolFromClient proxy server
# League Client Messages -> ProtocolFromClient -> parser -> Sends to Riot server
# ProtocolFromServer is a client connected to riot server, it receives messages and sends them to real league client
# Riot Server Messages -> ProtocolFromServer -> parser -> Sends to League client


def typed_object_repr(self):
    def format_datetime(dt):
        # if isinstance(dt, datetime.datetime):
        #     return dt.strftime('%Y-%m-%dT%H:%M:%S.%f')
        # else:
        return dt

    self["__class"] = str(self.alias)
    for key, value in self.items():
        self[key] = format_datetime(value)

    return dict.__repr__(self)

pyamf.TypedObject.__repr__ = typed_object_repr

def typed_object_init(self, alias):
    dict.__init__(self)

    self.alias = alias
    self["__class"] = alias

pyamf.TypedObject.__init__ = typed_object_init

# flex.messaging.io.ArrayCollection crashes
pyamf.unregister_class("flex.messaging.io.ArrayCollection")


def undefined_type_repr(self):
    return "'AMF3_UNDEFINED'"

def undefined_type_to_json(self):
    return "AMF3_UNDEFINED"


pyamf.UndefinedType.__repr__ = undefined_type_repr
pyamf.UndefinedType.to_json = undefined_type_to_json


def abstract_message_to_json(self):
    def format_datetime(dt):
        # if isinstance(dt, datetime.datetime):
        #     return dt.strftime('%Y-%m-%dT%H:%M:%S.%f')
        # else:
        return dt

    attrs = {k: format_datetime(getattr(self, k)) for k in self.__dict__}
    attrs['__class'] = "flex.messaging.messages." + self.__class__.__name__
    return attrs


def abstract_message_repr(self):
    return repr(abstract_message_to_json(self))


pyamf.flex.messaging.AbstractMessage.__repr__ = abstract_message_repr
pyamf.flex.messaging.AbstractMessage.to_json = abstract_message_to_json


def log_message(parser, is_outgoing):
    current_message = parser.current_message_parsed if parser.current_message_parsed else str(
        parser.current_message)

    #print('[RTMP] ' + ('>' if is_outgoing else '<') + " " + str(parser.current_message))

    current_time = datetime.datetime.now().strftime("%H:%M:%S")
    text = f"[{current_time}] "
    text += "[OUT] " if is_outgoing else "[IN]     "

    if parser.current_message_parsed:
        item = QListWidgetItem()

        json_msg = json.loads(json.dumps(current_message))
        invoke_id = json_msg.get("invokeId", "") or ""
        text += f"{invoke_id} "

        if "data" in json_msg:
            messaging = json_msg["data"].get("__class", "") or ""
            messaging = messaging.split('.')[-1].replace("Message", "").replace("Acknowledge", "Ack")
            destination = json_msg["data"].get("destination", "") or ""
            operation = json_msg["data"].get("operation", "") or ""
            text += f"{messaging} {destination} {operation}"

        item.setText(text)
        item.setData(256, json.dumps(current_message, indent=4))

        UiObjects.rtmpList.addItem(item)
    else:
        item = QListWidgetItem()
        item.setText(text)
        item.setData(256, str(parser.current_message))
        UiObjects.rtmpList.addItem(item)


class RtmpParser:
    CHUNK_SIZE = 128

    counter = 0

    def __init__(self):
        self.stream = pyamf.util.BufferedByteStream()
        self.decoder = pyamf.amf0.Decoder(stream=self.stream)

        self.received_new_message = True
        self.packet_length = 0

        self.all_data = b''  # all data that was received and not parsed yet

        self.current_message = b''  # currently parsed message, send it after parsing - when feed_data returns true
        self.current_message_parsed = dict()

    # returns true when succeeded and the self.current_message bytes can be sent to client/server
    def feed_data(self, data):
        if RtmpParser.counter < 6 and data != b'':  # first 6 are handshake and connect
            # todo, also decode handshake https://rtmp.veriskope.com/docs/spec/#7211connect
            RtmpParser.counter += 1
            self.current_message = data
            return True

        self.all_data += data

        if self.all_data == b'':
            return False

        if self.received_new_message:
            # first 12 bytes are header
            self.decoder.stream.append(self.all_data[:12])

            self.received_new_message = False
            self.current_message_parsed = dict()
            self.current_message = b''
            self.current_message += self.all_data[:12]

            chunk_header_type = self.decoder.stream.read(1)
            timestamp_delta = self.decoder.stream.read(3)
            self.packet_length = self.decoder.stream.read_24bit_uint()
            message_type_id = self.decoder.stream.read(1)
            message_stream_id = self.decoder.stream.read(4)

            self.all_data = self.all_data[12:]

        # messages are supposed to be sent in a chunks of 128 bytes
        # after every chunk theres a 0xc3 byte, in this implementation
        # it sometimes receives too little or too much bytes, so it has to
        # step by 128 and remove the 0xc3 and check if packet length is correct
        rtmp_message = self.all_data
        i = 0
        removed = 0  # number of removed 0xc3
        new_rtmp_message = bytearray()
        while i < min(len(rtmp_message), self.packet_length + removed):
            if i + RtmpParser.CHUNK_SIZE < min(len(rtmp_message), self.packet_length + removed):
                new_rtmp_message.extend(rtmp_message[i:i + RtmpParser.CHUNK_SIZE])
                # check if the next byte after the chunk is 0xc3
                if rtmp_message[i + RtmpParser.CHUNK_SIZE] == 0xc3:
                    i += 1
                    removed += 1
                # next chunk
                i += RtmpParser.CHUNK_SIZE
            else:
                # append the remaining bytes
                new_rtmp_message.extend(rtmp_message[i:min(len(rtmp_message), self.packet_length + removed)])
                break

        new_rtmp_message = bytes(new_rtmp_message)
        if self.packet_length > len(new_rtmp_message):  # haven't received enough bytes
            return False
        elif self.packet_length == len(new_rtmp_message):
            self.all_data = rtmp_message[self.packet_length + removed:]
        else:
            raise IndexError("[RTMP] Packet length is smaller than parsed message")

        self.decoder.stream.append(new_rtmp_message)
        self.current_message += rtmp_message[:self.packet_length + removed]

        obj = dict()
        if self.decoder.stream.peek(1) == b'\x00':
            obj["version"] = 0x00
            self.decoder.stream.read(1)

        try:
            obj["result"] = self.decoder.readElement()
            obj["invokeId"] = self.decoder.readElement()
            obj["serviceCall"] = self.decoder.readElement()
            obj["data"] = self.decoder.readElement()
        except Exception as e:
            print("[RTMP] Failed to parse rtmp message", e)

        if not self.decoder.stream.at_eof():
            print("[RTMP] Parsing failed, decoder not at eof")
            self.decoder.stream.read(self.decoder.stream.remaining())
        else:
            self.current_message_parsed = obj

        self.received_new_message = True
        return True


class ProtocolFromServer(asyncio.Protocol):

    def __init__(self, on_con_lost, league_client, first_req):
        self.on_con_lost = on_con_lost

        self.real_server = None
        self.league_client = league_client
        self.first_req = first_req

        self.parser = None

    def connection_made(self, transport):
        self.real_server = transport
        peername = transport.get_extra_info('peername')
        print(f'[RTMP] Client connected to real riot server {peername}')

        # connection is made after the first message was already sent
        self.real_server.write(self.first_req)

    def data_received(self, data):
        #print(f'[RTMP] < {data}')

        if self.parser is None:
            self.parser = RtmpParser()

        while self.parser.feed_data(data):
            log_message(self.parser, False)

            self.league_client.write(self.parser.current_message)

            data = b''

    def connection_lost(self, exc):
        print('[RTMP] Connection lost with riot server', exc)

        self.league_client.close()
        self.on_con_lost.set_result(True)

        UiObjects.add_disconnected_item(UiObjects.rtmpList)


class RtmpProxy:
    class ProtocolFromClient(asyncio.Protocol):

        def __init__(self, real_host, real_port):
            self.is_connected = False

            self.real_host = real_host  # feapp.euw1.lol.pvp.net
            self.real_port = real_port  # 2099

            self.real_server = None
            self.league_client = None

            self.parser = None

        def connection_made(self, transport):
            self.league_client = transport
            peername = self.league_client.get_extra_info('peername')
            print(f'[RTMP] League client connected to proxy {peername}')
            RtmpParser.counter = 0

            UiObjects.add_connected_item(UiObjects.rtmpList)

        def connection_lost(self, exc):
            print('[RTMP] Connection lost with league client', exc)

            if self.is_connected:
                self.real_server.close()
                self.is_connected = False

        def data_received(self, data):
            #print(f'[RTMP] > {data}')

            if self.parser is None:
                self.parser = RtmpParser()

            # while loop because there still might be some unsent data left
            while self.parser.feed_data(data):
                log_message(self.parser, True)
                if self.is_connected:
                    self.real_server.write(self.parser.current_message)
                else:
                    asyncio.ensure_future(
                        self.connect_to_real_server(self.real_host, self.real_port, self.league_client, data))
                data = b''

        async def connect_to_real_server(self, real_host, real_port, league_client, first_req):
            loop = asyncio.get_event_loop()
            on_con_lost = loop.create_future()

            transport, protocol = await loop.create_connection(
                lambda: ProtocolFromServer(on_con_lost, league_client, first_req),
                real_host, real_port, ssl=ssl.SSLContext(protocol=ssl.PROTOCOL_TLSv1_2))

            self.real_server = transport
            self.is_connected = True

            try:
                await on_con_lost
            finally:
                self.real_server.close()

    async def start_client_proxy(self, proxy_host, proxy_port, real_host, real_port):
        loop = asyncio.get_running_loop()

        server = await loop.create_server(
            lambda: self.ProtocolFromClient(real_host, real_port),
            proxy_host, proxy_port)

        print(f'[RTMP] Proxy server started on {proxy_host}:{proxy_port}')

        async with server:
            await server.serve_forever()
