import httpx

from src.config.settings import get_settings


settings = get_settings()


def predict_enset_disease(image_bytes: bytes, top_k: int = 3) -> list[dict]:
    if not settings.enset_model_server_url:
        raise RuntimeError("ENSET_MODEL_SERVER_URL is not configured")

    url = f"{settings.enset_model_server_url.rstrip('/')}/predict"
    files = {"image": ("upload.jpg", image_bytes, "image/jpeg")}

    with httpx.Client(timeout=float(settings.enset_model_server_timeout_seconds)) as client:
        response = client.post(url, params={"top_k": top_k}, files=files)

    if response.status_code >= 400:
        raise RuntimeError(f"Enset model server error ({response.status_code}): {response.text}")

    payload = response.json()
    predictions = payload.get("predictions")
    if not isinstance(predictions, list):
        raise RuntimeError("Enset model server returned no predictions")

    return predictions