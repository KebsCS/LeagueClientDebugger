import asyncio, requests, ssl, gzip, datetime, re, threading
from concurrent.futures import ThreadPoolExecutor
from httptools import HttpRequestParser
from requests.adapters import HTTPAdapter
from typing import Any
from ProxyServers import ProxyServers, REQUEST_TIMEOUT, MAX_CONCURRENT_REQUESTS
from ValoLogWatcher import ValoLogWatcher
from UiObjects import *

import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

CIPHERS = [
    "TLS_CHACHA20_POLY1305_SHA256",
    "TLS_AES_128_GCM_SHA256",
    "TLS_AES_256_GCM_SHA384",
    "ECDHE-ECDSA-CHACHA20-POLY1305",
    "ECDHE-RSA-CHACHA20-POLY1305",
    "ECDHE-ECDSA-AES128-GCM-SHA256",
    "ECDHE-RSA-AES128-GCM-SHA256",
    "ECDHE-ECDSA-AES256-GCM-SHA384",
    "ECDHE-RSA-AES256-GCM-SHA384",
    "ECDHE-ECDSA-AES128-SHA",
    "ECDHE-RSA-AES128-SHA",
    "ECDHE-ECDSA-AES256-SHA",
    "ECDHE-RSA-AES256-SHA",
    "AES128-GCM-SHA256",
    "AES256-GCM-SHA384",
    "AES128-SHA",
    "AES256-SHA",
    "DES-CBC3-SHA"
]


