from __future__ import annotations

from io import BytesIO
from pathlib import Path
from threading import Lock
from typing import Any

from src.config.settings import get_settings
from src.integrations.crop_health.enset_labels import display_enset_class


settings = get_settings()


def _resolve_model_path(configured_path: str) -> Path:
    path = Path(configured_path)
    if path.is_file():
        return path

    backend_root = Path(__file__).resolve().parents[3]
    candidates = [backend_root / configured_path]
    parts = path.parts
    if parts and parts[0].lower() == "backend":
        candidates.append(backend_root / Path(*parts[1:]))

    for candidate in candidates:
        if candidate.is_file():
            return candidate

    searched = ", ".join(str(candidate) for candidate in [path, *candidates])
    raise FileNotFoundError(f"Enset model file not found. Checked: {searched}")


class EnsetModelRuntime:
    def __init__(self) -> None:
        self._lock = Lock()
        self._loaded = False
        self._torch: Any = None
        self._image_cls: Any = None
        self._model: Any = None
        self._transform: Any = None
        self._class_names: list[str] = []

    def _load(self) -> None:
        if self._loaded:
            return

        with self._lock:
            if self._loaded:
                return

            import torch
            import torch.nn as nn
            from PIL import Image
            from torchvision import models, transforms

            model_path = _resolve_model_path(settings.enset_model_path)
            checkpoint = torch.load(model_path, map_location="cpu")
            class_names = list(checkpoint["class_names"])
            
            # Use the img_size from the file if available, otherwise default to 224
            img_size = int(checkpoint.get("img_size") or 224)

            # Build the Enset model architecture using torchvision instead of timm
            model = models.efficientnet_b0(weights=None)
            model.classifier[1] = nn.Linear(model.classifier[1].in_features, len(class_names))
            model.load_state_dict(checkpoint["model_state_dict"])
            model.eval()

            self._torch = torch
            self._image_cls = Image
            self._model = model
            self._class_names = class_names
            
            # The exact transform you used to train the model
            self._transform = transforms.Compose(
                [
                    transforms.Resize((img_size, img_size)),
                    transforms.ToTensor(),
                    transforms.Normalize(
                        mean=[0.485, 0.456, 0.406],
                        std=[0.229, 0.224, 0.225],
                    ),
                ]
            )
            self._loaded = True

    def predict(self, image_bytes: bytes, top_k: int = 3) -> list[dict]:
        self._load()

        image = self._image_cls.open(BytesIO(image_bytes)).convert("RGB")
        tensor = self._transform(image).unsqueeze(0)

        with self._torch.inference_mode():
            logits = self._model(tensor)
            probs = self._torch.nn.functional.softmax(logits, dim=1)[0]

        k = min(top_k, len(self._class_names))
        top_probs, top_idxs = self._torch.topk(probs, k=k)

        predictions: list[dict] = []
        for probability, idx in zip(top_probs.tolist(), top_idxs.tolist()):
            class_name = self._class_names[int(idx)]
            predictions.append(
                {
                    "class_name": class_name,
                    "name": display_enset_class(class_name),
                    "probability": float(probability),
                }
            )
        return predictions


_runtime = EnsetModelRuntime()


def warm_enset_model() -> None:
    _runtime._load()


def predict_enset_disease(image_bytes: bytes, top_k: int = 3) -> list[dict]:
    return _runtime.predict(image_bytes, top_k=top_k)