"""OS-backed keys. No plaintext fallback in application settings."""
from __future__ import annotations

import os


class SecretUnavailable(RuntimeError):
    pass


def set_secret(name: str, value: str) -> None:
    try:
        import keyring
        keyring.set_password("Kairo", name, value)
    except Exception as exc:
        raise SecretUnavailable("An unlocked OS keyring is required to save keys") from exc


def get_secret(name: str) -> str | None:
    env_name = {"jev": "KAIRO_JEV_API_KEY", "peer": "KAIRO_PEER_TOKEN"}.get(name)
    if env_name and os.environ.get(env_name):
        return os.environ[env_name]
    try:
        import keyring
        return keyring.get_password("Kairo", name)
    except Exception:
        return None
