import asyncio, requests, ssl, gzip, datetime
from httptools import HttpRequestParser
from requests.adapters import HTTPAdapter
from typing import Any
from ProxyServers import ProxyServers
from UiObjects import *

import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

CIPHERS = [
    'ECDHE-ECDSA-AES128-GCM-SHA256',
    'ECDHE-ECDSA-CHACHA20-POLY1305',
    'ECDHE-RSA-AES128-GCM-SHA256',
    'ECDHE-RSA-CHACHA20-POLY1305',
    'ECDHE+AES128',
    'RSA+AES128',
    'ECDHE+AES256',
    'RSA+AES256',
    'ECDHE+3DES',
    'RSA+3DES'
]


class SSLAdapter(HTTPAdapter):
    def init_poolmanager(self, *a: Any, **k: Any) -> None:
        c = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
        c.check_hostname = False
        c.set_ciphers(':'.join(CIPHERS))
        c.minimum_version = ssl.TLSVersion.TLSv1_2
        c.verify_mode = ssl.CERT_NONE

        k['ssl_context'] = c
        return super(SSLAdapter, self).init_poolmanager(*a, **k)

    def proxy_manager_for(self, *a: Any, **k: Any):
        c = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
        c.check_hostname = False
        c.set_ciphers(':'.join(CIPHERS))
        c.minimum_version = ssl.TLSVersion.TLSv1_2
        c.verify_mode = ssl.CERT_NONE

        k['ssl_context'] = c
        return super(SSLAdapter, self).proxy_manager_for(*a, **k)


class Request:
    def __init__(self):
        self.headers = dict()
        self.method = "GET"
        self.version = None
        self.url = "/"
        self.body = b""


def to_raw_response(response: requests.Response) -> bytearray:
    HTTP_VERSIONS = {
        9: b'0.9',
        10: b'1.0',
        11: b'1.1',
    }

    def _coerce_to_bytes(data):
        if not isinstance(data, bytes) and hasattr(data, 'encode'):
            data = data.encode('utf-8')
        return data if data is not None else b''

    def _format_header(name, value):
        return (_coerce_to_bytes(name) + b': ' + _coerce_to_bytes(value) +
                b'\r\n')

    bytearr = bytearray()
    raw = response.raw
    version_str = HTTP_VERSIONS.get(raw.version, b'?')

    bytearr.extend(b'HTTP/' + version_str + b' ' +
                   str(raw.status).encode('ascii') + b' ' +
                   _coerce_to_bytes(response.reason) + b'\r\n')

    headers = raw.headers
    for name in headers.keys():
        for value in headers.getlist(name):
            bytearr.extend(_format_header(name, value))

    if len(response.content) > 0 and 'Content-Length' not in headers:
        bytearr.extend(_format_header('Content-Length', str(len(response.content))))

    bytearr.extend(b'\r\n')

    bytearr.extend(response.content)
    return bytearr


def to_raw_request(request) -> bytearray:

    def _coerce_to_bytes(data):
        if not isinstance(data, bytes) and hasattr(data, 'encode'):
            data = data.encode('utf-8')

        if isinstance(data, bytes):
            if data[0] == 0x1F and data[1] == 0x8B and data[2] == 0x08:    # gzip file format header
                data = gzip.decompress(data)

        return data if data is not None else b''

    def _build_request_path(url):
        uri = requests.compat.urlparse(url)
        request_path = _coerce_to_bytes(uri.path)
        if uri.query:
            request_path += b'?' + _coerce_to_bytes(uri.query)

        return request_path, uri

    def _format_header(name, value):
        return (_coerce_to_bytes(name) + b': ' + _coerce_to_bytes(value) +
                b'\r\n')

    method = _coerce_to_bytes(request.method)
    request_path, uri = _build_request_path(request.url)

    bytearr = bytearray()

    headers = request.headers.copy()
    host_header = _coerce_to_bytes(headers.pop('Host', uri.netloc))

    bytearr.extend(method + b' ' + b'https://' + host_header + request_path + b' HTTP/1.1\r\n')

    bytearr.extend(b'Host: ' + host_header + b'\r\n')

    for name, value in headers.items():
        bytearr.extend(_format_header(name, value))

    bytearr.extend(b'\r\n')
    if request.body:
        if isinstance(request.body, requests.compat.basestring):
            bytearr.extend(_coerce_to_bytes(request.body))
        else:
            # In the event that the body is a file-like object, let's not try
            # to read everything into memory.
            bytearr.extend('<< Request body is not a string-like type >>')
    bytearr.extend(b'\r\n')
    return bytearr


class HttpProxy:
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
            if name.decode() == "Cookie":
                return  # requests session handles cookies
            self.req.headers[name.decode()] = value.decode()

        def on_body(self, body):
            self.req.body += body

        def edit_request(self, request: Request) -> Request:
            return request

        def edit_response(self, response: requests.Response) -> requests.Response:
            if response.url == "https://auth.riotgames.com/.well-known/openid-configuration":
                response._content = response.text.replace("https://auth.riotgames.com",
                                                          f"http://localhost:{ProxyServers.auth_port}").encode()

            # CORS fix, storefront required it
            if response.request.method.upper() == "OPTIONS":# and "storefront" in response.url:
                response.raw.status = 200
                response.status_code = 200

                headers_to_modify = ['access-control-allow-origin', 'access-control-allow-methods',
                                     'access-control-allow-headers', 'access-control-expose-headers']

                for headers_dict in [response.headers, response.raw.headers]:
                    for header in headers_dict:
                        if header.lower() in headers_to_modify:
                            headers_dict[header] = '*'

            return response

        def send_response(self, response: bytes):
            self.transport.write(response)

        def on_message_complete(self):
            self.req.headers["Host"] = self.original_host.split("//")[1]
            self.req.url = "https://" + self.req.headers["Host"] + self.req.url

            self.req = self.edit_request(self.req)

            response = HttpProxy.session.request(self.req.method, self.req.url, headers=self.req.headers, data=self.req.body,
                                                 proxies=ProxyServers.fiddler_proxies, verify=False)

            response = self.edit_response(response)

            if "Content-Length" in response.headers:
                response.headers["Content-Length"] = str(len(response.text))
            if "Content-Length" in response.raw.headers:
                response.raw.headers["Content-Length"] = str(len(response.text))
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
        item.setData(256, raw_request.decode())

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
