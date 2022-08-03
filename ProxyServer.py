import json, base64, re
import socket, requests

class ProxyServer:

    clientConfigUrl = "https://clientconfig.rpg.riotgames.com"
    geoPasUrl = "https://riot-geo.pas.si.riotgames.com/pas/v1/service/chat"

    authorizationBearer = ""

    port = 0
    chatPort = 0

    originalChatPort = 0
    originalChatHost = ""

    def find_free_port(self):
        with socket.socket() as s:
            s.bind(('', 0))
            return s.getsockname()[1]

    def __init__(self, chatPort):
        self.chatPort = chatPort
        self.port = self.find_free_port()


    def run_server(self, port):
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.bind(('localhost', port))
        server.listen(4)
        while True:
            connection, address = server.accept()
            response = self.recvall(connection).decode("UTF-8")
            config = self.proxy_get_config(response).json()
            config = self.edit_config(config)

            message = "HTTP/1.1 200 OK\r\n" \
                      f"Content-Length: {len(json.dumps(config))}\r\n" \
                      "Content-Type: application/json\r\n" \
                      "\r\n" \
                      f"{json.dumps(config)}"
            connection.sendall(message.encode("UTF-8"))


    def edit_config(self, config):
        if "chat.host" in config:
            config["chat.host"] = "127.0.0.1"
        if "chat.port" in config:
            self.originalChatPort = config["chat.port"]
            config["chat.port"] = self.chatPort
        if "chat.allow_bad_cert.enabled" in config:
            config["chat.allow_bad_cert.enabled"] = True
        if "chat.affinities" in config:
            if "chat.affinity.enabled" in config:
                pas = requests.get(self.geoPasUrl,headers={"Authorization": self.authorizationBearer})
                affinity = json.loads((base64.b64decode(str(pas.text).split('.')[1] + '==')))["affinity"]
                self.originalChatHost = config["chat.affinities"][affinity]

            for host in config["chat.affinities"]:
                config["chat.affinities"][host] = "127.0.0.1"

        return config


    def proxy_get_config(self, response):
        headers = {}
        r = re.search(r"(?<=user-agent: )([a-z/A-Z0-9. \-(;,)]+)",response)
        if r:
            headers["user-agent"] = r.group(0)
        r = re.search(r"(?<=Accept-Encoding: )([a-z/A-Z0-9. \-(;,)]+)", response)
        if r:
            headers["Accept-Encoding"] = r.group(0)
        r = re.search(r"(?<=X-Riot-Entitlements-JWT: )([a-z/A-Z0-9. \-(;,)_]+)", response)
        if r:
            headers["X-Riot-Entitlements-JWT"] = r.group(0)
        r = re.search(r"(?<=Authorization: )([a-z/A-Z0-9. \-(;,)_]+)", response)
        if r:
            self.authorizationBearer = r.group(0)
            headers["Authorization"] = self.authorizationBearer
        r = re.search(r"(?<=X-Riot-RSO-Identity-JWT: )([a-z/A-Z0-9. \-(;,)_]+)", response)
        if r:
            headers["X-Riot-RSO-Identity-JWT"] = r.group(0)
        r = re.search(r"(?<=Accept: )([a-z/A-Z0-9. \-(;,)]+)", response)
        if r:
            headers["Accept"] = r.group(0)

        return requests.get(self.clientConfigUrl + response.split(" ")[1], headers=headers)

    def recvall(self, sock):
        BUFF_SIZE = 4096
        data = b''
        while True:
            part = sock.recv(BUFF_SIZE)
            data += part
            if len(part) < BUFF_SIZE:
                break
        return data
