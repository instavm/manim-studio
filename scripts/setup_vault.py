"""One-shot: create a Manim Studio vault and store both credentials.

Idempotent: re-running is safe (it reuses an existing vault by name and
upserts credentials and service bindings).

    python scripts/setup_vault.py
"""
from __future__ import annotations
import os, sys, json, pathlib, requests

CTRL_API_KEY = pathlib.Path("~/.manim.txt").expanduser().read_text().strip()
OPENAI_KEY   = pathlib.Path("~/.3b1b_openai_key.txt").expanduser().read_text().strip()
BASE = "https://api.instavm.io"
VAULT_NAME = "manim-studio"

H = {"X-API-Key": CTRL_API_KEY, "Content-Type": "application/json"}


def req(method, path, **kw):
    r = requests.request(method, BASE + path, headers=H, timeout=30, **kw)
    if r.status_code >= 400:
        print(f"!! {method} {path} -> {r.status_code} {r.text[:300]}", file=sys.stderr)
        r.raise_for_status()
    return r.json() if r.text else {}


def _items(payload, *keys):
    """Vault API returns {'vaults': [...]} / {'credentials': [...]} / {'services': [...]}."""
    if isinstance(payload, dict):
        for k in keys:
            if k in payload and isinstance(payload[k], list):
                return payload[k]
        for v in payload.values():
            if isinstance(v, list):
                return v
        return []
    return payload if isinstance(payload, list) else []


def ensure_vault() -> str:
    vaults = req("GET", "/v1/vaults")
    for v in _items(vaults, "vaults", "items"):
        if v.get("name") == VAULT_NAME:
            print(f"[=] vault exists: {v['id']}")
            return v["id"]
    v = req("POST", "/v1/vaults", json={
        "name": VAULT_NAME,
        "description": "Credentials for the Manim Studio webapp",
    })
    print(f"[+] vault created: {v['id']}")
    return v["id"]


def ensure_credential(vault_id: str, name: str, value: str, desc: str) -> str:
    creds = req("GET", f"/v1/vaults/{vault_id}/credentials")
    for c in _items(creds, "credentials", "items"):
        if c.get("name") == name:
            print(f"[=] cred '{name}' exists ({c['id']}) — rotating value")
            req("POST", f"/v1/vaults/{vault_id}/credentials/{c['id']}/rotate",
                json={"value": value})
            return c["id"]
    c = req("POST", f"/v1/vaults/{vault_id}/credentials",
            json={"name": name, "value": value, "description": desc,
                  "credential_type": "api_key"})
    print(f"[+] cred '{name}' created: {c['id']}")
    return c["id"]


def ensure_service(vault_id: str, host: str, credential_name: str,
                   auth_type: str = "bearer", header: str | None = None,
                   description: str = ""):
    services = req("GET", f"/v1/vaults/{vault_id}/services")
    for s in _items(services, "services", "items"):
        if s.get("host") == host:
            print(f"[=] service host={host} already bound ({s.get('id')})")
            return s
    # auth_config keys are auth-type specific:
    #   bearer       → {"type":"bearer",  "token":   "<CRED_NAME>"}
    #   api-key      → {"type":"api-key", "header":"X-...","value":"<CRED_NAME>"}
    if auth_type == "bearer":
        auth_config: dict = {"type": "bearer", "token": credential_name}
    elif auth_type == "api-key":
        auth_config = {"type": "api-key", "header": header or "X-API-Key",
                       "key": credential_name}
    else:
        raise ValueError(f"unsupported auth_type {auth_type}")
    s = req("POST", f"/v1/vaults/{vault_id}/services", json={
        "host": host,
        "auth_config": auth_config,
        "description": description,
        "enabled": True,
    })
    print(f"[+] service host={host} bound to '{credential_name}'")
    return s


def main():
    vault_id = ensure_vault()
    ensure_credential(vault_id, "OPENAI_API_KEY",  OPENAI_KEY,   "OpenAI key for scene drafting")
    ensure_credential(vault_id, "INSTAVM_API_KEY", CTRL_API_KEY, "InstaVM control key (spawns render sandboxes)")
    ensure_service(vault_id, "api.openai.com",  "OPENAI_API_KEY",
                   auth_type="bearer",
                   description="OpenAI chat completions")
    ensure_service(vault_id, "api.instavm.io", "INSTAVM_API_KEY",
                   auth_type="api-key", header="X-API-Key",
                   description="InstaVM control plane (sandbox spawn)")

    summary = req("GET", f"/v1/vaults/{vault_id}/discover")
    print("\n[vault summary]")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
