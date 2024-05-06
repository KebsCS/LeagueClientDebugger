import websockets, asyncio, base64, ssl, datetime
from typing import Dict, Generator, List
from psutil import STATUS_ZOMBIE, Process, process_iter
from UiObjects import *


def _return_ux_process() -> Generator[Process, None, None]:
    for process in process_iter(attrs=["cmdline"]):
        if process.status() == STATUS_ZOMBIE:
            continue

        if process.name() in ["LeagueClientUx.exe", "LeagueClientUx"]:
            yield process


def parse_cmdline_args(cmdline_args) -> Dict[str, str]:
    cmdline_args_parsed = {}
    for cmdline_arg in cmdline_args:
        if len(cmdline_arg) > 0 and "=" in cmdline_arg:
            key, value = cmdline_arg[2:].split("=", 1)
            cmdline_args_parsed[key] = value
    return cmdline_args_parsed


class LcuWebsocket:
    global_ws = None
    is_running = False

    lcu_pid = None
    pid = None
    lcu_port = None
    lcu_token = None

    async def process_args(self, process: Process):
        process_args = parse_cmdline_args(process.cmdline())

        self.lcu_pid = process.pid
        self.pid = int(process_args['app-pid'])
        self.lcu_port = int(process_args['app-port'])
        self.lcu_token = process_args['remoting-auth-token']

    async def get_process(self):
        process = next(_return_ux_process(), None)
        while not process and self.is_running:
            await asyncio.sleep(1)
            process = next(_return_ux_process(), None)
        return process

    async def run(self):
        if self.is_running:
            return
        self.is_running = True
        process = await self.get_process()
        if not self.is_running:
            return
        await self.process_args(process)

        headers = {
            'Authorization': 'Basic ' + base64.b64encode(b'riot:' + self.lcu_token.encode()).decode(),
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
                async with websockets.connect("wss://127.0.0.1:" + str(self.lcu_port), extra_headers=headers,
                                              ssl=ssl_context, max_size=2**32, ping_interval=None) as target_ws:
                    print("[LCU] Started LCU websocket")
                    self.global_ws = target_ws
                    await target_ws.send(b"[5, \"OnJsonApiEvent\"]")
                    async for message in target_ws:
                        await LcuWebsocket.log_message(message)

                    break
            except ConnectionRefusedError:
                attempt += 1
                await asyncio.sleep(1)

    async def close(self):
        self.is_running = False
        if self.global_ws:
            await self.global_ws.close()


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

        scrollbar = UiObjects.lcuList.verticalScrollBar()
        if not scrollbar or scrollbar.value() == scrollbar.maximum():
            UiObjects.lcuList.addItem(item)
            UiObjects.lcuList.scrollToBottom()
        else:
            UiObjects.lcuList.addItem(item)

    async def start_ws(self):
        connection = await self.run()

