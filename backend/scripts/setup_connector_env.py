"""Create a private local Compose environment without printing or overwriting secrets."""

import argparse
import json
from pathlib import Path
import secrets

from cryptography.fernet import Fernet


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path(__file__).resolve().parents[1] / "private-data/compose.env")
    parser.add_argument(
        "--development", action="store_true", help="Permit local HTTP credential setup; bind API to localhost only"
    )
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    content = "\n".join(
        [
            "APP_ENV=" + ("development" if args.development else "production"),
            "POSTGRES_PASSWORD=" + secrets.token_urlsafe(32),
            "POSTGRES_APP_PASSWORD=" + secrets.token_urlsafe(32),
            "JWT_SECRET_KEY=" + secrets.token_urlsafe(48),
            "SECRET_ENCRYPTION_KEY=" + Fernet.generate_key().decode(),
            "LLM_PROVIDER=gemini",
            "GEMINI_API_KEY=",
            "GEMINI_MODEL=",
            "LIVE_TESTS_ENABLED=false",
            "LIVE_MODEL_TESTS_ENABLED=false",
            "LIVE_DIAGNOSIS_TESTS_ENABLED=false",
            "EXTERNAL_ACTIONS_ENABLED=false",
            "",
        ]
    )
    try:
        with args.output.open("x", encoding="utf-8") as target:
            target.write(content)
        args.output.chmod(0o600)
    except FileExistsError:
        raise SystemExit("Environment already exists; existing values were preserved.") from None
    policy = args.output.parent / "outbound-hosts.json"
    if not policy.exists():
        policy.write_text(
            json.dumps(
                {
                    "hosts": [
                        "api.open-meteo.com",
                        "power.larc.nasa.gov",
                        "api.isda-africa.com",
                        "climateserv.servirglobal.net",
                        "fpma.fao.org",
                        "www.arcgis.com",
                        "services5.arcgis.com",
                    ]
                },
                indent=2,
            ),
            encoding="utf-8",
        )
    print("Private environment created:", args.output.resolve())
    print("Set GEMINI_API_KEY and an explicitly verified GEMINI_MODEL locally before authorizing model runs.")


if __name__ == "__main__":
    main()
