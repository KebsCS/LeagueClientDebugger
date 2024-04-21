import asyncio, requests, os, urllib3
from httptools import HttpRequestParser
from ProxyServers import ProxyServers

import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


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
        # Don't bail out with an exception if data is None
        return data if data is not None else b''

    def _format_header(name, value):
        return (_coerce_to_bytes(name) + b': ' + _coerce_to_bytes(value) +
                b'\r\n')

    bytearr = bytearray()
    raw = response.raw
    # Let's convert the version int from httplib to bytes
    version_str = HTTP_VERSIONS.get(raw.version, b'?')

    # <prefix>HTTP/<version_str> <status_code> <reason>
    bytearr.extend(b'HTTP/' + version_str + b' ' +
                   str(raw.status).encode('ascii') + b' ' +
                   _coerce_to_bytes(response.reason) + b'\r\n')

    headers = raw.headers
    for name in headers.keys():
        for value in headers.getlist(name):
            if name == 'Content-Length':
                value = str(len(response.content))
            bytearr.extend(_format_header(name, value))

    if len(response.content) > 0 and 'Content-Length' not in headers:
        bytearr.extend(_format_header('Content-Length', str(len(response.content))))

    bytearr.extend(b'\r\n')

    bytearr.extend(response.content)
    return bytearr


class HttpProxy:
    #todo move, maybe diff class
    geoPasUrl = ""  # https://riot-geo.pas.si.riotgames.com/pas/v1/service/chat
    geoPasBody = ""

    session = requests.sessions.Session()

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
            if self.parser is None:
                self.parser = HttpRequestParser(self)

            try:
                self.parser.feed_data(data)
            except Exception as e:
                print("[HttpProxy] feed_data failed", e)
                print(data)

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
            # elif response.url == HttpProxy.geoPasUrl:
            #     HttpProxy.geoPasBody = response.text
            #     print(HttpProxy.geoPasBody)

            return response

        def send_response(self, response: requests.Response):
            if "Content-Length" in response.headers:
                response.headers["Content-Length"] = str(len(response.text))
            response = bytes(to_raw_response(response))

            #print(response.decode())
            self.transport.write(response)

        def on_message_complete(self):
            self.req.headers["Host"] = self.original_host.split("//")[1]
            self.req.url = "https://" + self.req.headers["Host"] + self.req.url

            self.req = self.edit_request(self.req)

            response = HttpProxy.session.request(self.req.method, self.req.url, headers=self.req.headers, data=self.req.body,
                                        proxies=ProxyServers.fiddler_proxies, verify=False)

            response = self.edit_response(response)

            self.send_response(response)

    async def run_server(self, host, port, original_host):
        loop = asyncio.get_running_loop()

        server = await loop.create_server(
            lambda: self.CustomProtocol(original_host),
            host, port)

        print(f'[HttpProxy] {original_host} server started on {host}:{str(port)}')

        async with server:
            await server.serve_forever()
