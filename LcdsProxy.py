import asyncio, ssl, pyamf
from pyamf import remoting
from pyamf.remoting import *
from pyamf import amf0


def my_read(self, n=-1):
    """
    Reads C{n} bytes from the stream.
    """
    if n < -1:
        raise IOError('Cannot read backwards')

    # bytes = self._buffer.read(n)
    buffer = b""
    while n != 0:
        byte = self._buffer.read(1)
        if byte == b'\xc3':    # no idea why client adds c3 randomly
            byte = self._buffer.read(1)
        if not byte:
            break
        buffer += byte
        n -= 1

    return buffer


pyamf.remoting.util.pure.BytesIOProxy.read = my_read


class TypedObject(dict):
    def __init__(self, *arg, **kw):
        super(TypedObject, self).__init__(*arg, **kw)

counter = 0
def decode(data):
    global counter
    counter += 1
    if counter > 6:
        try:
            stream = pyamf.util.BufferedByteStream(data)

            decoder = pyamf.amf0.Decoder(stream=stream)
            context = decoder.context

            obj = TypedObject()
            if decoder.stream.peek(1) == b'\x00':
                obj["version"] = 0x00
                decoder.stream.read(1)

            obj["result"] = decoder.readElement()
            obj["invokeId"] = decoder.readElement()
            obj["serviceCall"] = decoder.readElement()
            obj["data"] = decoder.readElement()
            print(obj)
            if stream.at_eof():
                print("at end")
        except:
            print("failed")

# Proxy server
class ProtocolToServer(asyncio.Protocol):

    def __init__(self, on_con_lost, client, firstReq):
        self.on_con_lost = on_con_lost
        self.client = client
        self.firstReq = firstReq

    def connection_made(self, transport):
        peername = transport.get_extra_info('peername')
        print(f'[LcdsToServer] Connected {peername}')
        self.transport = transport

        # connection is made after the first request was already sent
        transport.write(self.firstReq)

    def data_received(self, data):
        formatted_bytes = ", ".join([f"0x{byte:02X}" for byte in data[12:]])
        print(f'[LcdsToServer] Received: received {formatted_bytes}')
        print(data)

        # todo, if request is too long it sends it in multiple reuqests, join them and then decode
        # if b"ClientDynamicConfigurationNotification" in data:
        #     print(len(data))

        decode(data[12:])

        self.client.write(data)

    def connection_lost(self, exc):
        print('[LcdsToServer] Connection lost', exc)

        self.client.close()
        self.on_con_lost.set_result(True)


class LcdsProxy:
    connectedServer = None

    # Incoming from client
    class ProtocolFromClient(asyncio.Protocol):

        def __init__(self, realHost, realPort):
            self.state = 0  # 0 - not connected to real server
            self.realHost = realHost
            self.realPort = realPort

        def connection_made(self, transport):
            peername = transport.get_extra_info('peername')
            print(f'[LcdsFromClient] Connection from {peername}')
            self.fromClient = transport

        def connection_lost(self, exc):
            print('[LcdsFromClient] Connection lost', exc)

            if self.state == 1:
                self.realServer.close()
                self.state = 0

        def data_received(self, data):
            formatted_bytes = ", ".join([f"0x{byte:02X}" for byte in data[12:]])
            print(f'[LcdsFromClient] Data received: {formatted_bytes}')
            print(data)

            decode(data[12:])

            if self.state == 1:
                self.realServer.write(data)
            else:
                # connect to real server
                asyncio.ensure_future(
                    self.run_to_server(self.realHost, self.realPort, self.fromClient, data))


        async def run_to_server(self, host, port, client, firstReq):
            loop = asyncio.get_event_loop()
            on_con_lost = loop.create_future()

            transport, protocol = await loop.create_connection(
                lambda: ProtocolToServer(on_con_lost, client, firstReq),
                host, port, ssl=ssl.SSLContext(protocol=ssl.PROTOCOL_TLSv1_2))

            self.realServer = transport
            LcdsProxy.connectedServer = self.realServer
            self.state = 1

            try:
                await on_con_lost
            finally:
                self.realServer.close()


    async def run_from_client(self, host, port, realHost, realPort):
        loop = asyncio.get_running_loop()

        server = await loop.create_server(
            lambda: self.ProtocolFromClient(realHost, realPort),
            host, port)

        print('[LcdsFromClient] Server started on ' + host + ':' + str(port))

        async with server:
            await server.serve_forever()
