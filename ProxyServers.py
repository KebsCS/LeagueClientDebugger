import socket, asyncio


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
    sieve_port = 0 #"https://sieve.services.riotcdn.net", todo it has patch versions
    lifecycle_port = 0
    loyalty_port = 0
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


    @staticmethod
    def assign_ports():
        for attr_name in dir(ProxyServers):
            if attr_name.endswith("_port"):
                setattr(ProxyServers, attr_name, find_free_port())
