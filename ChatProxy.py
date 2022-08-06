import asyncio, ssl

# Proxy server
class ProtocolToServer(asyncio.Protocol):

    def __init__(self, on_con_lost, client, firstReq):
        self.on_con_lost = on_con_lost
        self.client = client
        self.firstReq = firstReq

    def connection_made(self, transport):
        peername = transport.get_extra_info('peername')
        print(f'[ToServer] Connected {peername}')

        # it connects after the first request was already sent
        transport.write(self.firstReq)

    def data_received(self, data):
        print(f'[ToServer] Received: {data.decode("UTF-8")}')
        ChatProxy.xmpp_objects["outgoingList"].addItem(data.decode("UTF-8"))
        self.client.write(data)

    def connection_lost(self, exc):
        print('[ToServer] Connection lost', exc)
        self.client.close()
        self.on_con_lost.set_result(True)


class ChatProxy:
    xmpp_objects = None
    connectedServer = None

    def __init__(self, xmpp_objects):
        ChatProxy.xmpp_objects = xmpp_objects

    # Incoming from client
    class ProtocolFromClient(asyncio.Protocol):

        def __init__(self, realHost, realPort):
            self.state = 0  # 0 - not connected to real server
            self.realHost = realHost
            self.realPort = realPort

        def connection_made(self, transport):
            peername = transport.get_extra_info('peername')
            print(f'[FromClient] Connection from {peername}')
            self.fromClient = transport


        def connection_lost(self, exc):
            print('[FromClient] Connection lost', exc)
            if self.state == 1:
                self.realServer.close()
                self.state = 0

        def data_received(self, data):
            print(f'[FromClient] Data received: {data.decode("UTF-8")}')
            ChatProxy.xmpp_objects["incomingList"].addItem(data.decode("UTF-8"))

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
            self.state = 1
            ChatProxy.connectedServer = transport


            try:
                await on_con_lost
            finally:
                self.realServer.close()


    async def run_from_client(self, host, port, realHost, realPort):
        loop = asyncio.get_running_loop()

        # context = ssl.SSLContext(ssl.PROTOCOL_TLSv1_2)
        # context.load_cert_chain(certfile="public.cer", keyfile="private.key")
        server = await loop.create_server(
            lambda: self.ProtocolFromClient(realHost, realPort),
            host, port) #, ssl=context)


        print('[FromClient] Server started on ' + host + ':' + str(port))

        async with server:
            await server.serve_forever()
