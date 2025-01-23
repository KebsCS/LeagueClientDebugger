import asyncio, requests, re, base64, json, platform
from ChatProxy import ChatProxy
from HttpProxy import HttpProxy
from ProxyServers import ProxyServers, find_free_port
from UiObjects import UiObjects


class ConfigProxy:
    geo_pas_url = ""  # https://riot-geo.pas.si.riotgames.com/pas/v1/service/chat
    full_config = {}

    is_chat_proxy_running = False

    def __init__(self, chat_port):
        self.chat_port = chat_port

    class CustomProtocol(HttpProxy.CustomProtocol):
        def __init__(self, original_host: str, chat_port):
            super().__init__(original_host)
            self.real_chat_host = ""
            self.real_chat_port = 0

            self.chat_port = chat_port

        def edit_response(self, response: requests.Response) -> requests.Response:
            if response.status_code == 403:
                raise Exception("Client config Cloudflare blocked, open a github issue or message on discord")

            # todo, move this, repeated code in SystemYaml.py
            def match_host_and_start_proxy(text):
                def start_http_proxy(host, port):
                    if not host or host in ProxyServers.started_proxies:
                        return
                    http_proxy = HttpProxy()
                    loop = asyncio.get_event_loop()
                    loop.create_task(http_proxy.run_server("127.0.0.1", port, host))
                    ProxyServers.started_proxies[host] = port

                pattern = r"https?:\/\/(www\.)?[-a-zA-Z0-9@:%._\+~#=]{1,256}"
                last_end = 0
                new_text = ""
                for match in re.finditer(pattern, text):
                    url = match.group(0)
                    if ("localhost" in url or "127.0.0.1" in url or url in ProxyServers.excluded_hosts
                            or "riotcdn" in url or "%1" in url or "clientconfig.rpg.riotgames.com" in url or "youtube.com" in url# broken urls
                            or "shared." in url): # valorant
                        continue
                    if UiObjects.optionsDisableAuth.isChecked():
                        if "https://auth.riotgames.com" == url or "https://authenticate.riotgames.com" == url:
                            continue

                    if url not in ProxyServers.started_proxies:
                        port = find_free_port()
                        start_http_proxy(url, port)
                    new_text += text[last_end:match.start()]
                    new_text += f"http://localhost:{ProxyServers.started_proxies[url]}"
                    last_end = match.end()
                new_text += text[last_end:]
                return new_text

            original_config = response.json()
            config = json.dumps(self.edit_config(original_config))
            config = match_host_and_start_proxy(config)

            config = re.sub(r"(wss://([a-z]{2,4})\.edge\.rms\.si\.riotgames\.com)",
                            f"ws://127.0.0.1", config)

            config = re.sub(r"(wss://([a-z0-9]{2,4})-rms-edge\.esports\.rpg\.riotgames\.com)",
                            f"ws://127.0.0.1", config)

            #todo "payments.pay_plugin.pmc-edge-url-template": "https://edge.%1.pmc.pay.riotgames.com",

            #print(config)
            response._content = config.encode()
            return response

        def edit_config(self, config):
            for key in config.keys():
                if key not in ConfigProxy.full_config:
                    ConfigProxy.full_config[key] = config[key]

            def replace_value(key: str, value):
                if key in config:
                    config[key] = value

            # updates key_to_match even if it's nested
            def update_nested_keys(key_to_match, new_value, d=config):
                for key, value in d.items():
                    if isinstance(value, dict):
                        update_nested_keys(key_to_match, new_value, value)
                    elif key_to_match in key:
                        d[key] = new_value

            # replace_value("keystone.client.feature_flags.chrome_devtools.enabled", True)
            #
            # replace_value("lol.client_settings.honeyfruit.account_claiming_enabled", True)
            # replace_value("lol.client_settings.honeyfruit.linking_settings_button_available", True)
            #
            # replace_value("lol.client_settings.patch.retrieve_all_supported_game_versions", True)
            # replace_value("lol.client_settings.player_behavior.display_reform_card", True)
            # replace_value("lol.client_settings.progression.player_platform_edge.enabled", True)
            # replace_value("lol.client_settings.purchase_widget.player_platform_edge.enabled", True)
            # replace_value("lol.client_settings.store.enableCodesPage", True)
            # replace_value("lol.client_settings.store.enableTransfers", True)
            # replace_value("lol.client_settings.store.enableRPPurchase", True)
            #
            # update_nested_keys("PlayerBehavior", True)
            # update_nested_keys("isSpectatorDelayConfigurable", True)
            # update_nested_keys("isUsingOperationalConfig", True)
            #
            # if "lol.game_client_settings.tft_npe" in config:
            #     config["lol.game_client_settings.tft_npe"]["queueBypass"] = True
            #     config["lol.game_client_settings.tft_npe"]["shouldShowNPEQueue"] = True
            #
            # if "lol.client_settings.tft.tft_npe" in config:
            #     config["lol.client_settings.tft.tft_npe"]["queueBypass"] = True
            #     config["lol.client_settings.tft.tft_npe"]["shouldShowNPEQueue"] = True
            #
            # if "lol.client_settings.yourshop" in config:
            #     config["lol.client_settings.yourshop"]["Active"] = True
            #
            # replace_value("lol.client_settings.champ_mastery.lcm_enabled", True)
            # replace_value("lol.client_settings.collections.lcm_eat_enabled", True)
            #
            # if "lol.client_settings.store.primeGamingPromo" in config:
            #     config["lol.client_settings.store.primeGamingPromo"]["active"] = True
            #
            # replace_value("lol.client_settings.summoner.profile_privacy_feature_flag", "ENABLED")
            #
            # replace_value("lol.client_settings.tft.tft_tastes_experiment_enabled", True)
            # replace_value("lol.client_settings.topNavUpdates.profileButtonMigration", True)
            #
            # if "lol.euw1.operational.spectator" in config:
            #     config["lol.euw1.operational.spectator"]["enabled"] = True

            # replace_value("lol.game_client_settings.mobile_tft_loadout_favorites", True)
            # if "lol.game_client_settings.pregame_rpd_config" in config:
            #     config["lol.game_client_settings.pregame_rpd_config"]["enabled"] = True
            #     config["lol.game_client_settings.pregame_rpd_config"]["save"] = True
            #     config["lol.game_client_settings.pregame_rpd_config"]["send"] = True


            # revert change, that makes the league client load longer
            replace_value("lol.client_settings.startup.should_wait_for_home_hubs", False)

            # -------------- Important below

            if UiObjects.allDisableVanguard.isChecked():
                replace_value("lol.client_settings.vanguard.enabled", False)
                replace_value("lol.client_settings.vanguard.enabled_embedded", False)
                # replace_value("lol.client_settings.vanguard.url", "")
                replace_value("anticheat.vanguard.enabled", False)
                replace_value("anticheat.vanguard.backgroundInstall", False)
                replace_value("anticheat.vanguard.enforceExactVersionMatching", False)

                def remove_vg_dependency(patchline: str):
                    if platform.system() == "Windows":
                        platforms = "win"
                    elif platform.system() == "Darwin":
                        platforms = "mac"
                    if patchline in config:
                        if "platforms" in config[patchline] and platforms in config[patchline]["platforms"]:
                            for node in config[patchline]["platforms"][platforms]["configurations"]:
                                if not node:
                                    continue
                                if "dependencies" in node:
                                    deps_copy = node["dependencies"][:]
                                    for deps in deps_copy:
                                        if not deps:
                                            continue
                                        if "id" in deps and deps["id"] == "vanguard":
                                            node["dependencies"].remove(deps)

                remove_vg_dependency("keystone.products.valorant.patchlines.live")
                for key in config.keys():
                    if "keystone.products.league_of_legends.patchlines." in key:
                        remove_vg_dependency(key)

            replace_value("rms.allow_bad_cert.enabled", True)
            replace_value("rms.port", str(ProxyServers.rms_port))

            def override_system_yaml(patchline: str):
                if platform.system() == "Windows":
                    platforms = "win"
                elif platform.system() == "Darwin":
                    platforms = "mac"
                if patchline in config:
                    if "platforms" in config[patchline] and platforms in config[patchline]["platforms"]:
                        for node in config[patchline]["platforms"][platforms]["configurations"]:
                            if not node:
                                continue
                            if "arguments" in node["launcher"]:
                                if UiObjects.allCheckboxLC.isChecked():
                                    node["launcher"]["arguments"] = ['--' + arg.strip() for arg in UiObjects.allTextLCArgs.toPlainText().split('--') if arg.strip()]
                                node["launcher"]["arguments"].append('--system-yaml-override=Config/system.yaml')

                            if "launchable_on_update_fail" in node:
                                node["launchable_on_update_fail"] = True

            for key in config.keys():
                if ".use_ledge" in key:
                    config[key] = True

                if "keystone.products.league_of_legends.patchlines." in key:
                    override_system_yaml(key)

            if "keystone.player-affinity.playerAffinityServiceURL" in config:
                if ConfigProxy.geo_pas_url == "":
                    ConfigProxy.geo_pas_url = config["keystone.player-affinity.playerAffinityServiceURL"] + "/pas/v1/service/chat"

            replace_value("chat.use_tls.enabled", False)
            replace_value("chat.host", "127.0.0.1")
            replace_value("chat.allow_bad_cert.enabled", True)
            if "chat.port" in config:
                self.real_chat_port = config["chat.port"]
                config["chat.port"] = self.chat_port
            if "chat.affinities" in config:
                if "chat.affinity.enabled" in config and self.real_chat_host == "":
                    pas = requests.get(ConfigProxy.geo_pas_url, headers={"Authorization": self.req.headers["Authorization"]},
                                       proxies=ProxyServers.fiddler_proxies, verify=False)
                    affinity = json.loads((base64.b64decode(str(pas.text).split('.')[1] + '==')))["affinity"]
                    self.real_chat_host = config["chat.affinities"][affinity]

                for host in config["chat.affinities"]:
                    config["chat.affinities"][host] = "127.0.0.1"

                if not ConfigProxy.is_chat_proxy_running:
                    ConfigProxy.is_chat_proxy_running = True
                    chatProxy = ChatProxy()
                    loop = asyncio.get_event_loop()
                    loop.create_task(chatProxy.start_client_proxy("127.0.0.1", self.chat_port, self.real_chat_host, self.real_chat_port))

            return config

    async def run_server(self, host, port, real_host):
        loop = asyncio.get_running_loop()

        server = await loop.create_server(
            lambda: self.CustomProtocol(real_host, self.chat_port),
            host, port)

        print(f'[ConfigProxy] Config server started on {host}:{str(port)}')

        async with server:
            await server.serve_forever()
