from contextlib import asynccontextmanager

from fastapi import FastAPI, File, HTTPException, UploadFile, status

from src.integrations.crop_health.sorghum_model import predict_sorghum_disease, warm_sorghum_model


@asynccontextmanager
async def lifespan(app: FastAPI):
    warm_sorghum_model()
    yield


app = FastAPI(title="Farmly Sorghum Model Server", lifespan=lifespan)


@app.get("/health")
def health_check() -> dict[str, str]:
    return {
        "status": "ok",
        "service": "Farmly Sorghum Model Server",
    }


@app.post("/predict")
def predict_sorghum(
    image: UploadFile = File(...),
    top_k: int = 3,
) -> dict[str, list[dict]]:
    content_type = (image.content_type or "").lower()
    if not content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Uploaded file must be an image.")

    image_bytes = image.file.read()
    if not image_bytes:
        raise HTTPException(status_code=400, detail="Uploaded image is empty.")

    try:
        predictions = predict_sorghum_disease(image_bytes, top_k=top_k)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Sorghum model inference failed: {exc}",
        )

    return {"predictions": predictions}
