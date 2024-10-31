import asyncio, ssl, copy, gzip, base64, datetime
from UiObjects import *
from rtmp.ByteStreamReader import ByteStreamReader
from rtmp.Amf0 import Amf0Decoder, Amf0Encoder, Amf0Amf3
from rtmp.Amf3 import Amf3Undefined


class CustomJSONEncoder(json.JSONEncoder):
    def _convert_to_json(self, obj):
        if hasattr(obj, 'to_json'):
            return self._convert_to_json(obj.to_json())
        elif isinstance(obj, dict):
            return {key: self._convert_to_json(value) for key, value in obj.items()}
        elif isinstance(obj, list):
            return [self._convert_to_json(item) for item in obj]
        else:
            return obj

    def default(self, obj):
        return super().default(self._convert_to_json(obj))

    def encode(self, obj):
        return super(CustomJSONEncoder, self).encode(self._convert_to_json(obj))


def log_message(message, is_outgoing):
    #print('[RTMP] ' + ('>' if is_outgoing else '<') + " " + str(message))

    current_time = datetime.datetime.now().strftime("%H:%M:%S")
    text = f"[{current_time}] "
    text += "[OUT] " if is_outgoing else "[IN]     "

    item = QListWidgetItem()
    if isinstance(message, dict):
        json_msg = json.loads(json.dumps(message, cls=CustomJSONEncoder))
        invoke_id = json_msg.get("invokeId", "") or ""
        text += f"{invoke_id} "

        if "data" in json_msg:
            messaging = json_msg["data"].get("__class", "") or ""
            messaging = messaging.split('.')[-1].replace("Message", "").replace("Acknowledge", "Ack")
            destination = json_msg["data"].get("destination", "") or ""
            operation = json_msg["data"].get("operation", "") or ""
            text += f"{messaging} {destination} {operation}"

        item.setText(text)
        item.setData(256, json.dumps(json_msg, indent=4))
    else:
        item.setText(text + "handshake" if isinstance(message, bytes) else "")
        item.setData(256, str(message))

    scrollbar = UiObjects.rtmpList.verticalScrollBar()
    if not scrollbar or scrollbar.value() == scrollbar.maximum():
        UiObjects.rtmpList.addItem(item)
        UiObjects.rtmpList.scrollToBottom()
    else:
        UiObjects.rtmpList.addItem(item)


class RTMPHeader:
    first_byte = None
    chunk_header_type = None
    chunk_stream_id = None

    timestamp = None
    message_length = 0
    message_type_id = None
    message_stream_id = None


class RtmpPacket:
    def __init__(self, header=RTMPHeader(), buffer=b'', length=0):
        self.header = header
        self.buffer = buffer
        self.length = length


