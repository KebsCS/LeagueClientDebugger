import asyncio, websockets, gzip, re, datetime

from ProxyServers import ProxyServers
from UiObjects import *

class RmsProxy:
    def __init__(self, real_host):
        self.real_host = real_host

    async def handle_connection(self, ws, path):
        target_hostname = self.real_host

        req_headers = dict(ws.request_headers)
        #print(f"req_headers {req_headers}")
        if 'host' in req_headers:
            del req_headers['host']
        if 'upgrade' in req_headers:
            del req_headers['upgrade']
        if 'connection' in req_headers:
            del req_headers['connection']
        if 'sec-websocket-key' in req_headers:
            del req_headers['sec-websocket-key']
        if 'origin' in req_headers:
            del req_headers['origin']

        ws.useragent = re.search(r"(?<=\) ).+/.", req_headers["user-agent"]).group()

        UiObjects.add_connected_item(UiObjects.rmsList, str(ws.useragent), json.dumps(req_headers, indent=4))

        ws.target_ws_buffer = []

        async def process_ws_messages(ws, target_ws):
            try:
                async for message in ws:
                    await self.log_message(message, True, ws.useragent)
                    if target_ws.open:
                        await target_ws.send(message)
                    else:
                        ws.target_ws_buffer.append(message)
            except websockets.ConnectionClosed as e:
                print("[RMS] Connection closed ", e)

        async def process_target_ws_messages(ws, target_ws):
            if len(ws.target_ws_buffer) > 0:
                for message in ws.target_ws_buffer:
                    await target_ws.send(message)
                ws.target_ws_buffer = []
            try:
                async for message in target_ws:
                    await self.log_message(message, False, ws.useragent)
                    await ws.send(message)
            except websockets.ConnectionClosed as e:
                print("[RMS] Connection closed ", e)
                UiObjects.add_disconnected_item(UiObjects.rmsList)


        async with websockets.connect(target_hostname + path, extra_headers=req_headers) as target_ws:

            await asyncio.gather(
                process_ws_messages(ws, target_ws),
                process_target_ws_messages(ws, target_ws)
            )

    async def log_message(self, message, is_outgoing, source):
        display_message = message

        if isinstance(message, bytes):
            if message[0] == 0x1F and message[1] == 0x8B and message[2] == 0x08:    # gzip file format header
                display_message = gzip.decompress(display_message)

        display_message = display_message if isinstance(message, str) else display_message.decode('utf-8')
        #print('[RMS] ' + ('>' if is_outgoing else '<') + " " + source + display_message)

        current_time = datetime.datetime.now().strftime("%H:%M:%S")
        json_message = json.loads(display_message)
        item_text = f"[{current_time}] "
        item_text += "[OUT] " if is_outgoing else "[IN]     "
        item_text += f"({source}) {json_message.get('subject', '')} {json_message['payload'].get('resource','') if 'payload' in json_message else ''}"

        item = QListWidgetItem()
        item.setText(item_text)
        item.setData(256, json.dumps(json_message, indent=4))
        UiObjects.rmsList.addItem(item)


    async def start_proxy(self):
        server = await websockets.serve(self.handle_connection, host="localhost", port=ProxyServers.rms_port)
