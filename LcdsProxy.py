import asyncio, ssl
import pyamf
from pyamf import amf0,remoting
from pyamf import *
from rtmplite3 import *
#pyamf.register_class(messaging.AsyncMessage, 'flex.messaging.messages.AsyncMessage')


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

    chunkSize = 128
    def data_received(self, data):
        #received = data.decode("UTF-8")
        print(f'[LcdsToServer] Received: received {data}')

        # self.decoder = pyamf.get_decoder(pyamf.AMF3)
        # self.buffer = self.decoder.stream
        # self.buffer.write(data)
        # self.buffer.seek(0)
        # msg = self.decoder.readElement()



        self.client.write(data)

    def connection_lost(self, exc):
        print('[LcdsToServer] Connection lost', exc)

        self.client.close()
        self.on_con_lost.set_result(True)


class LcdsProxy:
    connectedServer = None

    #def __init__(self):

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
            #received = data.decode("UTF-8")
            print(f'[LcdsFromClient] Data received: {data}')

            # self.decoder = pyamf.get_decoder(pyamf.AMF3)
            # self.buffer = self.decoder.stream
            # self.buffer.write(data)
            # self.buffer.seek(0)
            # msg = self.decoder.readElement()

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
                host, port, ssl=ssl.SSLContext(protocol=ssl.PROTOCOL_TLSv1))

            self.realServer = transport
            LcdsProxy.connectedServer = self.realServer
            self.state = 1

            try:
                await on_con_lost
            finally:
                self.realServer.close()


    async def run_from_client(self, host, port, realHost, realPort):
        loop = asyncio.get_running_loop()

        #context = ssl.SSLContext(ssl.PROTOCOL_TLSv1_2)
        #context.load_cert_chain(certfile="public.cer", keyfile="private.key")
        server = await loop.create_server(
            lambda: self.ProtocolFromClient(realHost, realPort),
            host, port)#, ssl=context)


        print('[FromClient] Server started on ' + host + ':' + str(port))

        async with server:
            await server.serve_forever()
