import asyncio
import json
import re

from src.api.schemas.diagnosis import DiagnosisResponse
from src.config.settings import get_settings
from src.db.models.user import UserProfile
from src.integrations.crop_health.kindwise_client import diagnose_with_kindwise
from src.integrations.crop_health.sorghum_labels import display_sorghum_class
from src.integrations.crop_health.sorghum_model_client import predict_sorghum_disease
from src.integrations.crop_health.enset_labels import display_enset_class
from src.integrations.crop_health.enset_model_client import predict_enset_disease
from src.integrations.llm.gemini_adapter import classify_crop_image, generate_reply
from src.integrations.soil.isda_client import get_soil_summary
from src.integrations.weather.open_meteo import get_current_and_forecast, get_weather_summary


settings = get_settings()

GEMINI_TRIAGE_MIN_CONFIDENCE = 0.35
GEMINI_TRIAGE_SUPPORTED_CROP_CONFIDENCE = 0.40

SORGHUM_SCIENTIFIC_NAMES = ("sorghum bicolor",)
SORGHUM_COMMON_NAMES = ("sorghum", "great millet", "jowar", "milo", "johnsongrass", "johnson grass")
ENSET_SCIENTIFIC_NAMES = ("ensete ventricosum",)
ENSET_COMMON_NAMES = ("enset", "ensete", "false banana", "ethiopian banana", "banana", "ensete banana")

SUPPORTED_CROP_KEYWORDS = (
    ("apple", "malus domestica"),
    ("barley", "hordeum vulgare"),
    ("beet", "beetroot", "beta vulgaris"),
    ("bell pepper", "capsicum annuum", "pepper"),
    ("blueberry", "vaccinium"),
    ("brassica", "cabbage", "kale", "broccoli", "cauliflower"),
    ("cassava", "manihot esculenta"),
    ("cherry", "prunus avium", "prunus cerasus"),
    ("corn", "maize", "zea mays"),
    ("cucumber", "cucumis sativus"),
    ("grape", "vitis vinifera"),
    ("hop", "humulus lupulus"),
    ("leek", "allium ampeloprasum"),
    ("lettuce", "lactuca sativa"),
    ("mustard", "brassica juncea", "sinapis alba"),
    ("oat", "avena sativa"),
    ("oilseed rape", "rapeseed", "canola", "brassica napus"),
    ("olive", "olea europaea"),
    ("onion", "allium cepa"),
    ("orange", "citrus sinensis"),
    ("peach", "prunus persica"),
    ("pear", "pyrus communis"),
    ("pea", "pisum sativum"),
    ("potato", "solanum tuberosum"),
    ("raspberry", "rubus idaeus"),
    ("rice", "oryza sativa"),
    ("rose", "rosa"),
    ("soybean", "soya", "glycine max"),
    ("squash", "pumpkin", "cucurbita"),
    ("strawberry", "fragaria"),
    ("sugar beet", "beta vulgaris"),
    ("sunflower", "helianthus annuus"),
    ("tomato", "solanum lycopersicum"),
    ("wheat", "triticum"),
)

SORGHUM_ADVICE = {
    "Normal_Sorghum": (
        "The sorghum looks normal from this image. Keep monitoring the field, avoid water stress, "
        "and check leaves and heads every few days for new spots, rust, mold, or smut symptoms."
    ),
    "": (
        "This may be anthracnose or red rot. Remove badly affected plant parts where practical, "
        "avoid overhead irrigation, improve field airflow, and rotate away from sorghum or related grasses next season."
    ),
    "Cereal_Grain_Molds": (
        "This may be cereal grain mold. Harvest on time, dry heads and grain quickly after harvest, "
        "store grain in a dry place, and use clean seed from healthy plants."
    ),
    "Covered_Kernel_Smut": (
        "This may be covered kernel smut. Use clean or certified seed, treat seed before planting if available, "
        "remove infected heads, and rotate crops to reduce carryover."
    ),
    "Head_Smut": (
        "This may be head smut. Remove infected heads before spores spread, use resistant varieties when available, "
        "plant clean seed, and rotate with non-host crops."
    ),
    "Loose_Smut": (
        "This may be loose smut. Use disease-free seed, treat seed before planting if available, "
        "remove infected heads early, and avoid saving seed from affected fields."
    ),
    "Rust": (
        "This may be rust. Remove heavily infected leaves where practical, avoid dense planting, "
        "monitor spread closely, and ask a local extension worker about fungicide options if rust is spreading fast."
    ),
}

