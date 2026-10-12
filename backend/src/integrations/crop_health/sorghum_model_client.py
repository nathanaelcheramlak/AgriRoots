import httpx

from src.config.settings import get_settings


settings = get_settings()


def predict_sorghum_disease(image_bytes: bytes, top_k: int = 3) -> list[dict]:
    if not settings.sorghum_model_server_url:
        raise RuntimeError("SORGHUM_MODEL_SERVER_URL is not configured")

    url = f"{settings.sorghum_model_server_url.rstrip('/')}/predict"
    files = {"image": ("upload.jpg", image_bytes, "image/jpeg")}

    with httpx.Client(timeout=float(settings.sorghum_model_server_timeout_seconds)) as client:
        response = client.post(url, params={"top_k": top_k}, files=files)

    if response.status_code >= 400:
        raise RuntimeError(f"Sorghum model server error ({response.status_code}): {response.text}")

    payload = response.json()
    predictions = payload.get("predictions")
    if not isinstance(predictions, list):
        raise RuntimeError("Sorghum model server returned no predictions")

    return predictions
