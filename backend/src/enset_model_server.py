from contextlib import asynccontextmanager

from fastapi import FastAPI, File, HTTPException, UploadFile, status

from src.integrations.crop_health.enset_model import predict_enset_disease, warm_enset_model


@asynccontextmanager
async def lifespan(app: FastAPI):
    # This loads the heavy .pt file into memory the second the server starts
    warm_enset_model()
    yield


app = FastAPI(title="Farmly Enset Model Server", lifespan=lifespan)


@app.get("/health")
def health_check() -> dict[str, str]:
    return {
        "status": "ok",
        "service": "Farmly Enset Model Server",
    }


@app.post("/predict")
def predict_enset(
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
        predictions = predict_enset_disease(image_bytes, top_k=top_k)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Enset model inference failed: {exc}",
        )

    return {"predictions": predictions}