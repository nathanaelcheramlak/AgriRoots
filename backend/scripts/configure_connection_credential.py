"""Provision a connection through existing write-only APIs, without browser secrets.

Interactive operator utility. Does not create accounts, approve tools or enable
connections. A credential change suspends activation according to backend policy.
"""
import argparse
import json
import sys
from getpass import getpass
from urllib.parse import urlsplit

import httpx


def api_origin(value):
    parsed = urlsplit(value)
    if (parsed.username or parsed.password or parsed.query or parsed.fragment or
            parsed.path not in ("", "/") or not parsed.hostname or
            (parsed.scheme != "https" and not (parsed.scheme == "http" and parsed.hostname in {"localhost", "127.0.0.1", "::1"}))):
        raise argparse.ArgumentTypeError("Use an HTTPS API origin, or local HTTP for development; no credentials, path or query.")
    return value.rstrip("/")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api", type=api_origin, default="http://127.0.0.1:8000")
    args = parser.parse_args()
    if not sys.stdin.isatty():
        raise SystemExit("Use an interactive terminal. Credentials cannot be supplied in arguments or piped input.")
    phone = input("Existing administrator phone: ").strip()
    password = getpass("Administrator password (hidden): ")
    with httpx.Client(base_url=args.api, timeout=30, follow_redirects=False, trust_env=False) as client:
        login = client.post("/api/auth/login", json={"phone_number": phone, "password": password})
        password = None
        if login.status_code != 200:
            raise SystemExit(f"Login failed (HTTP {login.status_code}); credentials were not displayed.")
        token = login.json()["access_token"]
        client.headers["Authorization"] = "Bearer " + token
        identity = client.get("/api/v1/me")
        if identity.status_code != 200 or identity.json().get("role") != "office_admin":
            raise SystemExit("An active office administrator is required.")
        from uuid import UUID
        connection_id = str(UUID(input("Backend connection UUID: ").strip()))
        detail = client.get(f"/api/v1/integrations/{connection_id}")
        if detail.status_code != 200:
            raise SystemExit("Connection was not found in the authorized office.")
        print("Connection:", detail.json()["name"])
        scope = input("Provider account scope label (not a secret): ").strip()
        encoded = getpass("New credential (hidden; plain value or JSON object): ")
        value = json.loads(encoded) if encoded.lstrip().startswith("{") else encoded
        if not value or not scope:
            raise SystemExit("A credential and account scope are required.")
        if input("Type STORE to provision this credential and suspend existing activation: ") != "STORE":
            raise SystemExit("No credential write was requested.")
        result = client.put(f"/api/v1/integrations/{connection_id}/credential", json={"value": value, "principal_scope": scope})
        value = encoded = token = None
        if result.status_code != 200:
            raise SystemExit(f"Backend rejected the write (HTTP {result.status_code}); response body suppressed. No automatic retry.")
        print("Backend credential write confirmed. Retest and approve the exact versions before activation.")


if __name__ == "__main__":
    try:
        main()
    except (httpx.HTTPError, ValueError, KeyError):
        raise SystemExit("Credential setup failed or its outcome is uncertain. Inspect backend metadata before retrying; values suppressed.") from None
