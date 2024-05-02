import asyncio, ssl, re, datetime
from UiObjects import *


def log_and_edit_message(message, is_outgoing) -> str:
    #print('[XMPP] ' + ('>' if is_outgoing else '<') + " " + message)

    item = QListWidgetItem()

    # MITM
    mitmTableWidget = UiObjects.mitmTableWidget
    for row in range(mitmTableWidget.rowCount()):
        if mitmTableWidget.item(row, 2).checkState() != 2:
            continue
        resp_req = "Request" if is_outgoing else "Response"
        if mitmTableWidget.cellWidget(row, 0).currentText() == resp_req:
            if mitmTableWidget.cellWidget(row, 1).currentText() == "XMPP":
                contains = mitmTableWidget.item(row, 2).text()
                if contains in message and contains and contains != "":
                    message = mitmTableWidget.item(row, 3).text()
                    item.setForeground(Qt.magenta)

    text = "[OUT] " if is_outgoing else "[IN]     "
    current_time = datetime.datetime.now().strftime("%H:%M:%S")
    text += f"[{current_time}] "

    if message.startswith("<"):
        regex = re.compile(r"^<\/?(.*?)\/?>", re.MULTILINE)
        match = regex.search(message)
        if match:
            text += match.group(1)
    elif message == " ":
        text += "heartbeat"
    else:
        text += message

    item.setText(text)
    item.setData(256, message)
    UiObjects.xmppList.addItem(item)
    return message

class ProtocolFromServer(asyncio.Protocol):

    def __init__(self, on_con_lost, league_client, first_req):
        self.on_con_lost = on_con_lost

        self.real_server = None
        self.league_client = league_client
        self.first_req = first_req

        self.all_data = b''

    def connection_made(self, transport):
        self.real_server = transport
        peername = transport.get_extra_info('peername')
        print(f'[XMPP] Client connected to real riot server {peername}')

        # connection is made after the first request was already sent
        self.real_server.write(self.first_req)

    def data_received(self, data):
        self.all_data += data
        if self.all_data and self.all_data != b" " and self.all_data[-1] != ord('>'):
            return
        message = self.all_data.decode("UTF-8")
        self.all_data = b''

        message = log_and_edit_message(message, False)
        self.league_client.write(message.encode("UTF-8"))

    def connection_lost(self, exc):
        print('[XMPP] Connection lost with riot server', exc)

        UiObjects.add_disconnected_item(UiObjects.xmppList)

        self.league_client.close()
        self.on_con_lost.set_result(True)


class ChatProxy:
    # Incoming from client
    class ProtocolFromClient(asyncio.Protocol):

        def __init__(self, real_host, real_port):
            self.is_connected = False

            self.real_host = real_host  # euw1.chat.si.riotgames.com
            self.real_port = real_port  # 5223

            self.real_server = None
            self.league_client = None

            self.all_data = b''

        def connection_made(self, transport):
            self.league_client = transport
            peername = transport.get_extra_info('peername')
            print(f'[XMPP] League client connected to proxy {peername}')

            UiObjects.add_connected_item(UiObjects.xmppList)

        def connection_lost(self, exc):
            print('[XMPP] Connection lost with league client', exc)

            if self.is_connected:
                self.real_server.close()
                self.is_connected = False

        def data_received(self, data):
            self.all_data += data
            if self.all_data and self.all_data != b" " and self.all_data[-1] != ord('>'):
                return
            message = self.all_data.decode("UTF-8")
            self.all_data = b''

            message = log_and_edit_message(message, True)

            if self.is_connected:
                self.real_server.write(message.encode("UTF-8"))
            else:
                asyncio.ensure_future(
                    self.connect_to_real_server(self.real_host, self.real_port, self.league_client, message.encode("UTF-8")))

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

        print(f'[XMPP] Proxy server started on {proxy_host}:{proxy_port}')

        async with server:
            await server.serve_forever()
