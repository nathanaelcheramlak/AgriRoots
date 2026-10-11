import re


def normalize_phone(phone_number: str) -> str:
    digits = re.sub(r"\D", "", phone_number or "")

    if digits.startswith("0") and len(digits) == 10:
        digits = f"251{digits[1:]}"

    if digits.startswith("251") and len(digits) == 12:
        return digits

    raise ValueError(
        "Invalid phone number format. Use Ethiopian format like 0911xxxxxx or 251911xxxxxx"
    )

