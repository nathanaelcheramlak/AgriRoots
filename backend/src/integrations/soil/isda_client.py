import httpx

from src.config.settings import get_settings


settings = get_settings()


def _get_access_token(username: str, password: str) -> str:
    url = "https://api.isda-africa.com/login"
    data = {
        "grant_type": "password",
        "username": username,
        "password": password,
        "scope": "",
        "client_id": "string",
        "client_secret": "string",
    }
    headers = {
        "accept": "application/json",
        "Content-Type": "application/x-www-form-urlencoded",
    }
    with httpx.Client(timeout=10.0) as client:
        response = client.post(url, data=data, headers=headers)
    if response.status_code >= 400:
        raise RuntimeError(f"iSDA login error ({response.status_code}): {response.text}")
    return response.json().get("access_token", "")


def _extract_value(soil_data: dict, key: str):
    prop = soil_data.get("property", {}).get(key)
    if prop and isinstance(prop, list) and prop[0].get("value"):
        return prop[0]["value"].get("value")
    return None


def get_soil_summary(lat: float, lon: float, depth: str = "0-20") -> dict:
    if not settings.isda_username or not settings.isda_password:
        raise RuntimeError("ISDA_USERNAME / ISDA_PASSWORD not configured")

    token = _get_access_token(settings.isda_username, settings.isda_password)
    if not token:
        raise RuntimeError("Unable to get iSDA access token")

    url = "https://api.isda-africa.com/isdasoil/v2/soilproperty"
    params = {"lat": lat, "lon": lon, "depth": depth}
    headers = {"accept": "application/json", "Authorization": f"Bearer {token}"}
    with httpx.Client(timeout=12.0) as client:
        response = client.get(url, params=params, headers=headers)
    if response.status_code >= 400:
        raise RuntimeError(f"iSDA soil error ({response.status_code}): {response.text}")

    soil_data = response.json()
    texture_class = _extract_value(soil_data, "texture_class")
    return {
        "soil_type": texture_class,
        "texture_class": texture_class,
        "ph": _extract_value(soil_data, "ph"),
        "nitrogen_total_g_per_kg": _extract_value(soil_data, "nitrogen_total"),
        "phosphorous_extractable_ppm": _extract_value(soil_data, "phosphorous_extractable"),
        "potassium_extractable_ppm": _extract_value(soil_data, "potassium_extractable"),
        "carbon_organic_g_per_kg": _extract_value(soil_data, "carbon_organic"),
    }

