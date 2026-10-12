import httpx
import logging

from src.config.settings import get_settings


settings = get_settings()
logger = logging.getLogger("uvicorn.error")


def _extract_similar_images(items: list[dict] | None) -> list[dict]:
    result: list[dict] = []
    for img in items or []:
        result.append(
            {
                "url": img.get("url"),
                "citation": img.get("citation"),
            }
        )
    return result


def _simplify_kindwise_response(data: dict) -> dict:
    result = data.get("result", {})
    is_plant = bool(((result.get("is_plant") or {}).get("binary")))

    crop_suggestions = []
    for crop in ((result.get("crop") or {}).get("suggestions") or []):
        crop_suggestions.append(
            {
                "name": crop.get("name"),
                "scientific_name": crop.get("scientific_name"),
                "probability": crop.get("probability"),
                "similar_images": _extract_similar_images(crop.get("similar_images")),
            }
        )

    disease_suggestions = []
    for dis in ((result.get("disease") or {}).get("suggestions") or []):
        disease_suggestions.append(
            {
                "name": dis.get("name"),
                "scientific_name": dis.get("scientific_name"),
                "probability": dis.get("probability"),
                "similar_images": _extract_similar_images(dis.get("similar_images")),
            }
        )

    disease_suggestions.sort(key=lambda x: x.get("probability") or 0, reverse=True)
    crop_suggestions.sort(key=lambda x: x.get("probability") or 0, reverse=True)
    if not is_plant and (crop_suggestions or disease_suggestions):
        is_plant = True

    return {
        "is_plant": is_plant,
        "crops": crop_suggestions,
        "diseases": disease_suggestions,
    }


def diagnose_with_kindwise(image_bytes: bytes, latitude: float = 9.03, longitude: float = 38.74) -> dict:
    if not settings.kindwise_crop_health_api_key:
        raise RuntimeError("KINDWISE_CROP_HEALTH_API_KEY is not configured")

    url = "https://crop.kindwise.com/api/v1/identification"
    headers = {"Api-Key": settings.kindwise_crop_health_api_key}
    data = {
        "latitude": str(latitude),
        "longitude": str(longitude),
        "similar_images": "true",
    }
    files = {"images": ("upload.jpg", image_bytes, "image/jpeg")}

    with httpx.Client(timeout=30.0) as client:
        response = client.post(url, headers=headers, data=data, files=files)

    if response.status_code >= 400:
        raise RuntimeError(f"Kindwise provider error ({response.status_code}): {response.text}")

    payload = response.json()
    if isinstance(payload, dict) and payload.get("error"):
        raise RuntimeError(f"Kindwise provider error: {payload.get('error')}")

    result = _simplify_kindwise_response(payload)
    logger.info(
        "Kindwise:crop_health response is_plant=%s crops=%s diseases=%s",
        result["is_plant"],
        len(result["crops"]),
        len(result["diseases"]),
    )
    return result