ENSET_ADVICE = {
    "HealthyEnsetDataset": (
        "The enset looks healthy from this image. Keep monitoring the field and ensure "
        "proper spacing and weed control."
    ),
    "BacterialWilt": (
        "This may be bacterial wilt. Remove and safely destroy infected plants immediately. "
        "Disinfect all cutting tools before and after use to prevent spreading."
    ),
    "CormRotk": (
        "This may be corm rot. Ensure proper drainage around the plant. "
        "Avoid physical damage to the corm during cultivation."
    ),
    "FusariumWilt": (
        "This may be fusarium wilt. Use resistant varieties if available and practice "
        "strict crop rotation away from infected soil."
    ),
    "LeafSpot": (
        "This may be leaf spot. Remove infected leaves where practical. "
        "Ensure good airflow and avoid overhead watering."
    ),
    "SheathRot": (
        "This may be sheath rot. Maintain field hygiene and avoid excessive "
        "nitrogen fertilization."
    ),
}

def split_crops(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def parse_lat_lon(location: str | None) -> tuple[float, float] | None:
    if not location:
        return None
    try:
        lat_str, lon_str = [x.strip() for x in location.split(",", maxsplit=1)]
        return float(lat_str), float(lon_str)
    except Exception:
        return None


def build_profile_context(
    profile: UserProfile,
    location_used: str | None,
    crops_used: list[str],
    soil_summary: dict | None = None,
    weather_summary: dict | None = None,
    extra: dict[str, str] | None = None,
) -> dict[str, str]:
    data = {
        "full_name": profile.full_name or "",
        "location": location_used or "",
        "preferred_language": profile.preferred_language or "",
        "response_language": "English",
        "user_type": profile.user_type or "",
        "years_experience": str(profile.years_experience) if profile.years_experience is not None else "",
        "main_goal": profile.main_goal or "",
        "crops_grown": ", ".join(crops_used),
        "soil_summary": json.dumps(soil_summary, ensure_ascii=False) if soil_summary else "",
        "weather_summary": json.dumps(weather_summary, ensure_ascii=False) if weather_summary else "",
    }
    if extra:
        data.update(extra)
    return data


def _fallback_text(kind: str, crops: list[str]) -> str:
    crops_text = ", ".join(crops) if crops else "your local crops"
    if kind == "crops":
        return (
            f"For {crops_text}, start with crops that match current season rainfall and soil.\n"
            "Use quality seeds, prepare land early, and plant on time.\n"
            "Keep spacing correct and remove weeds in the first 4 weeks."
        )
    return (
        f"For {crops_text}, apply fertilizer based on soil status and crop growth stage.\n"
        "Use basal fertilizer at planting and top-dress nitrogen at vegetative stage.\n"
        "Avoid over-application and apply before expected light rainfall."
    )


def _fallback_weather_text() -> str:
    return (
        "Check the next 5 days before planning farm work.\n"
        "Do fertilizer application before light rain, not heavy rain.\n"
        "Prepare drainage if rainfall is expected, and avoid spraying during strong wind."
    )


def _fallback_diagnosis_advice(is_plant: bool, top_disease_name: str | None) -> str:
    if not is_plant:
        return "The uploaded image does not appear to be a plant. Please upload a clear crop photo."
    if top_disease_name:
        return (
            f"Possible issue detected: {top_disease_name}. "
            "Remove affected leaves, avoid overhead irrigation, and monitor spread over the next 3 to 5 days."
        )
    return (
        "No clear disease was detected from this image. "
        "Continue field monitoring and upload a closer leaf image if symptoms worsen."
    )


def _crop_display_name(candidate: dict | None, default: str = "this crop") -> str:
    if not candidate:
        return default
    return (
        str(candidate.get("name") or "").strip()
        or str(candidate.get("scientific_name") or "").strip()
        or default
    )


def _fallback_crop_diagnosis_advice(crop_name: str, top_disease_name: str | None) -> str:
    if top_disease_name:
        return (
            f"Your {crop_name} shows possible signs of {top_disease_name}. "
            "Remove affected parts where practical, avoid overhead irrigation, "
            "and monitor spread over the next 3 to 5 days."
        )
    return (
        f"No clear disease was detected on your {crop_name} from this image. "
        "Continue field monitoring and upload a closer image if symptoms worsen."
    )


def _uncertain_crop_advice() -> str:
    return (
        "Farmly can see that this may be a plant, but the crop is not clear enough to route diagnosis safely. "
        "Please upload a closer, well-lit image of the affected leaf, stem, head, fruit, grain, or visible pest."
    )


def _candidate_probability(candidate: dict | None) -> float:
    if not candidate:
        return 0.0
    try:
        return float(candidate.get("probability") or 0)
    except (TypeError, ValueError):
        return 0.0


def _confidence_value(value) -> float:
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        normalized = str(value or "").strip().lower()
        if normalized == "high":
            return 0.85
        if normalized == "medium":
            return 0.6
        if normalized == "low":
            return 0.3
    return 0.0


def _candidate_text(candidate: dict | None) -> str:
    if not candidate:
        return ""
    values = [
        candidate.get("name"),
        candidate.get("scientific_name"),
        *(candidate.get("common_names") or []),
    ]
    return " ".join(str(value).lower() for value in values if value)


def _matches_keyword(text: str, keyword: str) -> bool:
    return bool(re.search(rf"(?<![a-z]){re.escape(keyword)}(?![a-z])", text))


def _candidate_matches(candidate: dict | None, keywords: tuple[str, ...]) -> bool:
    text = _candidate_text(candidate)
    return any(_matches_keyword(text, keyword) for keyword in keywords)


def _candidate_label_values(candidate: dict | None) -> list[str]:
    if not candidate:
        return []
    values = [
        candidate.get("name"),
        *(candidate.get("common_names") or []),
    ]
    return [str(value).strip().lower() for value in values if value and str(value).strip()]


def _is_sorghum_candidate(candidate: dict | None) -> bool:
    if not candidate:
        return False

    scientific_name = str(candidate.get("scientific_name") or "").strip().lower()
    if _matches_keyword(scientific_name, "sorghum") or any(
        _matches_keyword(scientific_name, name) for name in SORGHUM_SCIENTIFIC_NAMES
    ):
        return True

    return any(
        _matches_keyword(label, name)
        for label in _candidate_label_values(candidate)
        for name in SORGHUM_COMMON_NAMES
    )


def _find_sorghum_candidate(crops: list[dict]) -> dict | None:
    top_crop = crops[0] if crops else None
    if _is_sorghum_candidate(top_crop):
        return top_crop

    for crop in crops[:5]:
        if (
            _candidate_probability(crop) >= GEMINI_TRIAGE_MIN_CONFIDENCE
            and _is_sorghum_candidate(crop)
        ):
            return crop
    return None


def _is_enset_candidate(candidate: dict | None) -> bool:
    if not candidate:
        return False

    scientific_name = str(candidate.get("scientific_name") or "").strip().lower()
    if _matches_keyword(scientific_name, "enset") or any(
        _matches_keyword(scientific_name, name) for name in ENSET_SCIENTIFIC_NAMES
    ):
        return True

    return any(
        _matches_keyword(label, name)
        for label in _candidate_label_values(candidate)
        for name in ENSET_COMMON_NAMES
    )


def _find_enset_candidate(crops: list[dict]) -> dict | None:
    top_crop = crops[0] if crops else None
    if _is_enset_candidate(top_crop):
        return top_crop

    for crop in crops[:5]:
        if (
            _candidate_probability(crop) >= settings.plant_id_enset_threshold
            and _is_enset_candidate(crop)
        ):
            return crop
    return None

def _matches_supported_crop(candidate: dict | None) -> bool:
    return any(_candidate_matches(candidate, keywords) for keywords in SUPPORTED_CROP_KEYWORDS)


def _find_supported_crop(crops: list[dict]) -> dict | None:
    top_crop = crops[0] if crops else None
    if _matches_supported_crop(top_crop):
        return top_crop

    for crop in crops[:5]:
        if (
            _candidate_probability(crop) >= GEMINI_TRIAGE_SUPPORTED_CROP_CONFIDENCE
            and _matches_supported_crop(crop)
        ):
            return crop
    return None


def _supported_crop_names_for_prompt() -> list[str]:
    names: set[str] = set()
    for keywords in SUPPORTED_CROP_KEYWORDS:
        for keyword in keywords:
            names.add(keyword)
    return sorted(names)


def _bool_value(value) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        return value.strip().lower() in {"true", "yes", "1"}
    return False


def _triage_crop_candidate(triage: dict) -> dict | None:
    crop_name = str(triage.get("crop_name") or "").strip()
    scientific_name = str(triage.get("scientific_name") or "").strip()
    supported_match = str(triage.get("supported_crop_match") or "").strip()
    common_names_raw = triage.get("common_names")

    common_names: list[str] = []
    if isinstance(common_names_raw, list):
        common_names = [str(item).strip() for item in common_names_raw if str(item).strip()]
    elif isinstance(common_names_raw, str) and common_names_raw.strip():
        common_names = [common_names_raw.strip()]

    if supported_match and supported_match.lower() not in {item.lower() for item in common_names}:
        common_names.append(supported_match)

    if not crop_name and not scientific_name and not common_names:
        return None

    display_name = crop_name or (common_names[0] if common_names else scientific_name)
    return {
        "name": display_name,
        "scientific_name": scientific_name or None,
        "common_names": common_names,
        "probability": _confidence_value(triage.get("confidence")),
        "similar_images": [],
    }


def _unsupported_crop_advice(top_crop: dict | None) -> str:
    crop_name = _crop_display_name(top_crop, default="this plant")
    return (
        f"Farmly identified {crop_name}, but disease diagnosis is not available for that crop yet. "
        "Please upload a clear sorghum image or another supported crop image for disease diagnosis."
    )


def _unclear_crop_health_advice(top_crop: dict | None) -> str:
    crop_name = _crop_display_name(top_crop)
    return (
        f"Farmly identified {crop_name}, but the disease scan could not read the crop health clearly from this photo. "
        "Please upload a closer, well-lit image of the affected leaf, stem, head, fruit, grain, or visible pest."
    )


def _sorghum_advice_text(class_name: str, confidence_status: str) -> str:
    advice = SORGHUM_ADVICE.get(
        class_name,
        "Monitor the sorghum closely and upload another clear image if symptoms change or spread.",
    )
    if confidence_status == "uncertain":
        return (
            "The sorghum model is not confident from this image. Please upload a closer, well-lit photo "
            f"from another angle. Possible result: {display_sorghum_class(class_name)}. {advice}"
        )
    return advice


def _build_sorghum_advice(
    profile: UserProfile,
    class_name: str,
    confidence_status: str,
    recent_messages: list[dict[str, str]] | None,
) -> tuple[str, bool]:
    fallback_text = _sorghum_advice_text(class_name, confidence_status)
    profile_context = build_profile_context(
        profile,
        profile.location,
        split_crops(profile.crops_grown),
        extra={
            "diagnosis_summary": json.dumps(
                {
                    "provider": "farmly_sorghum",
                    "identified_crop": "sorghum",
                    "prediction": display_sorghum_class(class_name),
                    "confidence_status": confidence_status,
                    "base_advice": fallback_text,
                },
                ensure_ascii=False,
            )
        },
    )

    try:
        text = generate_reply(
            latest_user_message=(
                "Rewrite this sorghum diagnosis into short farmer-friendly advice. "
                "The first sentence must mention sorghum by name. "
                "Keep the disease meaning and practical action from the base advice."
            ),
            recent_messages=recent_messages or [],
            profile_context=profile_context,
        )
        return text, False
    except Exception:
        return fallback_text, True


def _run_sorghum_diagnosis(
    profile: UserProfile,
    image_bytes: bytes,
    crops: list[dict],
    sorghum_crop: dict | None,
    recent_messages: list[dict[str, str]] | None,
) -> DiagnosisResponse:
    predictions = predict_sorghum_disease(image_bytes, top_k=3)
    top_prediction = predictions[0] if predictions else {
        "class_name": "Unknown",
        "name": "Unknown sorghum issue",
        "probability": 0.0,
    }
    confidence = _candidate_probability(top_prediction)

    if confidence >= settings.sorghum_confident_threshold:
        confidence_status = "confident"
        needs_retake = False
    elif confidence >= settings.sorghum_uncertain_threshold:
        confidence_status = "uncertain"
        needs_retake = True
    else:
        confidence_status = "uncertain"
        needs_retake = True

    class_name = top_prediction.get("class_name") or ""
    advice_text, used_fallback = _build_sorghum_advice(
        profile,
        class_name,
        confidence_status,
        recent_messages,
    )

    diseases = [
        {
            "name": item.get("name") or display_sorghum_class(item.get("class_name") or ""),
            "scientific_name": item.get("class_name"),
            "probability": item.get("probability"),
            "similar_images": [],
        }
        for item in predictions
    ]
    top_crop = sorghum_crop or (crops[0] if crops else None)

    return DiagnosisResponse(
        is_plant=True,
        top_crop=top_crop,
        top_disease=diseases[0] if diseases else None,
        crops=crops,
        diseases=diseases,
        advice_text=advice_text,
        used_fallback=used_fallback,
        provider="farmly_sorghum",
        confidence_status=confidence_status,
        needs_retake=needs_retake,
    )

def _enset_advice_text(class_name: str, confidence_status: str) -> str:
    advice = ENSET_ADVICE.get(
        class_name,
        "Monitor the enset closely and upload another clear image if symptoms change or spread.",
    )
    if confidence_status == "uncertain":
        return (
            "The enset model is not confident from this image. Please upload a closer, well-lit photo "
            f"from another angle. Possible result: {display_enset_class(class_name)}. {advice}"
        )
    return advice


def _build_enset_advice(
    profile: UserProfile,
    class_name: str,
    confidence_status: str,
    recent_messages: list[dict[str, str]] | None,
) -> tuple[str, bool]:
    fallback_text = _enset_advice_text(class_name, confidence_status)
    profile_context = build_profile_context(
        profile,
        profile.location,
        split_crops(profile.crops_grown),
        extra={
            "diagnosis_summary": json.dumps(
                {
                    "provider": "farmly_enset",
                    "identified_crop": "enset",
                    "prediction": display_enset_class(class_name),
                    "confidence_status": confidence_status,
                    "base_advice": fallback_text,
                },
                ensure_ascii=False,
            )
        },
    )

    try:
        text = generate_reply(
            latest_user_message=(
                "Rewrite this enset diagnosis into short farmer-friendly advice. "
                "The first sentence must mention enset by name. "
                "Keep the disease meaning and practical action from the base advice."
            ),
            recent_messages=recent_messages or [],
            profile_context=profile_context,
        )
        return text, False
    except Exception:
        return fallback_text, True


def _run_enset_diagnosis(
    profile: UserProfile,
    image_bytes: bytes,
    crops: list[dict],
    enset_crop: dict | None,
    recent_messages: list[dict[str, str]] | None,
) -> DiagnosisResponse:
    predictions = predict_enset_disease(image_bytes, top_k=3)
    top_prediction = predictions[0] if predictions else {
        "class_name": "Unknown",
        "name": "Unknown enset issue",
        "probability": 0.0,
    }
    confidence = _candidate_probability(top_prediction)

    if confidence >= settings.enset_confident_threshold:
        confidence_status = "confident"
        needs_retake = False
    elif confidence >= settings.enset_uncertain_threshold:
        confidence_status = "uncertain"
        needs_retake = True
    else:
        confidence_status = "uncertain"
        needs_retake = True

    class_name = top_prediction.get("class_name") or ""
    advice_text, used_fallback = _build_enset_advice(
        profile,
        class_name,
        confidence_status,
        recent_messages,
    )

    diseases = [
        {
            "name": item.get("name") or display_enset_class(item.get("class_name") or ""),
            "scientific_name": item.get("class_name"),
            "probability": item.get("probability"),
            "similar_images": [],
        }
        for item in predictions
    ]
    top_crop = enset_crop or (crops[0] if crops else None)

    return DiagnosisResponse(
        is_plant=True,
        top_crop=top_crop,
        top_disease=diseases[0] if diseases else None,
        crops=crops,
        diseases=diseases,
        advice_text=advice_text,
        used_fallback=used_fallback,
        provider="farmly_enset",
        confidence_status=confidence_status,
        needs_retake=needs_retake,
    )


async def collect_soil_weather_context_async(
    profile: UserProfile,
) -> tuple[str | None, list[str], dict | None, dict | None]:
    location_used = profile.location
    crops_used = split_crops(profile.crops_grown)
    lat_lon = parse_lat_lon(location_used)

    soil_summary: dict | None = None
    weather_summary: dict | None = None
    if lat_lon:
        lat, lon = lat_lon

        async def load_soil_summary() -> dict | None:
            try:
                return await asyncio.to_thread(get_soil_summary, lat, lon)
            except Exception:
                return None

        async def load_weather_summary() -> dict | None:
            try:
                return await asyncio.to_thread(get_weather_summary, lat, lon, past_days=7)
            except Exception:
                return None

        soil_summary, weather_summary = await asyncio.gather(
            load_soil_summary(),
            load_weather_summary(),
        )
    return location_used, crops_used, soil_summary, weather_summary


def collect_soil_weather_context(profile: UserProfile) -> tuple[str | None, list[str], dict | None, dict | None]:
    return asyncio.run(collect_soil_weather_context_async(profile))


def run_crop_recommendation(profile: UserProfile, recent_messages: list[dict[str, str]] | None = None) -> dict:
    location_used, crops_used, soil_summary, weather_summary = collect_soil_weather_context(profile)
    profile_context = build_profile_context(profile, location_used, crops_used, soil_summary, weather_summary)

    used_fallback = False
    try:
        text = generate_reply(
            latest_user_message=(
                "Give crop recommendation for this farmer based on profile, soil, and weather context. "
                "Return short practical advice suitable for smallholder farmers."
            ),
            recent_messages=recent_messages or [],
            profile_context=profile_context,
        )
    except Exception:
        used_fallback = True
        text = _fallback_text("crops", crops_used)

    return {
        "recommendation_text": text,
        "location_used": location_used,
        "crops_used": crops_used,
        "soil_summary": soil_summary,
        "weather_summary": weather_summary,
        "used_fallback": used_fallback,
    }


def run_fertilizer_recommendation(
    profile: UserProfile,
    target_crop: str | None = None,
    recent_messages: list[dict[str, str]] | None = None,
) -> dict:
    location_used, crops_used, soil_summary, weather_summary = collect_soil_weather_context(profile)
    crop_override = target_crop.strip() if target_crop else ""
    if crop_override:
        crops_used = [crop_override]
    profile_context = build_profile_context(profile, location_used, crops_used, soil_summary, weather_summary)

    used_fallback = False
    try:
        text = generate_reply(
            latest_user_message=(
                "Give fertilizer recommendation for this farmer based on profile, soil, weather, and target crop context. "
                "Return short practical advice with timing and simple dosage guidance."
            ),
            recent_messages=recent_messages or [],
            profile_context=profile_context,
        )
    except Exception:
        used_fallback = True
        text = _fallback_text("fertilizer", crops_used)

    return {
        "recommendation_text": text,
        "location_used": location_used,
        "crops_used": crops_used,
        "soil_summary": soil_summary,
        "weather_summary": weather_summary,
        "used_fallback": used_fallback,
    }


def run_weather_recommendation(
    profile: UserProfile,
    recent_messages: list[dict[str, str]] | None = None,
) -> dict:
    coords = parse_lat_lon(profile.location)
    if not coords:
        raise ValueError("No valid coordinates found. Save location as 'lat,lon' in profile.")
    lat, lon = coords
    location_used = profile.location or f"{lat},{lon}"

    raw_weather = get_current_and_forecast(lat, lon, forecast_days=5)
    profile_context = build_profile_context(
        profile,
        location_used,
        split_crops(profile.crops_grown),
        weather_summary=raw_weather,
    )

    used_fallback = False
    try:
        recommendation_text = generate_reply(
            latest_user_message=(
                "Based on this 5-day weather forecast, give actionable farming advice for the next few days. "
                "Keep it simple and short for farmers, including warnings and what to do."
            ),
            recent_messages=recent_messages or [],
            profile_context=profile_context,
        )
    except Exception:
        used_fallback = True
        recommendation_text = _fallback_weather_text()

    return {
        "recommendation_text": recommendation_text,
        "location_used": location_used,
        "raw_weather": raw_weather,
        "used_fallback": used_fallback,
    }


def run_diagnosis(
    profile: UserProfile,
    image_bytes: bytes,
    image_mime_type: str = "image/jpeg",
    recent_messages: list[dict[str, str]] | None = None,
) -> DiagnosisResponse:
    coords = parse_lat_lon(profile.location)
    lat, lon = coords if coords else (9.03, 38.74)
    vision_triage = classify_crop_image(
        image_bytes=image_bytes,
        mime_type=image_mime_type or "image/jpeg",
        supported_crops=_supported_crop_names_for_prompt(),
    )

    plant_top_crop = _triage_crop_candidate(vision_triage)
    plant_crops = [plant_top_crop] if plant_top_crop else []
    is_plant = _bool_value(vision_triage.get("is_plant"))
    decision = str(vision_triage.get("decision") or "").strip().lower()
    crop_confidence = _confidence_value(vision_triage.get("confidence"))

    if not is_plant or decision == "not_plant":
        return DiagnosisResponse(
            is_plant=False,
            top_crop=None,
            top_disease=None,
            crops=[],
            diseases=[],
            advice_text=_fallback_diagnosis_advice(False, None),
            used_fallback=False,
            provider="gemini_vision",
            confidence_status="not_plant",
            needs_retake=True,
        )

    if decision == "uncertain" or not plant_top_crop or crop_confidence < GEMINI_TRIAGE_MIN_CONFIDENCE:
        return DiagnosisResponse(
            is_plant=True,
            top_crop=plant_top_crop,
            top_disease=None,
            crops=plant_crops,
            diseases=[],
            advice_text=_uncertain_crop_advice(),
            used_fallback=False,
            provider="gemini_vision",
            confidence_status="uncertain_crop",
            needs_retake=True,
        )

    sorghum_crop = _find_sorghum_candidate(plant_crops)
    if _bool_value(vision_triage.get("is_sorghum")) and not sorghum_crop:
        sorghum_crop = plant_top_crop
    if sorghum_crop:
        return _run_sorghum_diagnosis(
            profile,
            image_bytes,
            plant_crops,
            sorghum_crop,
            recent_messages,
        )
    enset_crop = _find_enset_candidate(plant_crops)
    if (_bool_value(vision_triage.get("is_enset")) or decision == "enset_model") and not enset_crop:
        enset_crop = plant_top_crop
    if enset_crop:
        return _run_enset_diagnosis(
            profile,
            image_bytes,
            plant_crops,
            enset_crop,
            recent_messages,
        )
    supported_crop = _find_supported_crop(plant_crops)
    if (
        not supported_crop
        and _bool_value(vision_triage.get("is_kindwise_supported"))
        and plant_top_crop
        and decision == "kindwise_crop_health"
    ):
        supported_crop = plant_top_crop

    if not supported_crop:
        return DiagnosisResponse(
            is_plant=True,
            top_crop=plant_top_crop,
            top_disease=None,
            crops=plant_crops,
            diseases=[],
            advice_text=_unsupported_crop_advice(plant_top_crop),
            used_fallback=False,
            provider="gemini_vision",
            confidence_status="unsupported",
            needs_retake=False,
        )

    diagnosis = diagnose_with_kindwise(image_bytes, latitude=lat, longitude=lon)

    crops = diagnosis.get("crops", [])
    diseases = diagnosis.get("diseases", [])
    is_plant = bool(diagnosis.get("is_plant", False))
    top_crop = crops[0] if crops else None
    top_disease = diseases[0] if diseases else None
    top_disease_name = top_disease.get("name") if top_disease else None
    advice_crop = top_crop or plant_top_crop
    advice_crop_name = _crop_display_name(advice_crop)

    if not is_plant:
        fallback_top_crop = top_crop or plant_top_crop
        return DiagnosisResponse(
            is_plant=True,
            top_crop=fallback_top_crop,
            top_disease=None,
            crops=crops or plant_crops,
            diseases=[],
            advice_text=_unclear_crop_health_advice(fallback_top_crop),
            used_fallback=False,
            provider="kindwise_crop_health",
            confidence_status="uncertain",
            needs_retake=True,
        )

    profile_context = build_profile_context(
        profile,
        profile.location,
        split_crops(profile.crops_grown),
        extra={
            "diagnosis_summary": json.dumps(
                {
                    "is_plant": is_plant,
                    "top_crop": advice_crop,
                    "top_disease": top_disease,
                    "identified_crop": advice_crop_name,
                },
                ensure_ascii=False,
            ),
            "identified_crop": advice_crop_name,
        },
    )

    used_fallback = False
    try:
        advice_text = generate_reply(
            latest_user_message=(
                "Provide short farmer-friendly diagnosis advice based on this crop health result. "
                f"The first sentence must mention the identified crop by name: {advice_crop_name}. "
                "Do not start with generic phrases like 'your plant'. "
                "Include what to do now and one prevention tip."
            ),
            recent_messages=recent_messages or [],
            profile_context=profile_context,
        )
    except Exception:
        used_fallback = True
        advice_text = _fallback_crop_diagnosis_advice(advice_crop_name, top_disease_name)

    return DiagnosisResponse(
        is_plant=is_plant,
        top_crop=top_crop,
        top_disease=top_disease,
        crops=crops,
        diseases=diseases,
        advice_text=advice_text,
        used_fallback=used_fallback,
        provider="kindwise_crop_health",
        confidence_status="confident",
        needs_retake=False,
    )

