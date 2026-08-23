import os, ssl, socket, datetime, requests
from Hosts import rewrite_etc_hosts


class ChatCert:
    """The client now verifies the chat connection certificate.
    XmppTcpSocket: OpenSSL error: error:1000007d:SSL routines:OPENSSL_internal:CERTIFICATE_VERIFY_FAILED
    For simplicity use Deceive solution which is a let's encrypt certificate for a domain that resolves to 127.0.0.1"""

    domain = "deceive-localhost.molenzwiebel.xyz"
    pfx_url = "https://mln.cx/deceive/localhost.pfx"

    # redownload when the certificate expires in less than this many days
    renew_days = 20

    base_dir = os.path.dirname(os.path.abspath(__file__))
    cert_path = os.path.join(base_dir, "chat_cert.pem")
    key_path = os.path.join(base_dir, "chat_key.pem")

    ssl_context = None

    @staticmethod
    def _expires_in_days() -> int:
        from cryptography import x509

        with open(ChatCert.cert_path, 'rb') as file:
            cert = x509.load_pem_x509_certificate(file.read())

        not_after = getattr(cert, "not_valid_after_utc", None)
        if not_after is None:
            not_after = cert.not_valid_after.replace(tzinfo=datetime.timezone.utc)

        return (not_after - datetime.datetime.now(datetime.timezone.utc)).days

    @staticmethod
    def _download():
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.serialization import pkcs12

        response = requests.get(ChatCert.pfx_url, timeout=15)
        response.raise_for_status()

        key, cert, chain = pkcs12.load_key_and_certificates(response.content, None)

        with open(ChatCert.key_path, 'wb') as file:
            file.write(key.private_bytes(serialization.Encoding.PEM,
                                         serialization.PrivateFormat.PKCS8,
                                         serialization.NoEncryption()))

        with open(ChatCert.cert_path, 'wb') as file:
            file.write(cert.public_bytes(serialization.Encoding.PEM))
            for ca in chain:
                file.write(ca.public_bytes(serialization.Encoding.PEM))

        print(f"[XMPP] Downloaded a new certificate, expires in {ChatCert._expires_in_days()} days")

    @staticmethod
    def get_ssl_context():
        if ChatCert.ssl_context:
            return ChatCert.ssl_context

        try:
            cached = os.path.exists(ChatCert.cert_path) and os.path.exists(ChatCert.key_path)
            if not cached or ChatCert._expires_in_days() < ChatCert.renew_days:
                ChatCert._download()
        except Exception as e:
            print(f"[XMPP] Error getting the chat certificate: {e}")
            if not (os.path.exists(ChatCert.cert_path) and os.path.exists(ChatCert.key_path)):
                return None
            print("[XMPP] Falling back to the cached certificate")

        try:
            ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            ssl_context.load_cert_chain(ChatCert.cert_path, ChatCert.key_path)
        except Exception as e:
            print(f"[XMPP] Error loading the chat certificate: {e}")
            return None

        ChatCert.ssl_context = ssl_context
        return ssl_context

    @staticmethod
    def resolves_to_localhost() -> bool:
        try:
            return "127.0.0.1" in socket.gethostbyname_ex(ChatCert.domain)[2]
        except OSError:
            return False

    @staticmethod
    def ensure_resolution() -> bool:
        """Some dns servers block answers pointing to 127.0.0.1,
        in that case the entry has to be added to the hosts file, which needs admin rights"""
        if ChatCert.resolves_to_localhost():
            return True

        print(f"[XMPP] {ChatCert.domain} doesn't resolve to 127.0.0.1, adding it to the hosts file")
        try:
            return rewrite_etc_hosts({ChatCert.domain: "127.0.0.1"}, 2)
        except Exception as e:
            print(f"[XMPP] Error writing to the hosts file: {e}")
            return False
