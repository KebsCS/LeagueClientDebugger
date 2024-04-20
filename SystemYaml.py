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
        self.path = 'C:\\Riot Games\\League of Legends\\system.yaml' #todo dont hardcode path
        self.path_pbe = 'C:\\Riot Games\\League of Legends (PBE)\\system.yaml'

    def read(self):
        self._read(self.path)
        self._read(self.path_pbe)

    def _read(self, path: str):
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
                    self.payments[region] = key["payments"]["payments_host"]    # https://plstore.euw1.lol.riotgames.com
                    #todo idk why its sometimes green and breaks with mailbox endpoint
                    self.player_platform[region] = key["player_platform_edge"]["player_platform_edge_url"].replace("green", "red")   # https://euc1-red.pp.sgp.pvp.net
                    self.rms[region] = key["rms"]["rms_url"]    # wss://eu.edge.rms.si.riotgames.com:443
                except KeyError as e:
                    # print(f"KeyError: {e} not found for region {region}")
                    pass

    def edit(self):
        read_data = None
        with open(self.path, 'r') as fp:
            read_data = yaml.YAML(typ='rt').load(fp)

        for region in read_data['region_data']:
            key = read_data['region_data'][region]["servers"]

            key["email_verification"]["external_url"] = key["email_verification"]["external_url"].replace(
                self.email[region], f"http://localhost:{ProxyServers.email_port}")
            key["entitlements"]["entitlements_url"] = key["entitlements"]["entitlements_url"].replace(
                self.entitlements[region], f"http://localhost:{ProxyServers.entitlements_port}")
            key["league_edge"]["league_edge_url"] = key["league_edge"]["league_edge_url"].replace(
                self.ledge[region], f"http://localhost:{ProxyServers.ledge_port}")
            key["payments"]["payments_host"] = key["payments"]["payments_host"].replace(
                self.payments[region], f"http://localhost:{ProxyServers.payments_port}")
            key["player_platform_edge"]["player_platform_edge_url"] = key["player_platform_edge"]["player_platform_edge_url"].replace(
                self.player_platform[region], f"http://localhost:{ProxyServers.player_platform_port}")

            key["lcds"]["lcds_host"] = "127.0.0.1"
            key["lcds"]["lcds_port"] = SystemYaml.lcds[region].split(":")[1]
            key["lcds"]["use_tls"] = False

        # save
        with open(self.path.replace('system.yaml', 'Config\\system.yaml'), 'w') as fp:
            yaml.YAML(typ='rt').dump(read_data, fp)

    def get_variable(self, name):
        return getattr(self, name)

