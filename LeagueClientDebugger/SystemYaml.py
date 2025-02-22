import os, asyncio, re, glob, platform
from ruamel import yaml
from ProxyServers import ProxyServers, find_free_port
from HttpProxy import HttpProxy
from RtmpProxy import RtmpProxy
from RmsProxy import RmsProxy
from UiObjects import UiObjects


class SystemYaml:
    paths = []

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
        if platform.system() == "Windows":
            base_dir = os.getenv('PROGRAMDATA', r"C:\ProgramData") + r"\Riot Games\Metadata"
        elif platform.system() == "Darwin":
            base_dir = "/Users/Shared/Riot Games/Metadata"

        pattern = os.path.join(base_dir, "league_of_legends.*")
        for folder in glob.glob(pattern):
            yaml_path = os.path.join(folder, os.path.basename(folder) + ".product_settings.yaml")
            if os.path.exists(yaml_path):
                with open(yaml_path, 'r', encoding='utf-8') as file:
                    read_data = yaml.YAML(typ='rt').load(file)
                    if 'product_install_full_path' in read_data:
                        if platform.system() == "Windows":
                            SystemYaml.paths.append(read_data['product_install_full_path'] + "/system.yaml")
                        elif platform.system() == "Darwin":
                            SystemYaml.paths.append(read_data['product_install_full_path'] + "/Contents/LoL/system.yaml")

        if not SystemYaml.paths:
            if platform.system() == "Windows":
                SystemYaml.paths.append('C:\\Riot Games\\League of Legends\\system.yaml')
                SystemYaml.paths.append('C:\\Riot Games\\League of Legends (PBE)\\system.yaml')
            elif platform.system() == "Darwin":
                SystemYaml.paths.append("/Applications/League of Legends.app")
        else:
            # live client first
            SystemYaml.paths = sorted(SystemYaml.paths, key=lambda x: ('League of Legends/system.yaml' not in x, x))

    @staticmethod
    def read():
        SystemYaml.setup()

        for path in SystemYaml.paths:
            SystemYaml._read(path)

        if not SystemYaml.regions:
            SystemYaml.set_default_values()

    @staticmethod
    def _read(path: str) -> bool:
        if not os.path.exists(path):
            print(f"{path} doesnt exist")
            return False
        with open(path, 'r', encoding='utf-8') as fp:
            read_data = yaml.YAML(typ='rt').load(fp)

            for region in read_data['region_data']:
                if region in SystemYaml.regions:
                    continue
                SystemYaml.regions.append(region)
                key = read_data['region_data'][region]["servers"]

                def safe_set(dictionary, key, key_path, append_com=False):
                    try:
                        value = eval(key_path)
                        dictionary[region] = value
                        if append_com:
                            temp = dictionary[region]
                            dictionary[region] = temp[:temp.find(".com") + len(".com")]
                    except KeyError as e:
                        if region == "PBE" or region == "PBE_TEST":
                            if str(e) == "'league_edge'":
                                dictionary[region] = "https://pbe-red.lol.sgp.pvp.net"
                            elif str(e) == "'payments'":
                                dictionary[region] = ""
                        elif "LOLTMNT" in region or "ESPORTSTMNT" in region: # esports:
                            if str(e) == "'client_config'":
                                dictionary[region] = "https://clientconfig.esports.rpg.riotgames.com"
                        else:
                            print(f"KeyError read: {e} not found for region {region}")


                safe_set(SystemYaml.chat, key, "key['chat']['chat_host'] + ':' + str(key['chat']['chat_port'])") # euw1.chat.si.riotgames.com:5223
                safe_set(SystemYaml.client_config, key, "key['client_config']['client_config_url']") # https://clientconfig.rpg.riotgames.com
                safe_set(SystemYaml.email, key,"key['email_verification']['external_url']", True)  # https://email-verification.riotgames.com/api
                safe_set(SystemYaml.entitlements, key,"key['entitlements']['entitlements_url']", True)  # https://entitlements.auth.riotgames.com/api/token/v1
                safe_set(SystemYaml.lcds, key, "key['lcds']['lcds_host'] + ':' + str(key['lcds']['lcds_port'])")  # feapp.euw1.lol.pvp.net:2099
                safe_set(SystemYaml.ledge, key,"key['league_edge']['league_edge_url']")  # https://euw-red.lol.sgp.pvp.net
                safe_set(SystemYaml.payments, key,"key['payments']['payments_host']")  # https://plstore.euw1.lol.riotgames.com
                # todo idk why its sometimes green and breaks with mailbox endpoint
                safe_set(SystemYaml.player_platform, key,"key['player_platform_edge']['player_platform_edge_url'].replace('green', 'red')")  # https://euc1-red.pp.sgp.pvp.net
                safe_set(SystemYaml.rms, key,"key['rms']['rms_url']")  # wss://eu.edge.rms.si.riotgames.com:443

        return True

    @staticmethod
    def edit():
        for path in SystemYaml.paths:
            SystemYaml._edit(path)

    @staticmethod
    def _edit(path: str):
        if not os.path.exists(path):
            return

        with open(path, 'r', encoding='utf-8') as file:
            content = file.read()

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
                        or "riotcdn" in url or "vivox" in url or "pbr.leagueoflegends.com" in url or "clientconfig.rpg.riotgames.com" in url
                        or "support.riotgames.com" in url or "vts.si" in url or "lienminh.vnggames.com" in url):
                    continue

                if url not in ProxyServers.started_proxies:
                    port = find_free_port()
                    start_http_proxy(url, port)

                    if "https://auth." in url:
                        ProxyServers.auth_port = port
                new_text += text[last_end:match.start()]
                new_text += f"http://localhost:{ProxyServers.started_proxies[url]}"
                last_end = match.end()
            new_text += text[last_end:]
            return new_text

        if UiObjects.miscDowngradeLCEnabled.isChecked():
            content = re.sub(r"(\w+)\.ledge\.leagueoflegends\.com", r"\1-red.lol.sgp.pvp.net", content)
            content = re.sub(r"prod\.(\w+)\.lol\.riotgames\.com", r"feapp.\1.lol.pvp.net", content)

        new_content = match_host_and_start_proxy(content)

        read_data = yaml.YAML(typ='rt').load(new_content)
        for region in read_data['region_data']:
            key = read_data['region_data'][region]["servers"]

            # on old patches some lcdsServiceProxy calls break when receiving the message
            # probably wrong decoding in my rtmp implementation, not a high priority to fix
            if not UiObjects.miscDowngradeLCEnabled.isChecked():
                lcds_port = find_free_port()
                rtmp_proxy = RtmpProxy()
                loop = asyncio.get_event_loop()
                try:
                    loop.create_task(
                        rtmp_proxy.start_client_proxy("127.0.0.1", lcds_port, key["lcds"]["lcds_host"], str(key["lcds"]["lcds_port"])))
                    key["lcds"]["lcds_host"] = "127.0.0.1"
                    key["lcds"]["lcds_port"] = lcds_port
                    key["lcds"]["use_tls"] = False
                except KeyError as e:
                    pass

            # todo, client config needs rms.port, find which host's port to replace
            # try:
            #     rms_port = find_free_port()
            #     rms_proxy = RmsProxy(key["rms"]["rms_url"])
            #     loop = asyncio.get_event_loop()
            #     loop.create_task(rms_proxy.start_proxy(rms_port))
            #     ProxyServers.rms_proxies[key["rms"]["rms_url"]] = rms_port
            # except KeyError as e:
            #     pass

            # todo, chat, clientconfig

        new_path = path.replace('system.yaml', 'Config/system.yaml')
        os.makedirs(os.path.dirname(new_path), exist_ok=True)  # make the Config folder if it doesn't exist
        with open(new_path, 'w', encoding='utf-8') as file:
            yaml.YAML(typ='rt').dump(read_data, file)

    @staticmethod
    def set_default_values():
        #todo, use https://raw.communitydragon.org/latest/system.yaml instead and append missing ones, like pbe
        SystemYaml.regions = ['BR', 'EUNE', 'EUW', 'JP', 'LA1', 'LA2', 'ME1', 'NA', 'OC1', 'RU', 'TEST', 'TR', 'PBE']
        SystemYaml.client_config = {key: 'https://clientconfig.rpg.riotgames.com' for key in SystemYaml.regions}
        SystemYaml.email = {key: 'https://email-verification.riotgames.com' for key in SystemYaml.regions}
        SystemYaml.entitlements = {key: 'https://entitlements.auth.riotgames.com' for key in SystemYaml.regions}
        SystemYaml.chat = {'BR': 'br.chat.si.riotgames.com:5223', 'EUNE': 'eun1.chat.si.riotgames.com:5223', 'EUW': 'euw1.chat.si.riotgames.com:5223', 'JP': 'jp1.chat.si.riotgames.com:5223', 'LA1': 'la1.chat.si.riotgames.com:5223', 'LA2': 'la2.chat.si.riotgames.com:5223', 'ME1': 'me1.chat.si.riotgames.com:5223', 'NA': 'na2.chat.si.riotgames.com:5223', 'OC1': 'oc1.chat.si.riotgames.com:5223', 'RU': 'ru1.chat.si.riotgames.com:5223', 'TEST': 'na2.chat.si.riotgames.com:5223', 'TR': 'tr1.chat.si.riotgames.com:5223', 'PBE': 'not-used.chat.si.riotgames.com:5223'}
        SystemYaml.ledge = {'BR': 'https://br-red.lol.sgp.pvp.net', 'EUNE': 'https://eune-red.lol.sgp.pvp.net', 'EUW': 'https://euw-red.lol.sgp.pvp.net', 'JP': 'https://jp-red.lol.sgp.pvp.net', 'LA1': 'https://las-red.lol.sgp.pvp.net', 'LA2': 'https://lan-red.lol.sgp.pvp.net', 'ME1': 'https://me1-red.lol.sgp.pvp.net', 'NA': 'https://na-red.lol.sgp.pvp.net', 'OC1': 'https://oce-red.lol.sgp.pvp.net', 'RU': 'https://ru-red.lol.sgp.pvp.net', 'TEST': 'https://na-red.lol.sgp.pvp.net', 'TR': 'https://tr-red.lol.sgp.pvp.net', 'PBE': 'https://pbe-red.lol.sgp.pvp.net'}
        SystemYaml.lcds = {'BR': 'feapp.br1.lol.pvp.net:2099', 'EUNE': 'feapp.eun1.lol.pvp.net:2099', 'EUW': 'feapp.euw1.lol.pvp.net:2099', 'JP': 'feapp.jp1.lol.pvp.net:2099', 'LA1': 'feapp.la1.lol.pvp.net:2099', 'LA2': 'feapp.la2.lol.pvp.net:2099', 'ME1': 'feapp.me1.lol.pvp.net:2099', 'NA': 'feapp.na1.lol.pvp.net:2099', 'OC1': 'feapp.oc1.lol.pvp.net:2099', 'RU': 'feapp.ru.lol.pvp.net:2099', 'TEST': 'feapp.na1.lol.pvp.net:2099', 'TR': 'feapp.tr1.lol.pvp.net:2099', 'PBE': 'feapp.pbe1.lol.pvp.net:2099'}
        SystemYaml.payments = {'BR': 'https://plstore.br.lol.riotgames.com', 'EUNE': 'https://plstore.eun1.lol.riotgames.com', 'EUW': 'https://plstore.euw1.lol.riotgames.com', 'JP': 'https://plstore.jp1.lol.riotgames.com', 'LA1': 'https://plstore2.la1.lol.riotgames.com', 'LA2': 'https://plstore2.la2.lol.riotgames.com', 'ME1': 'https://plstore.me1.lol.riotgames.com', 'NA': 'https://plstore2.na.lol.riotgames.com', 'OC1': 'https://plstore.oc1.lol.riotgames.com', 'RU': 'https://plstore.ru.lol.riotgames.com', 'TEST': 'https://plstore2.na.lol.riotgames.com', 'TR': 'https://plstore.tr.lol.riotgames.com', 'PBE': ''}
        SystemYaml.player_platform = {'BR': 'https://usw2-red.pp.sgp.pvp.net', 'EUNE': 'https://euc1-red.pp.sgp.pvp.net', 'EUW': 'https://euc1-red.pp.sgp.pvp.net', 'JP': 'https://apne1-red.pp.sgp.pvp.net', 'LA1': 'https://usw2-red.pp.sgp.pvp.net', 'LA2': 'https://usw2-red.pp.sgp.pvp.net', 'ME1': 'https://euc1-red.pp.sgp.pvp.net', 'NA': 'https://usw2-red.pp.sgp.pvp.net', 'OC1': 'https://usw2-red.pp.sgp.pvp.net', 'RU': 'https://euc1-red.pp.sgp.pvp.net', 'TEST': 'https://usw2-red.pp.sgp.pvp.net', 'TR': 'https://euc1-red.pp.sgp.pvp.net', 'PBE': 'https://usw2-red.pp.sgp.pvp.net'}
        SystemYaml.rms = {'BR': 'wss://us.edge.rms.si.riotgames.com:443', 'EUNE': 'wss://eu.edge.rms.si.riotgames.com:443', 'EUW': 'wss://eu.edge.rms.si.riotgames.com:443', 'JP': 'wss://asia.edge.rms.si.riotgames.com:443', 'LA1': 'wss://us.edge.rms.si.riotgames.com:443', 'LA2': 'wss://us.edge.rms.si.riotgames.com:443', 'ME1': 'wss://eu.edge.rms.si.riotgames.com:443', 'NA': 'wss://us.edge.rms.si.riotgames.com:443', 'OC1': 'wss://us.edge.rms.si.riotgames.com:443', 'RU': 'wss://eu.edge.rms.si.riotgames.com:443', 'TEST': 'wss://us.edge.rms.si.riotgames.com:443', 'TR': 'wss://eu.edge.rms.si.riotgames.com:443', 'PBE': 'wss://us.edge.rms.si.riotgames.com:443'}
