import asyncio, datetime, io, os, gzip, socket, ssl, subprocess
import http.client
import requests
import urllib3
try:
    from urllib3 import HTTPHeaderDict  # urllib3 >= 2.0
except ImportError:
    from urllib3._collections import HTTPHeaderDict  # urllib3 1.x
from requests.structures import CaseInsensitiveDict
from HttpProxy import HttpProxy
from ProxyServers import REQUEST_TIMEOUT
from Hosts import rewrite_etc_hosts

SNI_HOSTS = [
    # can add any host you want here, even not league related
    "data.riotgames.com",
    "telemetry.sgp.pvp.net",
    "ekg.riotgames.com",

    #"clientconfig.rpg.riotgames.com", # uncaught, probably from RC. But only passes sieve patcher url so it's not needed
    #"api.hcaptcha.com", # also used in RC, uncomment to see the requests

]

# hosts file always listens on 443
LISTEN_PORT = 443
UPSTREAM_PORT = 443  # real server port

base_dir = os.path.dirname(os.path.abspath(__file__))
ca_cert_path = os.path.join(base_dir, "sni_ca.pem")
ca_key_path = os.path.join(base_dir, "sni_ca_key.pem")
leaf_dir = os.path.join(base_dir, "sni_certs")

real_ips = {}

# id(sslobj) -> server name, filled by the sni callback and consumed in
# connection_made, which is the first place the protocol gets to see the transport
_pending_sni = {}
_leaf_contexts = {}


def ensure_ca():
    if os.path.exists(ca_cert_path) and os.path.exists(ca_key_path):
        return

    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import NameOID

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Local CA")])
    now = datetime.datetime.now(datetime.timezone.utc)
    cert = (x509.CertificateBuilder()
            .subject_name(name).issuer_name(name)
            .public_key(key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(now - datetime.timedelta(days=1))
            .not_valid_after(now + datetime.timedelta(days=3650))
            .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
            .add_extension(x509.KeyUsage(digital_signature=False, content_commitment=False,
                                         key_encipherment=False, data_encipherment=False,
                                         key_agreement=False, key_cert_sign=True, crl_sign=True,
                                         encipher_only=False, decipher_only=False), critical=True)
            .add_extension(x509.SubjectKeyIdentifier.from_public_key(key.public_key()), critical=False)
            .sign(key, hashes.SHA256()))

    with open(ca_key_path, 'wb') as file:
        file.write(key.private_bytes(serialization.Encoding.PEM,
                                     serialization.PrivateFormat.PKCS8,
                                     serialization.NoEncryption()))
    with open(ca_cert_path, 'wb') as file:
        file.write(cert.public_bytes(serialization.Encoding.PEM))
    print("[SniProxy] Generated a new CA")


def ensure_ca_trusted() -> bool:
    ensure_ca()

    machine = subprocess.run(["certutil", "-addstore", "Root", ca_cert_path],
                             capture_output=True)
    if machine.returncode == 0:
        return True

    user = subprocess.run(["certutil", "-user", "-addstore", "Root", ca_cert_path],
                          capture_output=True)
    if user.returncode == 0:
        print("[SniProxy] CA added to the current user store")
        return True

    print(f"[SniProxy] Could not install the CA: {user.stderr.decode(errors='replace')}")
    return False


def _leaf_context(host: str) -> ssl.SSLContext:
    if host in _leaf_contexts:
        return _leaf_contexts[host]

    os.makedirs(leaf_dir, exist_ok=True)
    cert_path = os.path.join(leaf_dir, host + ".pem")
    key_path = os.path.join(leaf_dir, host + ".key")

    if not (os.path.exists(cert_path) and os.path.exists(key_path)):
        from cryptography import x509
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import rsa
        from cryptography.x509.oid import NameOID, ExtendedKeyUsageOID

        with open(ca_key_path, 'rb') as file:
            ca_key = serialization.load_pem_private_key(file.read(), password=None)
        with open(ca_cert_path, 'rb') as file:
            ca_cert = x509.load_pem_x509_certificate(file.read())

        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        now = datetime.datetime.now(datetime.timezone.utc)
        cert = (x509.CertificateBuilder()
                .subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, host)]))
                .issuer_name(ca_cert.subject)
                .public_key(key.public_key())
                .serial_number(x509.random_serial_number())
                .not_valid_before(now - datetime.timedelta(days=1))
                .not_valid_after(now + datetime.timedelta(days=397))  # chrome cap
                .add_extension(x509.SubjectAlternativeName([x509.DNSName(host)]), critical=False)
                .add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key(ca_key.public_key()), critical=False)
                .add_extension(x509.SubjectKeyIdentifier.from_public_key(key.public_key()), critical=False)
                .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
                .add_extension(x509.KeyUsage(digital_signature=True, content_commitment=False,
                                             key_encipherment=True, data_encipherment=False,
                                             key_agreement=False, key_cert_sign=False, crl_sign=False,
                                             encipher_only=False, decipher_only=False), critical=True)
                .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]), critical=False)
                .sign(ca_key, hashes.SHA256()))

        with open(key_path, 'wb') as file:
            file.write(key.private_bytes(serialization.Encoding.PEM,
                                         serialization.PrivateFormat.PKCS8,
                                         serialization.NoEncryption()))
        with open(cert_path, 'wb') as file:
            file.write(cert.public_bytes(serialization.Encoding.PEM))
        print(f"[SniProxy] Generated a certificate for {host}")

    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(cert_path, key_path)
    _leaf_contexts[host] = context
    return context


