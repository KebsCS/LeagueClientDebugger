import psutil, base64, websockets, ssl, asyncio, datetime
from UiObjects import *

class RiotWs:
    global_ws = None
    is_running = False

    async def get_port_token(self):
        return await asyncio.to_thread(self._get_port_token_sync)

    def _get_port_token_sync(self):
        for proc in psutil.process_iter(['name', 'cmdline']):
            try:
                if "Riot Client" in proc.info['name'] and any('--app-port' in arg for arg in proc.info['cmdline']):
                    if proc.status() == psutil.STATUS_ZOMBIE:
                        continue
                    cmdline = proc.info['cmdline']
                    app_port = [s.split('=')[1] for s in cmdline if s.startswith('--app-port=')][0]
                    auth_token = [s.split('=')[1] for s in cmdline if s.startswith('--remoting-auth-token=')][0]
                    return app_port, auth_token
            except Exception as e:
                continue
        return None, None

    async def run(self):
        if self.is_running:
            return
        self.is_running = True
        port, token = await self.get_port_token()
        while port is None and token is None and self.is_running:
            await asyncio.sleep(0.5)
            port, token = await self.get_port_token()

        if not self.is_running:
            return

        url = "https://127.0.0.1:" + port
        headers = {
            'Authorization': 'Basic ' + base64.b64encode(f"riot:{token}".encode("utf-8")).decode(),
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }

        ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE

        attempt = 0
        max_attempts = 20
        while attempt < max_attempts:  # refuses connection if we try to connect too quickly
            try:
                async with websockets.connect("wss://127.0.0.1:" + str(port), extra_headers=headers,
                                              ssl=ssl_context, max_size=2 ** 32, ping_interval=None) as target_ws:
                    print(f"[RC] Started RiotClient websocket on port {str(port)}")
                    self.global_ws = target_ws
                    await target_ws.send(b"[5, \"OnJsonApiEvent\"]")
                    async for message in target_ws:
                        await RiotWs.log_message(message)

                    break
            except ConnectionRefusedError:
                attempt += 1
                await asyncio.sleep(1)
            except websockets.exceptions.ConnectionClosedError:
                print("[RC] Websocket closed")
                return

    async def close(self):
        self.is_running = False
        if self.global_ws:
            await self.global_ws.close()
            print("[RC] Websocket closed")

    @staticmethod
    async def log_message(message):
        # print(message)
        if not message:
            return
        item = QListWidgetItem()
        data = json.loads(message)[2]
        current_time = datetime.datetime.now().strftime("%H:%M:%S")
        text = f"[{current_time}] {data['eventType']} {data['uri']}"
        item.setText(text)
        item.setData(256, data)

        scrollbar = UiObjects.rcList.verticalScrollBar()
        if not scrollbar or scrollbar.value() == scrollbar.maximum():
            UiObjects.rcList.addItem(item)
            UiObjects.rcList.scrollToBottom()
        else:
            UiObjects.rcList.addItem(item)

