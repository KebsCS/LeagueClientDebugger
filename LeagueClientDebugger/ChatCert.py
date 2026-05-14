import json
import os
import pathlib
import ssl
import urllib.request
from datetime import datetime, timedelta, timezone

from cryptography.hazmat.primitives.serialization import (
    pkcs12,
    Encoding,
    PrivateFormat,
    NoEncryption,
)


DEFAULT_PFX_URL = "https://pfx.lolcert.online/localhost.pfx"
DEFAULT_CHAT_PROXY_HOST = "localhost.lolcert.online"

CONFIG_FILENAME = "chat_cert_config.json"
CACHE_DIR = pathlib.Path.home() / ".lcd_chat"
CACHE_DIR.mkdir(exist_ok=True)
PFX_PATH = CACHE_DIR / "localhost.pfx"
FULLCHAIN_PEM = CACHE_DIR / "fullchain.pem"
KEY_PEM = CACHE_DIR / "key.pem"


def _load_config():
    pfx_url = os.environ.get("LCD_PFX_URL")
    chat_host = os.environ.get("LCD_CHAT_PROXY_HOST")

    config_path = pathlib.Path(__file__).parent / CONFIG_FILENAME
    if config_path.exists():
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            pfx_url = pfx_url or cfg.get("pfx_url")
            chat_host = chat_host or cfg.get("chat_proxy_host")
        except Exception as e:
            print(f"[ChatCert] Failed to read {CONFIG_FILENAME}: {e}")

    return {
        "pfx_url": pfx_url or DEFAULT_PFX_URL,
        "chat_proxy_host": chat_host or DEFAULT_CHAT_PROXY_HOST,
    }


_config = None


def _get_config():
    global _config
    if _config is None:
        _config = _load_config()
    return _config


def get_chat_proxy_host():
    return _get_config()["chat_proxy_host"]


def _http_download(url, dest):
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "*/*",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp, open(dest, "wb") as out:
        out.write(resp.read())


def _cert_is_fresh(min_days_left=20):
    if not PFX_PATH.exists():
        return False
    try:
        data = PFX_PATH.read_bytes()
        _, cert, _ = pkcs12.load_key_and_certificates(data, password=None)
        if cert is None:
            return False
        not_after = getattr(cert, "not_valid_after_utc", None) or cert.not_valid_after
        if not_after.tzinfo is None:
            not_after = not_after.replace(tzinfo=timezone.utc)
        return not_after > datetime.now(timezone.utc) + timedelta(days=min_days_left)
    except Exception as e:
        print(f"[ChatCert] Could not read cached cert: {e}")
        return False


def _download_and_extract():
    cfg = _get_config()
    print(f"[ChatCert] Downloading certificate from {cfg['pfx_url']}")
    _http_download(cfg["pfx_url"], PFX_PATH)

    data = PFX_PATH.read_bytes()
    key, cert, additional_certs = pkcs12.load_key_and_certificates(
        data, password=None
    )
    if cert is None or key is None:
        raise RuntimeError("Downloaded PFX does not contain a valid cert or key")

    chain_pem = cert.public_bytes(Encoding.PEM)
    if additional_certs:
        for extra in additional_certs:
            chain_pem += extra.public_bytes(Encoding.PEM)
        print(f"[ChatCert] Chain with {1 + len(additional_certs)} certificates")
    else:
        print("[ChatCert] Warning: leaf cert only, no intermediates")

    FULLCHAIN_PEM.write_bytes(chain_pem)
    KEY_PEM.write_bytes(
        key.private_bytes(Encoding.PEM, PrivateFormat.PKCS8, NoEncryption())
    )
    print(f"[ChatCert] Certificate cached at {CACHE_DIR}")


def get_proxy_ssl_context():
    if not _cert_is_fresh() or not FULLCHAIN_PEM.exists() or not KEY_PEM.exists():
        _download_and_extract()

    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(certfile=str(FULLCHAIN_PEM), keyfile=str(KEY_PEM))
    return ctx