def _sni_callback(sslobj, server_name, ssl_context):
    # the name isn't reachable from the protocol later, python doesn't expose the
    # received sni on the server side, so it is parked here by ssl object identity
    #print(f"[SniProxy] Handshake for {server_name}")
    _pending_sni[id(sslobj)] = server_name
    try:
        # the context has to be assigned on the ssl object, returning it makes python
        # read the return value as an integer tls alert and the handshake dies
        sslobj.context = _leaf_context(server_name)
    except Exception as e:
        print(f"[SniProxy] Certificate for {server_name} failed: {e!r}")
        return ssl.ALERT_INTERNAL_ERROR
    return None


def resolve_real_hosts(hosts=None):
    for host in hosts or SNI_HOSTS:
        try:
            response = requests.get("https://1.1.1.1/dns-query",
                                    params={"name": host, "type": "A"},
                                    headers={"accept": "application/dns-json"},
                                    timeout=10,
                                    proxies={"http": None, "https": None})
            answers = [a["data"] for a in response.json().get("Answer", []) if a.get("type") == 1]
            if answers:
                real_ips[host] = answers[0]
        except Exception as e:
            print(f"[SniProxy] Could not resolve {host} over https: {e!r}")


def forward_upstream(req) -> requests.Response:
    from urllib.parse import urlparse

    host = req.headers["Host"]
    if host not in real_ips:
        resolve_real_hosts([host])
    ip = real_ips.get(host)
    if ip is None:
        raise RuntimeError(f"no upstream address for {host}")

    uri = urlparse(req.url)
    path = uri.path + (f"?{uri.query}" if uri.query else "")

    headers = {name: value for name, value in req.headers.items()
               if name.lower() not in ("connection", "keep-alive", "proxy-connection",
                                       "transfer-encoding", "upgrade", "content-length")}

    context = ssl.create_default_context()
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE

    sock = socket.create_connection((ip, UPSTREAM_PORT), timeout=REQUEST_TIMEOUT[0])
    try:
        conn = http.client.HTTPConnection(host, timeout=REQUEST_TIMEOUT[1])
        conn.sock = context.wrap_socket(sock, server_hostname=host)
        conn.request(req.method, path, body=req.body, headers=headers)
        resp = conn.getresponse()
        content = resp.read()
        try:
            conn.close()
        except Exception:
            pass
    except Exception:
        sock.close()
        raise

    if resp.headers.get("Content-Encoding", "").lower() == "gzip":
        try:
            content = gzip.decompress(content)
        except Exception:
            pass

    raw_headers = HTTPHeaderDict(resp.headers.items())
    raw = urllib3.HTTPResponse(body=io.BytesIO(content), headers=raw_headers,
                               status=resp.status, version=resp.version,
                               reason=resp.reason, preload_content=False)

    response = requests.Response()
    response.status_code = resp.status
    response.reason = resp.reason
    response.headers = CaseInsensitiveDict(raw_headers)
    response.raw = raw
    response.url = req.url
    response.request = req
    response._content = content
    response._content_consumed = True
    return response


class SniProtocol(HttpProxy.CustomProtocol):
    def __init__(self):
        super().__init__("")  # original_host replaced with the sni name in connection_made

    def connection_made(self, transport):
        sslobj = transport.get_extra_info("ssl_object")
        server_name = _pending_sni.pop(id(sslobj), None) if sslobj else None
        if not server_name:
            server_name = SNI_HOSTS[0]
            print(f"[SniProxy] connection without sni, assuming {server_name}")
        self.original_host = f"https://{server_name}"
        super().connection_made(transport)

    def forward(self, req):
        return forward_upstream(req)


class HttpsSniProxy:
    @staticmethod
    async def run_server(host="127.0.0.1", port=LISTEN_PORT):
        trusted = await asyncio.to_thread(ensure_ca_trusted)
        if not trusted:
            print("[SniProxy] CA is not trusted, the client will reject the proxied connections")
        await asyncio.to_thread(resolve_real_hosts)

        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.sni_callback = _sni_callback

        # a default certificate is required for the handshake
        await asyncio.to_thread(_leaf_context, SNI_HOSTS[0])
        context.load_cert_chain(os.path.join(leaf_dir, SNI_HOSTS[0] + ".pem"),
                                os.path.join(leaf_dir, SNI_HOSTS[0] + ".key"))

        loop = asyncio.get_running_loop()
        try:
            server = await loop.create_server(SniProtocol, host, port, ssl=context)
        except Exception as e:
            print(f"[SniProxy] FAILED to bind {host}:{port}: {e!r} "
                  f"- check 'netstat -ano | findstr :{port}'")
            raise

        print(f"[SniProxy] Serving {', '.join(SNI_HOSTS)} on {host}:{port}")
        async with server:
            await server.serve_forever()


def port_holders(port: int) -> list:
    """[(process name, pid)] of everything listening on the port, on any address."""
    import psutil

    holders = []
    seen = set()
    for conn in psutil.net_connections(kind="tcp"):
        if conn.status == psutil.CONN_LISTEN and conn.laddr.port == port \
                and conn.pid and conn.pid not in seen:
            seen.add(conn.pid)
            try:
                name = psutil.Process(conn.pid).name()
            except psutil.Error:
                name = f"<pid {conn.pid}>"
            holders.append((name, conn.pid))
    return holders


def can_bind(port: int, host="127.0.0.1") -> bool:
    """Probes the exact bind the server would do. SO_EXCLUSIVEADDRUSE (windows)
    prevents the probe from stealing the port from or shadowing another socket."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        try:
            sock.bind((host, port))
            return True
        except OSError:
            return False