class RtmpParser:
    CHUNK_SIZE = 128
    handshake_counter = 0

    unfinished_packet = None

    def __init__(self, parent):
        self.parent = parent

        self.stream = ByteStreamReader()
        self.packets = dict()

    def read_header(self) -> RTMPHeader:
        header = RTMPHeader()
        header.first_byte = self.stream.read_uchar()
        header.chunk_header_type = (header.first_byte >> 6) & 0b11    # first 2 bits
        header.chunk_stream_id = header.first_byte & 0b00111111   #  bits 0-5 (least significant) represent the chunk stream ID

        if header.chunk_header_type == 0x00:   # chunk header type 0
            header.timestamp = self.stream.read(3)
            header.message_length = self.stream.read_24bit_uint()
            header.message_type_id = self.stream.read_uchar()
            header.message_stream_id = self.stream.read(4)
        elif header.chunk_header_type == 0x01: # type 1
            header.timestamp = self.stream.read(3)
            header.message_length = self.stream.read_24bit_uint()
            header.message_type_id = self.stream.read_uchar()
        elif header.chunk_header_type == 0x02: # type 2
            header.timestamp = self.stream.read(3)
        elif header.chunk_header_type == 0x03: # type 3
            pass    # no message header
        else:
            raise Exception("[RTMP] Unknown chunk header type")

        return header

    def feed_data(self, data):
        if RtmpParser.handshake_counter < 6:
            RtmpParser.handshake_counter += 1
            if hasattr(self.parent, 'on_message_parsed'):
                self.parent.on_message_parsed(data)
            return
        elif RtmpParser.handshake_counter == 6:
            RtmpParser.handshake_counter += 1
            self.stream = ByteStreamReader()
            self.packets = dict()

        self.stream.append(data)

        while not self.stream.at_eof():
            if self.unfinished_packet is None:
                header = self.read_header()
                if str(header.chunk_stream_id) not in self.packets:
                    packet = RtmpPacket(header, b'', header.message_length)
                    self.packets[str(header.chunk_stream_id)] = packet
                else:
                    packet = self.packets[str(header.chunk_stream_id)]
            else:
                packet = self.unfinished_packet
                self.unfinished_packet = None

            read_len = min(self.CHUNK_SIZE, packet.length)
            if read_len > len(self.stream.data) - self.stream.offset:
                # not enough bytes received
                self.unfinished_packet = packet
                return
            packet.buffer += self.stream.read(read_len)
            packet.length -= read_len
            if packet.length == 0:
                self.handle_packet(packet)
                del self.packets[str(packet.header.chunk_stream_id)]
                self.stream.remove_already_read()

    def handle_packet(self, packet: RtmpPacket):
        obj = None
        if packet.header.chunk_header_type == 0x00:
            if packet.header.message_type_id == 0x14 or packet.header.message_type_id == 0x11:  # AMF0 or AMF3 Command Message
                obj = dict()
                decoder = Amf0Decoder(packet.buffer)
                if ord(decoder.stream.peek(1)) == 0x00:
                    obj["version"] = 0x00
                    decoder.stream.read(1)
                obj["result"] = decoder.decode()
                obj["invokeId"] = decoder.decode()
                obj["serviceCall"] = decoder.decode()
                obj["data"] = decoder.decode()
                #print(json.dumps(obj, indent=4))

                # mitm example - revealing names in champion select
                def mitm():
                    if type(obj["data"]) is Amf0Amf3:
                        data = obj["data"].value
                    elif isinstance(obj["data"], dict):
                        data = obj["data"]
                    else:
                        return
                    if isinstance(data, dict) and "body" in data:
                        if isinstance(data["body"], dict):
                            body = data["body"]
                        elif isinstance(data["body"], list) and len(data["body"]) != 0:
                            if isinstance(data["body"][0], dict):
                                body = data["body"][0]
                            else:
                                return
                        else:
                            return

                        payload = None
                        is_compressed = False
                        if "compressedPayload" in body and body["compressedPayload"] is True:
                            is_compressed = True
                            payload = body["payload"]
                            payload = gzip.decompress(base64.b64decode(payload.encode("utf-8")))
                        elif "payload" in body and body["payload"]:
                            payload = body["payload"]
                        if payload:
                            payload = json.loads(payload.decode('utf-8') if type(payload) is bytes else payload)

                            # reveal
                            if "queueId" in payload and payload["queueId"] == 420:  # soloq
                                if "championSelectState" in payload:
                                    for cell in payload["championSelectState"]["cells"]["alliedTeam"]:
                                        if "nameVisibilityType" in cell and cell["nameVisibilityType"] != "UNHIDDEN":
                                            cell["nameVisibilityType"] = "UNHIDDEN"
                            if is_compressed:
                                payload = base64.b64encode(gzip.compress(json.dumps(payload).encode('utf-8'))).decode('utf-8')
                            body["payload"] = payload

                # mitm()

                # Uncomment if you make any changes to the packets
                # Encoding slows down the client a bit, and it's not necessary

                # try:
                #     encoder = Amf0Encoder()
                #     if "version" in obj:
                #         encoder.stream.write_uchar(obj["version"])
                #     encoder.encode(obj["result"])
                #     encoder.encode(obj["invokeId"])
                #     encoder.encode(obj["serviceCall"])
                #     encoder.encode(obj["data"])
                #     new_packet = RtmpPacket(copy.deepcopy(packet.header), packet.buffer[:], 0)
                #     new_packet.buffer = encoder.stream.data
                #     new_packet.header.message_length = len(new_packet.buffer)
                #
                #     packet = new_packet
                # except Exception as e:
                #     print(f"Amf encode error: {e}")
                #     print(f"Handled packet: {packet.buffer}")


            elif packet.header.message_type_id == 0x01:     # Set Chunk Size
                pass #etc todo
            else:
                print("[RTMP] not amf3 or amf0")
                pass
                #raise Exception("[RTMP] Unhandled message type")
        else:
            pass
        self.write_packet(packet, obj)

    def write_packet(self, packet: RtmpPacket, decoded_obj=None):
        output = self.write_header(packet.header)

        packet_len = len(packet.buffer)
        for i in range(0, packet_len):
            output.append(packet.buffer[i:i+1])

            if i % 128 == 127 and i != packet_len - 1:
                output.append(b'\xc3')

        if hasattr(self.parent, 'on_message_parsed'):
            self.parent.on_message_parsed(output.data, decoded_obj)
            #print(output.data)

    def write_header(self, header: RTMPHeader) -> ByteStreamReader:
        output = ByteStreamReader()
        output.write_uchar(header.first_byte)
        if header.chunk_header_type == 0x00:  # chunk header type 0
            output.write(header.timestamp)
            output.write_24bit_uint(header.message_length)
            output.write_uchar(header.message_type_id)
            output.write(header.message_stream_id)
        elif header.chunk_header_type == 0x01:  # type 1
            output.write(header.timestamp)
            output.write_24bit_uint(header.message_length)
            output.write_uchar(header.message_type_id)
        elif header.chunk_header_type == 0x02:  # type 2
            output.write(header.timestamp)
        elif header.chunk_header_type == 0x03:  # type 3
            pass  # no message header
        else:
            raise Exception("[RTMP] Unknown chunk header type")

        return output


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
            self.parser = RtmpParser(self)

        self.parser.feed_data(data)

    def on_message_parsed(self, msg, decoded_obj=None):
        log_message(decoded_obj if decoded_obj else msg, False)
        self.league_client.write(msg)

    def connection_lost(self, exc):
        print('[RTMP] Connection lost with riot server', exc)

        self.league_client.close()
        self.on_con_lost.set_result(True)

        UiObjects.add_disconnected_item(UiObjects.rtmpList)
        RtmpParser.handshake_counter = 0


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

            UiObjects.add_connected_item(UiObjects.rtmpList)

        def connection_lost(self, exc):
            print('[RTMP] Connection lost with league client', exc)

            if self.is_connected:
                self.real_server.close()
                self.is_connected = False

        def data_received(self, data):
            #print(f'[RTMP] > {data}')

            if self.parser is None:
                self.parser = RtmpParser(self)

            self.parser.feed_data(data)

        def on_message_parsed(self, msg, decoded_obj=None):
            log_message(decoded_obj if decoded_obj else msg, True)
            if self.is_connected:
                self.real_server.write(msg)
            else:
                asyncio.ensure_future(
                    self.connect_to_real_server(self.real_host, self.real_port, self.league_client, msg))

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

        print(f'[RTMP] {real_host} server started on {proxy_host}:{proxy_port}')

        async with server:
            await server.serve_forever()
