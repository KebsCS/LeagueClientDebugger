import os
from ruamel import yaml  # pip install ruamel.yaml
from ProxyServers import ProxyServers


class SystemYaml:
    path = 'C:\\Riot Games\\League of Legends\\system.yaml'
    path_pbe = 'C:\\Riot Games\\League of Legends (PBE)\\system.yaml'

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

    @staticmethod
    def setup():
        live_settings = os.getenv('PROGRAMDATA') + \
                        "/Riot Games/Metadata/league_of_legends.live/league_of_legends.live.product_settings.yaml"

        if os.path.exists(live_settings):
            with open(live_settings, 'r', encoding='utf-8') as file:
                read_data = yaml.YAML(typ='rt').load(file)
                SystemYaml.path = read_data['product_install_full_path'] + "\\system.yaml"

        pbe_settings = os.getenv('PROGRAMDATA') + \
                       "/Riot Games/Metadata/league_of_legends.pbe/league_of_legends.pbe.product_settings.yaml"

        if os.path.exists(pbe_settings):
            with open(pbe_settings, 'r', encoding='utf-8') as file:
                read_data = yaml.YAML(typ='rt').load(file)
                SystemYaml.path_pbe = read_data['product_install_full_path'] + "\\system.yaml"

    @staticmethod
    def read():
        SystemYaml.setup()

        if not SystemYaml._read(SystemYaml.path):
            # when league not installed
            SystemYaml.set_default_values()
        SystemYaml._read(SystemYaml.path_pbe)

    @staticmethod
    def _read(path: str) -> bool:
        if not os.path.exists(path):
            return False
        with open(path, 'r', encoding='utf-8') as fp:
            read_data = yaml.YAML(typ='rt').load(fp)

            for region in read_data['region_data']:
                SystemYaml.regions.append(region)

                key = read_data['region_data'][region]["servers"]
                try:
                    SystemYaml.chat[region] = key["chat"]["chat_host"] + ":" + str(key["chat"]["chat_port"])  # euw1.chat.si.riotgames.com:5223
                    SystemYaml.client_config[region] = key["client_config"]["client_config_url"]  # https://clientconfig.rpg.riotgames.com
                    SystemYaml.email[region] = key["email_verification"]["external_url"]  # https://email-verification.riotgames.com/api
                    email_url = SystemYaml.email[region]
                    SystemYaml.email[region] = email_url[:email_url.find(".com") + len(".com")]
                    SystemYaml.entitlements[region] = key["entitlements"]["entitlements_url"] # https://entitlements.auth.riotgames.com/api/token/v1
                    entitlements_url = SystemYaml.entitlements[region]
                    SystemYaml.entitlements[region] = entitlements_url[:entitlements_url.find(".com") + len(".com")]
                    SystemYaml.lcds[region] = key["lcds"]["lcds_host"] + ":" + str(key["lcds"]["lcds_port"])  #feapp.euw1.lol.pvp.net:2099
                    SystemYaml.ledge[region] = key["league_edge"]["league_edge_url"]  # https://euw-red.lol.sgp.pvp.net
                    # no payments on pbe
                    SystemYaml.payments[region] = key.get("payments", {}).get("payments_host", "")    # https://plstore.euw1.lol.riotgames.com
                    #todo idk why its sometimes green and breaks with mailbox endpoint
                    SystemYaml.player_platform[region] = key["player_platform_edge"]["player_platform_edge_url"].replace("green", "red")   # https://euc1-red.pp.sgp.pvp.net
                    SystemYaml.rms[region] = key["rms"]["rms_url"]    # wss://eu.edge.rms.si.riotgames.com:443
                except KeyError as e:
                    print(f"KeyError: {e} not found for region {region}")
                    pass
        return True

    @staticmethod
    def edit():
        SystemYaml._edit(SystemYaml.path)
        SystemYaml._edit(SystemYaml.path_pbe)

    @staticmethod
    def _edit(path: str):
        if not os.path.exists(path):
            return
        read_data = None
        with open(path, 'r', encoding='utf-8') as fp:
            read_data = yaml.YAML(typ='rt').load(fp)

        for region in read_data['region_data']:
            key = read_data['region_data'][region]["servers"]

            key["email_verification"]["external_url"] = key["email_verification"]["external_url"].replace(
                SystemYaml.email[region], f"http://localhost:{ProxyServers.email_port}")
            key["entitlements"]["entitlements_url"] = key["entitlements"]["entitlements_url"].replace(
                SystemYaml.entitlements[region], f"http://localhost:{ProxyServers.entitlements_port}")
            key["league_edge"]["league_edge_url"] = key["league_edge"]["league_edge_url"].replace(
                SystemYaml.ledge[region], f"http://localhost:{ProxyServers.ledge_port}")
            try:    # no payments on pbe
                key["payments"]["payments_host"] = key["payments"]["payments_host"].replace(
                    SystemYaml.payments[region], f"http://localhost:{ProxyServers.payments_port}")
            except KeyError as e:
                pass
            key["player_platform_edge"]["player_platform_edge_url"] = key["player_platform_edge"]["player_platform_edge_url"].replace(
                SystemYaml.player_platform[region], f"http://localhost:{ProxyServers.player_platform_port}")

            key["lcds"]["lcds_host"] = "127.0.0.1"
            key["lcds"]["lcds_port"] = ProxyServers.rtmp_port
            key["lcds"]["use_tls"] = False

        # save
        with open(path.replace('system.yaml', 'Config\\system.yaml'), 'w', encoding='utf-8') as fp:
            yaml.YAML(typ='rt').dump(read_data, fp)

    @staticmethod
    def set_default_values():
        SystemYaml.regions = ['BR', 'EUNE', 'EUW', 'JP', 'LA1', 'LA2', 'ME1', 'NA', 'OC1', 'RU', 'TEST', 'TR']
        SystemYaml.client_config = {key: 'https://clientconfig.rpg.riotgames.com' for key in SystemYaml.regions}
        SystemYaml.email = {key: 'https://email-verification.riotgames.com' for key in SystemYaml.regions}
        SystemYaml.entitlements = {key: 'https://entitlements.auth.riotgames.com' for key in SystemYaml.regions}
        SystemYaml.chat = {'BR': 'br.chat.si.riotgames.com:5223', 'EUNE': 'eun1.chat.si.riotgames.com:5223', 'EUW': 'euw1.chat.si.riotgames.com:5223', 'JP': 'jp1.chat.si.riotgames.com:5223', 'LA1': 'la1.chat.si.riotgames.com:5223', 'LA2': 'la2.chat.si.riotgames.com:5223', 'ME1': 'me1.chat.si.riotgames.com:5223', 'NA': 'na2.chat.si.riotgames.com:5223', 'OC1': 'oc1.chat.si.riotgames.com:5223', 'RU': 'ru1.chat.si.riotgames.com:5223', 'TEST': 'na2.chat.si.riotgames.com:5223', 'TR': 'tr1.chat.si.riotgames.com:5223'}
        SystemYaml.ledge = {'BR': 'https://br-red.lol.sgp.pvp.net', 'EUNE': 'https://eune-red.lol.sgp.pvp.net', 'EUW': 'https://euw-red.lol.sgp.pvp.net', 'JP': 'https://jp-red.lol.sgp.pvp.net', 'LA1': 'https://las-red.lol.sgp.pvp.net', 'LA2': 'https://lan-red.lol.sgp.pvp.net', 'ME1': 'https://me1-red.lol.sgp.pvp.net', 'NA': 'https://na-red.lol.sgp.pvp.net', 'OC1': 'https://oce-red.lol.sgp.pvp.net', 'RU': 'https://ru-red.lol.sgp.pvp.net', 'TEST': 'https://na-red.lol.sgp.pvp.net', 'TR': 'https://tr-red.lol.sgp.pvp.net'}
        SystemYaml.lcds = {'BR': 'feapp.br1.lol.pvp.net:2099', 'EUNE': 'feapp.eun1.lol.pvp.net:2099', 'EUW': 'feapp.euw1.lol.pvp.net:2099', 'JP': 'feapp.jp1.lol.pvp.net:2099', 'LA1': 'feapp.la1.lol.pvp.net:2099', 'LA2': 'feapp.la2.lol.pvp.net:2099', 'ME1': 'feapp.me1.lol.pvp.net:2099', 'NA': 'feapp.na1.lol.pvp.net:2099', 'OC1': 'feapp.oc1.lol.pvp.net:2099', 'RU': 'feapp.ru.lol.pvp.net:2099', 'TEST': 'feapp.na1.lol.pvp.net:2099', 'TR': 'feapp.tr1.lol.pvp.net:2099'}
        SystemYaml.payments = {'BR': 'https://plstore.br.lol.riotgames.com', 'EUNE': 'https://plstore.eun1.lol.riotgames.com', 'EUW': 'https://plstore.euw1.lol.riotgames.com', 'JP': 'https://plstore.jp1.lol.riotgames.com', 'LA1': 'https://plstore2.la1.lol.riotgames.com', 'LA2': 'https://plstore2.la2.lol.riotgames.com', 'ME1': 'https://plstore.me1.lol.riotgames.com', 'NA': 'https://plstore2.na.lol.riotgames.com', 'OC1': 'https://plstore.oc1.lol.riotgames.com', 'RU': 'https://plstore.ru.lol.riotgames.com', 'TEST': 'https://plstore2.na.lol.riotgames.com', 'TR': 'https://plstore.tr.lol.riotgames.com'}
        SystemYaml.player_platform = {'BR': 'https://usw2-red.pp.sgp.pvp.net', 'EUNE': 'https://euc1-red.pp.sgp.pvp.net', 'EUW': 'https://euc1-red.pp.sgp.pvp.net', 'JP': 'https://apne1-red.pp.sgp.pvp.net', 'LA1': 'https://usw2-red.pp.sgp.pvp.net', 'LA2': 'https://usw2-red.pp.sgp.pvp.net', 'ME1': 'https://euc1-red.pp.sgp.pvp.net', 'NA': 'https://usw2-red.pp.sgp.pvp.net', 'OC1': 'https://usw2-red.pp.sgp.pvp.net', 'RU': 'https://euc1-red.pp.sgp.pvp.net', 'TEST': 'https://usw2-red.pp.sgp.pvp.net', 'TR': 'https://euc1-red.pp.sgp.pvp.net'}
        SystemYaml.rms = {'BR': 'wss://us.edge.rms.si.riotgames.com:443', 'EUNE': 'wss://eu.edge.rms.si.riotgames.com:443', 'EUW': 'wss://eu.edge.rms.si.riotgames.com:443', 'JP': 'wss://asia.edge.rms.si.riotgames.com:443', 'LA1': 'wss://us.edge.rms.si.riotgames.com:443', 'LA2': 'wss://us.edge.rms.si.riotgames.com:443', 'ME1': 'wss://eu.edge.rms.si.riotgames.com:443', 'NA': 'wss://us.edge.rms.si.riotgames.com:443', 'OC1': 'wss://us.edge.rms.si.riotgames.com:443', 'RU': 'wss://eu.edge.rms.si.riotgames.com:443', 'TEST': 'wss://us.edge.rms.si.riotgames.com:443', 'TR': 'wss://eu.edge.rms.si.riotgames.com:443'}
