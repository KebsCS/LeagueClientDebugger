import asyncio, requests, re, json, base64,os
from ChatProxy import ChatProxy
os.environ['no_proxy'] = '*'


class ConfigProxy():
    clientConfigUrl = "https://clientconfig.rpg.riotgames.com"
    geoPasUrl = "https://riot-geo.pas.si.riotgames.com/pas/v1/service/chat"
    chatPort = 0

    chatProxyRunning = False

    def __init__(self, chatPort, xmpp_objects):
        ConfigProxy.chatPort = chatPort
        ConfigProxy.xmpp_objects = xmpp_objects

    class CustomProtocol(asyncio.Protocol):

        originalChatHost = ""
        originalChatPort = 0
        authorizationBearer = ""

        def connection_made(self, transport):
            peername = transport.get_extra_info('peername')
            print('[ConfigProxy] Connection from {}'.format(peername))
            self.transport = transport

        def data_received(self, data):
            message = data.decode("UTF-8")
            print('[ConfigProxy] Data received: {!r}'.format(message))

            originalConfig = self.proxy_get_config(message).json()
            config = self.edit_config(originalConfig)

            message = "HTTP/1.1 200 OK\r\n" \
                      f"Content-Length: {len(json.dumps(config))}\r\n" \
                      "Content-Type: application/json\r\n" \
                      "\r\n" \
                      f"{json.dumps(config)}"

            print('[ConfigProxy] Sent modified config back')
            self.transport.write(message.encode("UTF-8"))

            print('[ConfigProxy] Closed the client socket')
            self.transport.close()

        def edit_config(self, config):
            print(json.dumps(config, indent=4))

            if "keystone.products.league_of_legends.patchlines.live" in config:
                if "platforms" in config["keystone.products.league_of_legends.patchlines.live"]:
                    for node in config["keystone.products.league_of_legends.patchlines.live"]["platforms"]["win"]["configurations"]:
                        if not node:
                            continue
                        if "arguments" in node["launcher"]: pass
                            #node["launcher"]["arguments"].append("--allow-running-insecure-content")

            if "keystone.client.feature_flags.chrome_devtools.enabled" in config:
                config["keystone.client.feature_flags.chrome_devtools.enabled"] = True

            if "keystone.client.feature_flags.flaggedNameModal.disabled" in config:
                config["keystone.client.feature_flags.flaggedNameModal.disabled"] = True

            if "chat.use_tls.enabled" in config:
                config["chat.use_tls.enabled"] = False

            if "chat.host" in config:
                config["chat.host"] = "127.0.0.1"
            if "chat.port" in config:
                ConfigProxy.originalChatPort = config["chat.port"]
                config["chat.port"] = ConfigProxy.chatPort
            if "chat.allow_bad_cert.enabled" in config:
                config["chat.allow_bad_cert.enabled"] = True
            if "chat.affinities" in config:
                if "chat.affinity.enabled" in config and self.originalChatHost == "":
                    pas = requests.get(ConfigProxy.geoPasUrl, headers={"Authorization": self.authorizationBearer}, )
                    affinity = json.loads((base64.b64decode(str(pas.text).split('.')[1] + '==')))["affinity"]
                    self.originalChatHost = config["chat.affinities"][affinity]


                for host in config["chat.affinities"]:
                    config["chat.affinities"][host] = "127.0.0.1"

                if not ConfigProxy.chatProxyRunning:
                    ConfigProxy.chatProxyRunning = True
                    chatProxy = ChatProxy(ConfigProxy.xmpp_objects)
                    loop = asyncio.get_event_loop()
                    loop.create_task(chatProxy.run_from_client("127.0.0.1", ConfigProxy.chatPort,
                                                               self.originalChatHost, ConfigProxy.originalChatPort))

            return config

        def proxy_get_config(self, response):
            headers = {}
            r = re.search(r"(?<=user-agent: )([a-z/A-Z0-9. \-(;,)]+)", response)
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

            return requests.get(ConfigProxy.clientConfigUrl + response.split(" ")[1], headers=headers)

    async def run_server(self, host, port):
        loop = asyncio.get_running_loop()

        server = await loop.create_server(
            lambda: self.CustomProtocol(),
            host, port)

        print('[ConfigProxy] Server started on ' + host + ':' + str(port))

        async with server:
            await server.serve_forever()
