"""Pinned TLS plus random bearer credential for the first LAN control path."""
from __future__ import annotations

import hashlib
import hmac
import http.client
import json
import secrets
import ssl
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse

from .config import data_dir, read_config, write_config
from .secrets import get_secret, set_secret


class PairingError(RuntimeError):
    pass


def _atomic_private(path: Path, content: bytes) -> None:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    with path.open("xb") as f:
        f.write(content)
    path.chmod(0o600)


def init_desktop() -> tuple[str, str]:
    """Return token ONCE and pin fingerprint. Reinitialization is refused."""
    base = data_dir()
    if any((base / name).exists() for name in ("desktop-cert.pem", "desktop-key.pem", "desktop.json")):
        raise PairingError("Desktop identity already exists; reinitialization would revoke existing peers")
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.x509.oid import NameOID

    private_key = ec.generate_private_key(ec.SECP256R1())
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Kairo Desktop")])
    now = datetime.now(timezone.utc)
    cert = (x509.CertificateBuilder().subject_name(name).issuer_name(name)
            .public_key(private_key.public_key()).serial_number(x509.random_serial_number())
            .not_valid_before(now - timedelta(minutes=5)).not_valid_after(now + timedelta(days=365))
            .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
            .sign(private_key, hashes.SHA256()))
    pem = cert.public_bytes(serialization.Encoding.PEM)
    key = private_key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                    serialization.NoEncryption())
    token = secrets.token_urlsafe(32)
    _atomic_private(base / "desktop-key.pem", key)
    _atomic_private(base / "desktop-cert.pem", pem)
    _atomic_private(base / "desktop.json", json.dumps({"token_sha256": hashlib.sha256(token.encode()).hexdigest()}).encode())
    return token, hashlib.sha256(cert.public_bytes(serialization.Encoding.DER)).hexdigest()


def fingerprint() -> str:
    from cryptography import x509
    from cryptography.hazmat.primitives import serialization
    cert = x509.load_pem_x509_certificate((data_dir() / "desktop-cert.pem").read_bytes())
    return hashlib.sha256(cert.public_bytes(serialization.Encoding.DER)).hexdigest()


def authorize(token: str) -> bool:
    config = json.loads((data_dir() / "desktop.json").read_text(encoding="utf-8"))
    actual = hashlib.sha256(token.encode()).hexdigest()
    return hmac.compare_digest(config["token_sha256"], actual)


class PeerClient:
    def __init__(self, url: str, fingerprint_sha256: str, token: str):
        address = urlparse(url)
        if address.scheme != "https" or not address.hostname or address.username or address.password or address.path not in ("", "/"):
            raise PairingError("Peer address must be a bare https://host:port URL")
        if len(fingerprint_sha256) != 64 or any(c not in "0123456789abcdef" for c in fingerprint_sha256.lower()):
            raise PairingError("Peer fingerprint must be 64 hex characters")
        self.host, self.port = address.hostname, address.port or 443
        self.fingerprint = fingerprint_sha256.lower()
        self.token = token

    def request(self, path: str, body: dict | None = None) -> dict:
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE  # Pin is verified before credentials are sent.
        conn = http.client.HTTPSConnection(self.host, self.port, context=ctx, timeout=12)
        try:
            conn.connect()
            der = conn.sock.getpeercert(binary_form=True)
            if not hmac.compare_digest(hashlib.sha256(der).hexdigest(), self.fingerprint):
                raise PairingError("TLS certificate fingerprint mismatch; no credentials were sent")
            headers = {"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"}
            conn.request("POST" if body is not None else "GET", path,
                         body=json.dumps(body).encode() if body is not None else None, headers=headers)
            response = conn.getresponse()
            result = json.loads(response.read(120_000))
            if response.status != 200:
                raise PairingError(result.get("error", "Peer request failed"))
            return result
        except (OSError, ssl.SSLError) as exc:
            raise PairingError(f"Cannot reach paired desktop: {type(exc).__name__}") from exc
        finally:
            conn.close()


def save_peer(url: str, pin: str, token: str) -> None:
    PeerClient(url, pin, token).request("/health")
    set_secret("peer", token)
    config = read_config()
    config["peer"] = {"url": url, "fingerprint": pin.lower()}
    write_config(config)


def configured_peer() -> PeerClient:
    config = read_config().get("peer")
    token = get_secret("peer")
    if not config or not token:
        raise PairingError("No peer configured, or its credential is missing from the OS keyring")
    return PeerClient(config["url"], config["fingerprint"], token)
