import socket


def find_free_port():
    with socket.socket() as s:
        s.bind(('', 0))
        return s.getsockname()[1]


class ProxyServers:
    fiddler_proxies = {}

    client_config_port = 0
    chat_port = 0
    rms_port = 0

    # needed in esports to overwrite launch arg
    auth_port = 0

    rms_proxies = {}

    started_proxies = {}
    excluded_hosts = [
        "https://riot-client.secure.dyn.riotcdn.net",
        "https://telemetry.sgp.pvp.net",
        "https://ritoplus.secure.dyn.riotcdn.net", # AccessDenied
        "https://lol.secure.dyn.riotcdn.net", # AccessDenied
        # "https://static.rgpub.io",
        # "https://riot-geo.vts.si.riotgames.com",
        "https://legal.kr.riotgames.com",
        "https://www.riotgames.com",
        "https://riot.com",
        # "https://lolstatic-a.akamaihd.net",
        "https://login.playersupport.riotgames.com",
        "https://status.riotgames.com",
        "https://support-leagueoflegends.riotgames.com",
        "https://parents.riotgames.com",
        "https://support-wildrift.riotgames.com",
        "https://recovery.riotgames.com",
        "https://support.riotgames.com",
        "https://update-account.riotgames.com"
    ]

    @staticmethod
    def assign_ports():
        for attr_name in dir(ProxyServers):
            if attr_name.endswith("_port"):
                setattr(ProxyServers, attr_name, find_free_port())
