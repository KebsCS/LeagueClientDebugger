import websockets, asyncio, base64, ssl, datetime
from typing import Dict, Generator, List
from psutil import STATUS_ZOMBIE, Process, process_iter
from UiObjects import *


class LCUConnection:

    class Args:
        lcu_pid = None
        pid = None
        lcu_port = None
        lcu_token = None

    @staticmethod
    def return_ux_process() -> Generator[Process, None, None]:
        for process in process_iter(attrs=["cmdline"]):
            if process.status() == STATUS_ZOMBIE:
                continue

            if process.name() in ["LeagueClientUx.exe", "LeagueClientUx"]:
                yield process

    @staticmethod
    def parse_cmdline_args(cmdline_args) -> Dict[str, str]:
        cmdline_args_parsed = {}
        for cmdline_arg in cmdline_args:
            if len(cmdline_arg) > 0 and "=" in cmdline_arg:
                key, value = cmdline_arg[2:].split("=", 1)
                cmdline_args_parsed[key] = value
        return cmdline_args_parsed

    @staticmethod
    def process_args(process: Process) -> Args:
        process_args = LCUConnection.parse_cmdline_args(process.cmdline())
        args = LCUConnection.Args()
        args.lcu_pid = process.pid
        args.pid = int(process_args['app-pid'])
        args.lcu_port = int(process_args['app-port'])
        args.lcu_token = process_args['remoting-auth-token']
        return args


class LcuWebsocket:
    global_ws = None
    is_running = False

    args = LCUConnection.Args()

    async def run(self):
        if self.is_running:
            return
        self.is_running = True
        process = next(LCUConnection.return_ux_process(), None)
        while not process and self.is_running:
            await asyncio.sleep(1)
            process = next(LCUConnection.return_ux_process(), None)

        if not self.is_running:
            return
        args = LCUConnection.process_args(process)

        headers = {
            'Authorization': 'Basic ' + base64.b64encode(b'riot:' + args.lcu_token.encode()).decode(),
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
                async with websockets.connect("wss://127.0.0.1:" + str(args.lcu_port), extra_headers=headers,
                                              ssl=ssl_context, max_size=2**32, ping_interval=None) as target_ws:
                    print(f"[LCU] Started LCU websocket on port {str(args.lcu_port)}")
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

