"""No public image URLs. Re-encode pixels to remove metadata before private storage."""

import hashlib
import warnings
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageOps, UnidentifiedImageError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from src.config.settings import get_settings
from src.db.models.image_asset import DiagnosisReceipt, ImageAsset
from src.db.session import SessionLocal
from src.integrations.contracts import ConnectorError

MAX_IMAGE_BYTES = 10 * 1024 * 1024


def asset_path(asset):
    # All path components are generated IDs, never filenames or model input.
    root = Path(get_settings().connector_artifact_root).resolve() / "images"
    path = root / asset.office_id / (asset.id + ".bin")
    if not path.resolve().is_relative_to(root):
        raise ConnectorError("POLICY_DENIED", "Invalid private asset path")
    return path


def owned_image(db, principal, asset_id):
    row = db.get(ImageAsset, asset_id)
    if not row or row.office_id != principal.office_id:
        raise ConnectorError("POLICY_DENIED", "Image is outside the authenticated office")
    return row


def save_image(db, principal, content, media_type):
    if principal.role not in ("office_admin", "extension_officer"):
        raise ConnectorError("POLICY_DENIED", "An officer is required to upload crop images")
    if not content or len(content) > MAX_IMAGE_BYTES or media_type not in ("image/jpeg", "image/png"):
        raise ConnectorError("INPUT_VALIDATION_FAILED", "Use a JPEG or PNG image no larger than 10 MB")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(content)) as image:
                if image.format not in ("JPEG", "PNG") or image.width * image.height > 20_000_000:
                    raise ValueError()
                if (image.format == "JPEG") != (media_type == "image/jpeg"):
                    raise ValueError()
                clean = ImageOps.exif_transpose(image).convert("RGB")
                target = BytesIO()
                # Reconstruct only pixels; EXIF, ICC, GPS and source comments are discarded.
                Image.frombytes("RGB", clean.size, clean.tobytes()).save(target, format="JPEG", quality=90)
                data = target.getvalue()
                if len(data) > MAX_IMAGE_BYTES:
                    raise ValueError()
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombWarning, Image.DecompressionBombError):
        raise ConnectorError("INPUT_VALIDATION_FAILED", "Invalid, oversized or unsupported crop image") from None
    row = ImageAsset(
        office_id=principal.office_id,
        created_by=principal.user_id,
        sha256=hashlib.sha256(data).hexdigest(),
        media_type="image/jpeg",
        byte_size=len(data),
    )
    db.add(row)
    db.flush()
    path = asset_path(row)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("xb") as file:
            file.write(data)
        path.chmod(0o600)
        db.commit()
    except BaseException:
        db.rollback()
        path.unlink(missing_ok=True)
        raise
    return {"id": row.id, "media_type": row.media_type, "byte_size": row.byte_size}


def claim_diagnosis(context, asset_id):
    with SessionLocal() as db:
        asset = owned_image(db, context.principal, asset_id)
        try:
            content = asset_path(asset).read_bytes()
        except OSError:
            raise ConnectorError("NO_DATA", "Private image file is unavailable") from None
        if len(content) > MAX_IMAGE_BYTES or hashlib.sha256(content).hexdigest() != asset.sha256:
            raise ConnectorError("OUTPUT_VALIDATION_FAILED", "Private image integrity check failed")
        receipt = DiagnosisReceipt(
            office_id=asset.office_id,
            image_sha256=asset.sha256,
            provider="kindwise",
            invocation_id=context.invocation_id,
            state="attempted",
        )
        db.add(receipt)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            raise ConnectorError(
                "AMBIGUOUS_OUTCOME",
                "This image already has a diagnosis submission receipt; inspect the earlier invocation",
            ) from None
        return content, asset.sha256


def complete_diagnosis(context, image_digest):
    with SessionLocal() as db:
        row = db.scalar(
            select(DiagnosisReceipt).where(
                DiagnosisReceipt.office_id == context.principal.office_id,
                DiagnosisReceipt.image_sha256 == image_digest,
                DiagnosisReceipt.invocation_id == context.invocation_id,
            )
        )
        if row:
            row.state = "completed"
            db.commit()
