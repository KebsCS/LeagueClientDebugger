import os
from ruamel import yaml  # pip install ruamel.yaml
from ProxyServers import ProxyServers


class SystemYaml:
    regions = []
    chat = {}
    client_config = {}
    email = {}
    entitlements = {}
    lcds = {}
    ledge = {}
    payments = {}
    player_platform = {}  # pp
    rms = {}
    
    def __init__(self):
        self.path = 'C:\\Riot Games\\League of Legends\\system.yaml'
        self.path_pbe = 'C:\\Riot Games\\League of Legends (PBE)\\system.yaml'

        live_settings = os.getenv('PROGRAMDATA') + \
                        "/Riot Games/Metadata/league_of_legends.live/league_of_legends.live.product_settings.yaml"

        if os.path.exists(live_settings):
            with open(live_settings, 'r') as file:
                read_data = yaml.YAML(typ='rt').load(file)
                self.path = read_data['product_install_full_path'] + "\\system.yaml"

        pbe_settings = os.getenv('PROGRAMDATA') + \
                       "/Riot Games/Metadata/league_of_legends.pbe/league_of_legends.pbe.product_settings.yaml"

        if os.path.exists(pbe_settings):
            with open(pbe_settings, 'r') as file:
                read_data = yaml.YAML(typ='rt').load(file)
                self.path_pbe = read_data['product_install_full_path'] + "\\system.yaml"

    def read(self):
        self._read(self.path)
        self._read(self.path_pbe)

    def _read(self, path: str):
        if not os.path.exists(path):
            return
        with open(path, 'r') as fp:
            read_data = yaml.YAML(typ='rt').load(fp)

            for region in read_data['region_data']:
                self.regions.append(region)

                key = read_data['region_data'][region]["servers"]
                try:
                    self.chat[region] = key["chat"]["chat_host"] + ":" + str(key["chat"]["chat_port"])  # euw1.chat.si.riotgames.com:5223
                    self.client_config[region] = key["client_config"]["client_config_url"]  # https://clientconfig.rpg.riotgames.com
                    self.email[region] = key["email_verification"]["external_url"]  # https://email-verification.riotgames.com/api
                    email_url = self.email[region]
                    self.email[region] = email_url[:email_url.find(".com") + len(".com")]
                    self.entitlements[region] = key["entitlements"]["entitlements_url"] # https://entitlements.auth.riotgames.com/api/token/v1
                    entitlements_url = self.entitlements[region]
                    self.entitlements[region] = entitlements_url[:entitlements_url.find(".com") + len(".com")]
                    self.lcds[region] = key["lcds"]["lcds_host"] + ":" + str(key["lcds"]["lcds_port"])  #feapp.euw1.lol.pvp.net:2099
                    self.ledge[region] = key["league_edge"]["league_edge_url"]  # https://euw-red.lol.sgp.pvp.net
                    # no payments on pbe
                    self.payments[region] = key.get("payments", {}).get("payments_host", "")    # https://plstore.euw1.lol.riotgames.com
                    #todo idk why its sometimes green and breaks with mailbox endpoint
                    self.player_platform[region] = key["player_platform_edge"]["player_platform_edge_url"].replace("green", "red")   # https://euc1-red.pp.sgp.pvp.net
                    self.rms[region] = key["rms"]["rms_url"]    # wss://eu.edge.rms.si.riotgames.com:443
                except KeyError as e:
                    print(f"KeyError: {e} not found for region {region}")
                    pass

    def edit(self):
        self._edit(self.path)
        self._edit(self.path_pbe)

    def _edit(self, path: str):
        if not os.path.exists(path):
            return
        read_data = None
        with open(path, 'r') as fp:
            read_data = yaml.YAML(typ='rt').load(fp)

        for region in read_data['region_data']:
            key = read_data['region_data'][region]["servers"]

            key["email_verification"]["external_url"] = key["email_verification"]["external_url"].replace(
                self.email[region], f"http://localhost:{ProxyServers.email_port}")
            key["entitlements"]["entitlements_url"] = key["entitlements"]["entitlements_url"].replace(
                self.entitlements[region], f"http://localhost:{ProxyServers.entitlements_port}")
            key["league_edge"]["league_edge_url"] = key["league_edge"]["league_edge_url"].replace(
                self.ledge[region], f"http://localhost:{ProxyServers.ledge_port}")
            try:    # no payments on pbe
                key["payments"]["payments_host"] = key["payments"]["payments_host"].replace(
                    self.payments[region], f"http://localhost:{ProxyServers.payments_port}")
            except KeyError as e:
                pass
            key["player_platform_edge"]["player_platform_edge_url"] = key["player_platform_edge"]["player_platform_edge_url"].replace(
                self.player_platform[region], f"http://localhost:{ProxyServers.player_platform_port}")

            key["lcds"]["lcds_host"] = "127.0.0.1"
            key["lcds"]["lcds_port"] = ProxyServers.rtmp_port
            key["lcds"]["use_tls"] = False

        # save
        with open(path.replace('system.yaml', 'Config\\system.yaml'), 'w') as fp:
            yaml.YAML(typ='rt').dump(read_data, fp)


