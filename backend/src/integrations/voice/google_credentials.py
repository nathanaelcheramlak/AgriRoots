from pathlib import Path

from src.config.settings import get_settings


def get_google_credentials():
    settings = get_settings()
    if not settings.google_application_credentials:
        return None

    credentials_path = Path(settings.google_application_credentials).expanduser()
    if not credentials_path.exists():
        raise RuntimeError(
            f"Google service account file was not found: {credentials_path}"
        )

    from google.oauth2 import service_account

    return service_account.Credentials.from_service_account_file(str(credentials_path))

