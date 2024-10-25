import asyncio, requests, re, base64, json
from ChatProxy import ChatProxy
from HttpProxy import HttpProxy
from ProxyServers import ProxyServers
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

            original_config = response.json()
            config = json.dumps(self.edit_config(original_config))

            config = config.replace("https://playerpreferences.riotgames.com",
                                    f"http://localhost:{ProxyServers.playerpreferences_port}")

            for server in ProxyServers.playerpreferences_new_servers:
                config = config.replace(server, f"http://localhost:{ProxyServers.playerpreferences_new_servers[server]}")

            config = config.replace("https://api.account.riotgames.com",
                                    f"http://localhost:{ProxyServers.accounts_port}")

            config = config.replace("https://content.publishing.riotgames.com",
                                    f"http://localhost:{ProxyServers.publishing_content_port}")

            config = re.sub(r"https://\w+-\w+\.pp\.sgp\.pvp\.net", f"http://localhost:{ProxyServers.player_platform_port}", config) #pp.sgp.pvp.net

            config = re.sub(r"https://\w+\.ledge\.leagueoflegends\.com",
                            f"http://localhost:{ProxyServers.ledge_port}", config)

            config = config.replace("https://sieve.services.riotcdn.net",
                                    f"http://localhost:{ProxyServers.sieve_port}")

            config = config.replace("https://scd.riotcdn.net",
                                    f"http://localhost:{ProxyServers.scd_port}")

            for server in ProxyServers.lifecycle_servers:
                config = config.replace(server, f"http://localhost:{ProxyServers.lifecycle_servers[server]}")

            for server in ProxyServers.loyalty_servers:
                config = config.replace(server, f"http://localhost:{ProxyServers.loyalty_servers[server]}")

            config = config.replace("https://pcbs.loyalty.riotgames.com",
                                    f"http://localhost:{ProxyServers.pcbs_loyalty_port}")

            config = re.sub(r"(wss://([a-z]{2,4})\.edge\.rms\.si\.riotgames\.com)",
                            f"ws://127.0.0.1", config)

            #todo "payments.pay_plugin.pmc-edge-url-template": "https://edge.%1.pmc.pay.riotgames.com",

            # lor
            for server in ProxyServers.lor_login_servers:
                config = config.replace(server, f"http://localhost:{ProxyServers.lor_login_servers[server]}")
            for server in ProxyServers.lor_services_servers:
                config = config.replace(server, f"http://localhost:{ProxyServers.lor_services_servers[server]}")
            for server in ProxyServers.lor_spectate_servers:
                config = config.replace(server, f"http://localhost:{ProxyServers.lor_spectate_servers[server]}")

            # # valorant, replacing shared with localhost doesnt work, whitelisted for pvp.net
            # for server in ProxyServers.shared_servers:
            #     config = config.replace(server, f"http://127.0.0.1:{ProxyServers.shared_servers[server]}")

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
                # replace_value("lol.client_settings.vanguard.url", "")
                replace_value("anticheat.vanguard.enabled", False)

                def remove_vg_dependency(patchline: str):
                    if patchline in config:
                        if "platforms" in config[patchline]:
                            for node in config[patchline]["platforms"]["win"]["configurations"]:
                                if not node:
                                    continue
                                if "dependencies" in node:
                                    deps_copy = node["dependencies"][:]
                                    for deps in deps_copy:
                                        if not deps:
                                            continue
                                        if "id" in deps and deps["id"] == "vanguard":
                                            node["dependencies"].remove(deps)
                remove_vg_dependency("keystone.products.league_of_legends.patchlines.live")
                remove_vg_dependency("keystone.products.league_of_legends.patchlines.pbe")
                remove_vg_dependency("keystone.products.valorant.patchlines.live")

            replace_value("rms.allow_bad_cert.enabled", True)
            replace_value("rms.port", str(ProxyServers.rms_port))

            replace_value("rndb.client_settings.pft_host", f"localhost:{ProxyServers.pft_port}")
            replace_value("rndb.client_settings.ap_collector_dns_record", f"http://localhost:{ProxyServers.data_riotgames_port}")

            if "keystone.products.league_of_legends.patchlines.live" in config:
                if "platforms" in config["keystone.products.league_of_legends.patchlines.live"]:
                    for node in config["keystone.products.league_of_legends.patchlines.live"]["platforms"]["win"]["configurations"]:
                        if not node:
                            continue
                        if "arguments" in node["launcher"]:
                            if UiObjects.allCheckboxLC.isChecked():
                                node["launcher"]["arguments"] = ['--' + arg.strip() for arg in UiObjects.allTextLCArgs.toPlainText().split('--') if arg.strip()]
                            node["launcher"]["arguments"].append('--system-yaml-override="Config/system.yaml"')

                        if "launchable_on_update_fail" in node:
                            node["launchable_on_update_fail"] = True

            if "keystone.products.league_of_legends.patchlines.pbe" in config:
                if "platforms" in config["keystone.products.league_of_legends.patchlines.pbe"]:
                    for node in config["keystone.products.league_of_legends.patchlines.pbe"]["platforms"]["win"]["configurations"]:
                        if not node:
                            continue
                        if "arguments" in node["launcher"]:
                            if UiObjects.allCheckboxLC.isChecked():
                                node["launcher"]["arguments"] = ['--' + arg.strip() for arg in UiObjects.allTextLCArgs.toPlainText().split('--') if arg.strip()]
                            node["launcher"]["arguments"].append('--system-yaml-override="Config/system.yaml"')

                        if "launchable_on_update_fail" in node:
                            node["launchable_on_update_fail"] = True
            if not UiObjects.optionsDisableAuth.isChecked():
                replace_value("keystone.rso_auth.url", f"http://localhost:{ProxyServers.auth_port}")
                replace_value("keystone.rso-authenticator.service_url", f"http://localhost:{ProxyServers.authenticator_port}")

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
                if ConfigProxy.geo_pas_url == "":
                    ConfigProxy.geo_pas_url = config["keystone.player-affinity.playerAffinityServiceURL"] + "/pas/v1/service/chat"
                config["keystone.player-affinity.playerAffinityServiceURL"] = f"http://localhost:{ProxyServers.geo_port}"

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
