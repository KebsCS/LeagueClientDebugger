import websockets, asyncio, base64, ssl, datetime, psutil
from HttpProxy import HttpProxy
from UiObjects import *

class LcuWebsocket:
    global_ws = None
    is_running = False

    async def get_port_token(self):
        return await asyncio.to_thread(self._get_port_token_sync)

    def _find_cmdline_sync(self):
        for proc in psutil.process_iter(['name', 'cmdline']):
            try:
                if "LeagueClientUx" in proc.info['name'] and any('--app-port' in arg for arg in proc.info['cmdline']):
                    if proc.status() == psutil.STATUS_ZOMBIE:
                        continue
                    if "LeagueClientUxRender" in proc.info['name']:
                        continue
                    return proc.info['cmdline']
            except Exception as e:
                continue
        return None

    @staticmethod
    def _parse_port_token(cmdline):
        port = next((arg.split('=', 1)[1] for arg in cmdline if arg.startswith('--app-port=')), None)
        token = next((arg.split('=', 1)[1] for arg in cmdline if arg.startswith('--remoting-auth-token=')), None)
        return port, token

    def _get_client_info_sync(self):
        cmdline = self._find_cmdline_sync()
        if not cmdline:
            return None, None, None
        port, token = self._parse_port_token(cmdline)
        return port, token, cmdline

    async def get_client_info(self):
        """Returns (port, token, cmdline) from a single process scan."""
        return await asyncio.to_thread(self._get_client_info_sync)

    def _get_port_token_sync(self):
        port, token, _ = self._get_client_info_sync()
        return port, token

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
        while attempt < max_attempts:   # refuses connection if we try to connect too quickly
            try:
                async with websockets.connect("wss://127.0.0.1:" + str(port), extra_headers=headers,
                                              ssl=ssl_context, max_size=2**32, ping_interval=None) as target_ws:
                    print(f"[LCU] Started LCU websocket on port {str(port)}")
                    self.global_ws = target_ws
                    await target_ws.send(b"[5, \"OnJsonApiEvent\"]")
                    async for message in target_ws:
                        await LcuWebsocket.log_message(message)

                    break
            except ConnectionRefusedError:
                attempt += 1
                await asyncio.sleep(1)
            except websockets.exceptions.ConnectionClosedError:
                print("[LCU] Websocket closed")
                return

    async def close(self):
        self.is_running = False
        if self.global_ws:
            await self.global_ws.close()
            print("[LCU] Websocket closed")


    async def request(self, method : str, url : str, body : str, proxies):
        port, token = await self.get_port_token()
        if port is None and token is None:
            print("[LCU] Failed sending custom request, client not found")
            return

        try:
            headers = {
                'Authorization': 'Basic ' + base64.b64encode(f"riot:{token}".encode("utf-8")).decode(),
                'Content-Type': 'application/json',
                'Accept': 'application/json',
                'User-Agent': 'Mozilla/5.0 (Windows NT 6.2; WOW64) AppleWebKit/537.36 '
                              '(KHTML, like Gecko) LeagueOfLegendsClient/15.22.723.8396 (CEF 91) Safari/537.36'
            }

            if not url.startswith("https://127.0.0.1"):
                if not url.startswith("http://") and not url.startswith("https://"):
                    if url[0] != "/":
                        url = "/" + url
                    url = "https://127.0.0.1:" + str(port) + url
            elif not url.startswith("https://127.0.0.1:"):
                insert_index = len("https://127.0.0.1")
                url = url[:insert_index] + ":" + port + url[insert_index:]

            response = requests.request(method,
                                        url,
                                        headers=headers, data=body,
                                        proxies=proxies, verify=False)

            HttpProxy.log_message(response)
        except Exception as e:
            print("[LCU] Failed to send custom request ", e)

    @staticmethod
    async def log_message(message):
        #print(message)
        if not message:
            return
        item = QListWidgetItem()
        data = json.loads(message)[2]
        current_time = datetime.datetime.now().strftime("%H:%M:%S")
        text = f"[{current_time}] {data['eventType']} {data['uri']}"
        item.setText(text)
        item.setData(256, data)
        item.setData(258, "lcu")

        scrollbar = UiObjects.lcuList.verticalScrollBar()
        if not scrollbar or scrollbar.value() == scrollbar.maximum():
            UiObjects.lcuList.addItem(item)
            UiObjects.lcuList.scrollToBottom()
        else:
            UiObjects.lcuList.addItem(item)

    async def start_ws(self):
        connection = await self.run()

