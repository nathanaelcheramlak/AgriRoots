from __future__ import annotations


APP_LANGUAGE_NAMES = {
    "en": "English",
    "am": "Amharic",
}

APP_LANGUAGE_TO_BCP47 = {
    "en": "en-US",
    "am": "am-ET",
}

BCP47_TO_APP_LANGUAGE = {
    "en": "en",
    "en-us": "en",
    "am": "am",
    "am-et": "am",
    "amh": "am",
}


def normalize_app_language(value: str | None, default: str = "en") -> str:
    normalized = (value or "").strip().lower().replace("_", "-")
    return BCP47_TO_APP_LANGUAGE.get(normalized, default)


def language_to_bcp47(value: str | None, default: str = "en-US") -> str:
    app_language = normalize_app_language(value, default="")
    if app_language:
        return APP_LANGUAGE_TO_BCP47[app_language]
    return default


def language_name(value: str | None, default: str = "English") -> str:
    app_language = normalize_app_language(value, default="")
    if app_language:
        return APP_LANGUAGE_NAMES[app_language]
    return default


def is_amharic(value: str | None) -> bool:
    return normalize_app_language(value, default="") == "am"