class LockedCookieJar(requests.cookies.RequestsCookieJar):
    """requests.Session isn't thread safe. Now that requests are forwarded from a thread
    pool, the cookie jar is the one piece of shared mutable state that isn't already
    guarded: preparing a request iterates the jar (merge_cookies) without taking the
    jar's own lock, so a response storing a cookie at the same time raises
    "dictionary changed size during iteration". urllib3's connection pools are thread
    safe, so locking the iteration and the writes is enough.
    The jar is shared on purpose - the client relies on it whenever
    optionsClientHandlesCookies is off, see CustomProtocol.on_header"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._jar_lock = threading.RLock()

    def __iter__(self):
        with self._jar_lock:
            return iter(list(super().__iter__()))

    def set_cookie(self, *args, **kwargs):
        with self._jar_lock:
            return super().set_cookie(*args, **kwargs)

    def clear(self, *args, **kwargs):
        with self._jar_lock:
            return super().clear(*args, **kwargs)


class SSLAdapter(HTTPAdapter):
    def init_poolmanager(self, *a: Any, **k: Any) -> None:
        c = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
        c.check_hostname = False
        c.verify_mode = ssl.CERT_NONE
        c.set_ciphers(':'.join(CIPHERS))
        c.minimum_version = ssl.TLSVersion.TLSv1
        c.options |= 1 << 19  # SSL_OP_NO_ENCRYPT_THEN_MAC
        c.options |= 1 << 14  # SSL_OP_NO_TICKET

        k['ssl_context'] = c
        return super(SSLAdapter, self).init_poolmanager(*a, **k)

    def proxy_manager_for(self, *a: Any, **k: Any):
        c = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
        c.check_hostname = False
        c.verify_mode = ssl.CERT_NONE
        c.set_ciphers(':'.join(CIPHERS))
        c.minimum_version = ssl.TLSVersion.TLSv1
        c.options |= 1 << 19  # SSL_OP_NO_ENCRYPT_THEN_MAC
        c.options |= 1 << 14  # SSL_OP_NO_TICKET

        k['ssl_context'] = c
        return super(SSLAdapter, self).proxy_manager_for(*a, **k)


class HttpProxy:
    is_valo_log_running = False
    userinfo_token = "" # not consistently updated, only used for rtmp player-preferences

    session = requests.sessions.Session()
    # one session is shared by every host proxy, so the pool has to hold more than the
    # default 10 connections, otherwise urllib3 keeps discarding and reopening them
    session.mount('https://', SSLAdapter(pool_connections=64, pool_maxsize=MAX_CONCURRENT_REQUESTS))
    session.cookies = LockedCookieJar()

    # requests are forwarded here instead of on the event loop, which also runs the Qt ui
    # and every other proxy - a blocking call there stalls all of them at once
    executor = ThreadPoolExecutor(max_workers=MAX_CONCURRENT_REQUESTS, thread_name_prefix="http-proxy")

    class CustomProtocol(asyncio.Protocol):
        def __init__(self, original_host: str):
            self.parser = None
            self.req = Request()
            self.original_host = original_host
            self.transport = None
            self.current_req = self.req  # the request being forwarded right now

            # answers have to arrive in the order they were requested, so every
            # connection forwards its own requests one by one. Different connections still
            # run in parallel, which is where the concurrency comes from
            self.queue = asyncio.Queue()
            self.pump_task = None

        def connection_made(self, transport):
            peername = transport.get_extra_info('peername')
            #print('[HttpProxy] Connection from {}'.format(peername))
            self.transport = transport
            self.pump_task = asyncio.get_running_loop().create_task(self.pump())

        def connection_lost(self, exc):
            if self.pump_task:
                self.pump_task.cancel()
                self.pump_task = None
            self.transport.close()

        def data_received(self, data):
            #print(data.decode())
            if self.parser is None:
                self.parser = HttpRequestParser(self)
            self.parser.feed_data(data)
            # try:
            #     self.parser.feed_data(data)
            # except Exception as e:
            #     print("[HttpProxy] feed_data failed", e)
            #     print(data)

        def on_url(self, url):
            self.req = Request()
            self.req.url = url.decode()
            self.req.method = self.parser.get_method().decode()

        def on_header(self, name, value):
            if name.decode() == "Cookie" and not UiObjects.optionsClientHandlesCookies.isChecked():
                return  # requests session handles cookies
            self.req.headers[name.decode()] = value.decode()

        def on_body(self, body):
            self.req.body += body

        def edit_request(self, request: Request) -> Request:

            # after replacing player-preferences in rtmp, sent player-preference requests from client don't have authorization header
            if "https://player-preferences" in request.url and "Authorization" not in request.headers and HttpProxy.userinfo_token:
                request.headers["Authorization"] = HttpProxy.userinfo_token

            return request

        async def edit_response(self, response: requests.Response) -> requests.Response:
            if response.url.startswith("https://auth.") and response.url.endswith("/.well-known/openid-configuration"):
                response._content = re.sub(
                    r"https://auth\.(riotgames|esports\.rpg\.riotgames)\.com",
                    lambda match: f"http://localhost:{ProxyServers.started_proxies[match.group(0)]}",
                    response.text
                ).encode()

            # CORS fix
            if response.request.method.upper() == "OPTIONS":
                response.raw.status = 200
                response.status_code = 200

                headers_to_modify = ['Access-Control-Allow-Origin', 'Access-Control-Allow-Methods',
                                     'Access-Control-Allow-Headers', 'Access-Control-Expose-Headers']
                headers_to_modify_lower = [header.lower() for header in headers_to_modify]

                for headers_dict in [response.headers, response.raw.headers]:
                    for header in headers_dict:
                        if header.lower() in headers_to_modify_lower:
                            headers_dict[header] = '*'


            if UiObjects.miscDowngradeLCEnabled.isChecked():
                # name change screen bypass from 2020
                # summoner names got removed from all requests and namechange endpoints don't exist anymore
                if "summoners/summoner-ids" in response.url or "summoners/puuids" in response.url:
                    original = response.json()
                    for player in original:
                        if "unnamed" in player:
                            player["unnamed"] = False
                    response._content = json.dumps(original).encode()

            return response

        def send_response(self, response: bytes):
            # the client can disconnect while its request is still in flight
            if self.transport and not self.transport.is_closing():
                self.transport.write(response)

        def on_message_complete(self):
            self.req.headers["Host"] = self.original_host.split("//")[1]
            self.req.url = "https://" + self.req.headers["Host"] + self.req.url

            self.queue.put_nowait(self.req)
            self.req = Request()  # the connection is kept alive, don't touch the queued request anymore

        async def pump(self):
            """Forwards the requests of this connection one by one"""
            loop = asyncio.get_running_loop()
            while True:
                req = await self.queue.get()
                try:
                    req = self.current_req = self.edit_request(req)
                    response = await loop.run_in_executor(HttpProxy.executor, self.forward, req)
                    await self.handle_response(req, response)
                except asyncio.CancelledError:
                    raise
                except Exception as e:
                    print(f"[HttpProxy] {req.method} {req.url} failed: {e!r}")
                    # sent when a request couldn't be forwarded
                    self.send_response((b"HTTP/1.1 502 Bad Gateway\r\n"
                        b"Content-Length: 0\r\n"
                        b"Connection: close\r\n"
                        b"\r\n"))
                    if self.transport:
                        self.transport.close()  # the client shouldn't reuse this connection
                    return

        @staticmethod
        def forward(req: Request) -> requests.Response:
            """Runs on a worker thread, so it must not touch qt widgets or the event loop"""
            return HttpProxy.session.request(req.method, req.url, headers=req.headers, data=req.body,
                                             proxies=ProxyServers.fiddler_proxies, verify=False,
                                             timeout=REQUEST_TIMEOUT)

        async def handle_response(self, req: Request, response: requests.Response):
            if req.url == "https://entitlements.auth.riotgames.com/api/token/v1" and not HttpProxy.is_valo_log_running:
                HttpProxy.is_valo_log_running = True
                auth = req.headers["Authorization"]
                entitlements = response.json()["entitlements_token"]
                valo_log = ValoLogWatcher(auth, entitlements)
                asyncio.create_task(valo_log.run())

            # valid for 1h, best to get a new one when it's refreshed, although this isn't too important as
            # I think player-preferences are sent only at beginning after login and client doesn't rely on them
            if "https://player-preferences" in req.url and "Authorization" in req.headers:
                HttpProxy.userinfo_token = req.headers["Authorization"]

            response = await self.edit_response(response)

            if "Content-Length" in response.headers:
                response.headers["Content-Length"] = str(len(response.content))
            if "Content-Length" in response.raw.headers:
                response.raw.headers["Content-Length"] = str(len(response.content))
            if "Content-Encoding" in response.raw.headers:  # remove gzip
                encodings = [encoding.strip() for encoding in response.raw.headers["Content-Encoding"].split(",")]
                encodings = [encoding for encoding in encodings if encoding.lower() != "gzip"]
                response.raw.headers["Content-Encoding"] = ", ".join(encodings)
                if not response.raw.headers["Content-Encoding"]:
                    del response.raw.headers["Content-Encoding"]
            if "Transfer-Encoding" in response.raw.headers:
                del response.raw.headers["Transfer-Encoding"]
            if "Transfer-Encoding" in response.headers:
                del response.headers["Transfer-Encoding"]

            raw_response = to_raw_response(response)

            HttpProxy.log_message(response, raw_response)
            self.send_response(bytes(raw_response))

    @staticmethod
    def log_message(response: requests.Response, raw_response=None):
        if raw_response is None:
            raw_response = to_raw_response(response)
        item = QListWidgetItem()
        current_time = datetime.datetime.now().strftime("%H:%M:%S")
        item.setText(
            f"[{current_time}] {str(response.status_code.real)} {response.request.method} {response.request.url}")
        raw_request = to_raw_request(response.request)

        try:
            item.setData(256, raw_request.decode())
        except UnicodeDecodeError:
            item.setData(256, raw_request.hex())

        raw_response_str = raw_response.decode()
        try:
            if "Content-Type" in response.headers and "json" in response.headers["Content-Type"] \
                    and response.status_code.real != 204:
                raw_response_split = raw_response_str.split("\r\n\r\n")
                raw_response_str = raw_response_split[0] + "\r\n\r\n" + json.dumps(json.loads(raw_response_split[1]), indent=4)
            item.setData(257, raw_response_str)
        except Exception as e:
            print("json indent response failed")
            print(raw_response_str)
            item.setData(257, raw_response_str)

        scrollbar = UiObjects.httpsList.verticalScrollBar()
        if not scrollbar or scrollbar.value() == scrollbar.maximum():
            UiObjects.httpsList.addItem(item)
            UiObjects.httpsList.scrollToBottom()
        else:
            UiObjects.httpsList.addItem(item)

    async def run_server(self, host, port, original_host):
        loop = asyncio.get_running_loop()

        server = await loop.create_server(
            lambda: self.CustomProtocol(original_host),
            host, port)

        print(f'[HttpProxy] {original_host} server started on {host}:{str(port)}')

        async with server:
            await server.serve_forever()
