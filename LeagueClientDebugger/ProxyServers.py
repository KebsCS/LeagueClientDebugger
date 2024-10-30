import socket


def find_free_port():
    with socket.socket() as s:
        s.bind(('', 0))
        return s.getsockname()[1]


class ProxyServers:
    fiddler_proxies = {}

    client_config_port = 0
    chat_port = 0
    accounts_port = 0
    publishing_content_port = 0
    scd_port = 0
    sieve_port = 0
    pcbs_loyalty_port = 0
    email_port = 0
    entitlements_port = 0
    ledge_port = 0
    player_platform_port = 0
    payments_port = 0
    playerpreferences_port = 0
    geo_port = 0
    auth_port = 0
    authenticator_port = 0
    rms_port = 0
    rtmp_port = 0

    player_platform_new_servers = {
        "https://usw2-red.pp.sgp.pvp.net": 0,
        "https://apse1-red.pp.sgp.pvp.net": 0,
        "https://euc1-red.pp.sgp.pvp.net": 0,
        "https://apne1-red.pp.sgp.pvp.net": 0
    }
    player_platform_uses_new = False

    loyalty_servers = {
        "https://kr.lers.loyalty.riotgames.com": 0,
        "https://latam.lers.loyalty.riotgames.com": 0,
        "https://northamerica.lers.loyalty.riotgames.com": 0,
        "https://ap.lers.loyalty.riotgames.com": 0,
        "https://eu.lers.loyalty.riotgames.com": 0,
    }

    lifecycle_servers = {
        "https://player-lifecycle-apne.publishing.riotgames.com": 0,
        "https://player-lifecycle-apse.publishing.riotgames.com": 0,
        "https://player-lifecycle-euc.publishing.riotgames.com": 0,
        "https://player-lifecycle-usw.publishing.riotgames.com": 0,
    }

    playerpreferences_new_servers = {
        "https://player-preferences-apne1.pp.sgp.pvp.net": 0,
        "https://player-preferences-euc1.pp.sgp.pvp.net": 0,
        "https://player-preferences-apse1.pp.sgp.pvp.net": 0,
        "https://player-preferences-usw2.pp.sgp.pvp.net": 0,
    }

    # lor
    lor_login_servers = {
        "https://l-americas-green.b.pvp.net": 0,
        "https://l-apac-green.b.pvp.net": 0,
        "https://l-europe-green.b.pvp.net": 0,
    }

    lor_services_servers = {
        "https://fe-americas-green.b.pvp.net": 0,
        "https://fe-apac-green.b.pvp.net": 0,
        "https://fe-europe-green.b.pvp.net": 0,
    }

    lor_spectate_servers = {
        "https://s-americas-green.b.pvp.net": 0,
        "https://s-apac-green.b.pvp.net": 0,
        "https://s-europe-green.b.pvp.net": 0,
    }
    pft_port = 0
    data_riotgames_port = 0

    # valorant
    shared_servers = {
        "https://shared.eu.a.pvp.net": 0,
        "https://shared.kr.a.pvp.net": 0,
        "https://shared.na.a.pvp.net": 0,
        "https://shared.ap.a.pvp.net": 0,
        "https://shared.pbe.a.pvp.net": 0,
        "https://shared.ext1.a.pvp.net": 0,
    }

    @staticmethod
    def assign_ports():
        for attr_name in dir(ProxyServers):
            if attr_name.endswith("_port"):
                setattr(ProxyServers, attr_name, find_free_port())

            if attr_name.endswith("_servers"):
                server_dict = getattr(ProxyServers, attr_name)
                if isinstance(server_dict, dict):
                    for server in server_dict:
                        server_dict[server] = find_free_port()
                setattr(ProxyServers, attr_name, server_dict)
