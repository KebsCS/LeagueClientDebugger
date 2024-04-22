import asyncio, requests, re, json, base64, os
from ChatProxy import ChatProxy
from HttpProxy import HttpProxy
from ProxyServers import ProxyServers

from requests.packages.urllib3.exceptions import InsecureRequestWarning
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)


class ConfigProxy:
    chatPort = 0

    chatProxyRunning = False

    full_config = {}

    def __init__(self, chatPort, xmpp_objects):
        ConfigProxy.chatPort = chatPort
        ConfigProxy.xmpp_objects = xmpp_objects

    class CustomProtocol(HttpProxy.CustomProtocol):

        originalChatHost = ""
        originalChatPort = 0

        def edit_response(self, response: requests.Response) -> requests.Response:
            originalConfig = response.json()
            config = json.dumps(self.edit_config(originalConfig))

            config = config.replace("https://playerpreferences.riotgames.com",
                                    f"http://localhost:{ProxyServers.playerpreferences_port}")

            config = config.replace("https://api.account.riotgames.com",
                                    f"http://localhost:{ProxyServers.accounts_port}")

            config = config.replace("https://content.publishing.riotgames.com",
                                    f"http://localhost:{ProxyServers.publishing_content_port}")

            config = re.sub(r"https://\w+-\w+\.pp\.sgp\.pvp\.net", f"http://localhost:{ProxyServers.player_platform_port}", config) #pp.sgp.pvp.net

            config = re.sub(r"https://\w+\.ledge\.leagueoflegends\.com",
                            f"http://localhost:{ProxyServers.ledge_port}", config)

            config = config.replace("https://scd.riotcdn.net",
                                    f"http://localhost:{ProxyServers.scd_port}")

            config = config.replace("https://player-lifecycle-euc.publishing.riotgames.com",
                                    f"http://localhost:{ProxyServers.lifecycle_port}")

            config = config.replace("https://eu.lers.loyalty.riotgames.com",
                                    f"http://localhost:{ProxyServers.loyalty_port}")

            config = config.replace("https://pcbs.loyalty.riotgames.com",
                                    f"http://localhost:{ProxyServers.pcbs_loyalty_port}")

            config = re.sub(r"(wss://([a-z]{2,4})\.edge\.rms\.si\.riotgames\.com)",
                            f"ws://127.0.0.1", config)

            #todo "payments.pay_plugin.pmc-edge-url-template": "https://edge.%1.pmc.pay.riotgames.com",

            #print(config)
            response._content = config.encode()
            return response

        def edit_config(self, config):
            for key in config.keys():
                if key not in ConfigProxy.full_config:
                    ConfigProxy.full_config[key] = config[key]

            def ReplaceValue(key: str, value):
                if key in config:
                    config[key] = value

            def update_nested_keys(key_to_match, new_value, d=config):
                for key, value in d.items():
                    if isinstance(value, dict):
                        update_nested_keys(key_to_match, new_value, value)
                    elif key_to_match in key:
                        d[key] = new_value

            ReplaceValue("keystone.client.feature_flags.chrome_devtools.enabled", True)

            ReplaceValue("lol.client_settings.honeyfruit.account_claiming_enabled", True)
            ReplaceValue("lol.client_settings.honeyfruit.linking_settings_button_available", True)

            ReplaceValue("lol.client_settings.patch.retrieve_all_supported_game_versions", True)
            ReplaceValue("lol.client_settings.player_behavior.display_reform_card", True)
            ReplaceValue("lol.client_settings.progression.player_platform_edge.enabled", True)
            ReplaceValue("lol.client_settings.purchase_widget.player_platform_edge.enabled", True)
            ReplaceValue("lol.client_settings.store.enableCodesPage", True)
            ReplaceValue("lol.client_settings.store.enableTransfers", True)
            ReplaceValue("lol.client_settings.store.enableRPPurchase", True)

            update_nested_keys("PlayerBehavior", True)
            update_nested_keys("isSpectatorDelayConfigurable", True)
            update_nested_keys("isUsingOperationalConfig", True)

            if "lol.game_client_settings.tft_npe" in config:
                config["lol.game_client_settings.tft_npe"]["queueBypass"] = True
                config["lol.game_client_settings.tft_npe"]["shouldShowNPEQueue"] = True

            if "lol.client_settings.tft.tft_npe" in config:
                config["lol.client_settings.tft.tft_npe"]["queueBypass"] = True
                config["lol.client_settings.tft.tft_npe"]["shouldShowNPEQueue"] = True

            if "lol.client_settings.yourshop" in config:
                config["lol.client_settings.yourshop"]["Active"] = True

            ReplaceValue("lol.client_settings.champ_mastery.lcm_enabled", True)
            ReplaceValue("lol.client_settings.collections.lcm_eat_enabled", True)

            if "lol.client_settings.store.primeGamingPromo" in config:
                config["lol.client_settings.store.primeGamingPromo"]["active"] = True

            ReplaceValue("lol.client_settings.summoner.profile_privacy_feature_flag", "ENABLED")

            ReplaceValue("lol.client_settings.tft.tft_tastes_experiment_enabled", True)
            ReplaceValue("lol.client_settings.topNavUpdates.profileButtonMigration", True)
            # ReplaceValue("lol.client_settings.vanguard.enabled", True)

            if "lol.euw1.operational.spectator" in config:
                config["lol.euw1.operational.spectator"]["enabled"] = True

            # if "lol.euw1.operational.vanguard" in config:
            #     config["lol.euw1.operational.vanguard"]["enabled"] = True

            ReplaceValue("lol.game_client_settings.mobile_tft_loadout_favorites", True)
            if "lol.game_client_settings.pregame_rpd_config" in config:
                config["lol.game_client_settings.pregame_rpd_config"]["enabled"] = True
                config["lol.game_client_settings.pregame_rpd_config"]["save"] = True
                config["lol.game_client_settings.pregame_rpd_config"]["send"] = True


            # -------------- Important below

            ReplaceValue("rms.allow_bad_cert.enabled", True)
            ReplaceValue("rms.port", str(ProxyServers.rms_port))




            if "keystone.products.league_of_legends.patchlines.live" in config:
                if "platforms" in config["keystone.products.league_of_legends.patchlines.live"]:
                    for node in config["keystone.products.league_of_legends.patchlines.live"]["platforms"]["win"]["configurations"]:
                        if not node:
                            continue
                        if "arguments" in node["launcher"]:
                            node["launcher"]["arguments"].append('--system-yaml-override="Config/system.yaml"')

            if "keystone.rso_auth.url" in config:
                config["keystone.rso_auth.url"] = f"http://localhost:{ProxyServers.auth_port}"

            if "keystone.rso-authenticator.service_url" in config:
                config["keystone.rso-authenticator.service_url"] = f"http://localhost:{ProxyServers.authenticator_port}"

            for key in config.keys():
                if ".player_platform_edge.url" in key:
                    config[key] = f"http://localhost:{ProxyServers.player_platform_port}"

                if ".league_edge.url" in key:
                    config[key] = f"http://localhost:{ProxyServers.ledge_port}"

                if ".use_ledge" in key:
                    config[key] = True

            if "keystone.entitlements.url" in config:
                config["keystone.entitlements.url"] = re.sub(r'^(https?://[^/]+)', f"http://localhost:{ProxyServers.entitlements_port}", config["keystone.entitlements.url"])

            if "keystone.player-affinity.playerAffinityServiceURL" in config:
                if HttpProxy.geoPasUrl == "":
                    HttpProxy.geoPasUrl = config["keystone.player-affinity.playerAffinityServiceURL"] + "/pas/v1/service/chat"
                config["keystone.player-affinity.playerAffinityServiceURL"] = f"http://localhost:{ProxyServers.geo_port}"
            if "chat.use_tls.enabled" in config:
                config["chat.use_tls.enabled"] = False
            if "chat.host" in config:
                config["chat.host"] = "127.0.0.1"
            if "chat.port" in config:
                ConfigProxy.originalChatPort = config["chat.port"]
                config["chat.port"] = ConfigProxy.chatPort
            if "chat.allow_bad_cert.enabled" in config:
                config["chat.allow_bad_cert.enabled"] = True
            if "chat.affinities" in config: # todo idk why this method doesnt work
                # if "chat.affinity.enabled" in config and self.originalChatHost == "" and HttpProxy.geoPasBody != "":
                #     affinity = json.loads((base64.b64decode(str(HttpProxy.geoPasBody).split('.')[1] + '==')))["affinity"]
                #     self.originalChatHost = config["chat.affinities"][affinity]

                if "chat.affinity.enabled" in config and self.originalChatHost == "":
                    pas = requests.get(HttpProxy.geoPasUrl, headers={"Authorization": self.req.headers["Authorization"]},
                                       proxies=ProxyServers.fiddler_proxies, verify=False)
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

    async def run_server(self, host, port, original_host):
        loop = asyncio.get_running_loop()

        server = await loop.create_server(
            lambda: self.CustomProtocol(original_host),
            host, port)

        print(f'[ConfigProxy] Config server started on {host}:{str(port)}')

        async with server:
            await server.serve_forever()
