import asyncio, requests, ssl, gzip, datetime, re
from httptools import HttpRequestParser
from requests.adapters import HTTPAdapter
from typing import Any
from ProxyServers import ProxyServers
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

    session = requests.sessions.Session()
    session.mount('https://', SSLAdapter())

    class CustomProtocol(asyncio.Protocol):
        def __init__(self, original_host: str):
            self.parser = None
            self.req = Request()
            self.original_host = original_host

        def connection_made(self, transport):
            peername = transport.get_extra_info('peername')
            #print('[HttpProxy] Connection from {}'.format(peername))
            self.transport = transport
            #self.session = requests.sessions.Session()

        def connection_lost(self, exc):
            self.transport.close()
            #self.session.close()

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
            return request

        def edit_response(self, response: requests.Response) -> requests.Response:
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
            self.transport.write(response)

        def on_message_complete(self):
            self.req.headers["Host"] = self.original_host.split("//")[1]
            self.req.url = "https://" + self.req.headers["Host"] + self.req.url

            self.req = self.edit_request(self.req)

            response = HttpProxy.session.request(self.req.method, self.req.url, headers=self.req.headers, data=self.req.body,
                                                 proxies=ProxyServers.fiddler_proxies, verify=False)

            if self.req.url == "https://entitlements.auth.riotgames.com/api/token/v1" and not HttpProxy.is_valo_log_running:
                HttpProxy.is_valo_log_running = True
                auth = self.req.headers["Authorization"]
                entitlements = response.json()["entitlements_token"]
                valo_log = ValoLogWatcher(auth, entitlements)
                asyncio.create_task(valo_log.run())

            response = self.edit_response(response)

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
