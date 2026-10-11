import httpx


def _safe_avg(values: list[float | None]) -> float | None:
    cleaned = [v for v in values if v is not None]
    if not cleaned:
        return None
    return round(sum(cleaned) / len(cleaned), 2)


def _safe_sum(values: list[float | None]) -> float | None:
    cleaned = [v for v in values if v is not None]
    if not cleaned:
        return None
    return round(sum(cleaned), 2)


def get_weather_summary(lat: float, lon: float, past_days: int = 7) -> dict:
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": lat,
        "longitude": lon,
        "daily": [
            "temperature_2m_max",
            "temperature_2m_min",
            "rain_sum",
            "wind_speed_10m_max",
        ],
        "past_days": past_days,
        "forecast_days": 0,
        "timezone": "auto",
    }
    with httpx.Client(timeout=20.0) as client:
        response = client.get(url, params=params)
    if response.status_code >= 400:
        raise RuntimeError(f"Open-Meteo error ({response.status_code}): {response.text}")

    daily = response.json().get("daily", {})
    tmax = daily.get("temperature_2m_max", [])
    tmin = daily.get("temperature_2m_min", [])
    rain = daily.get("rain_sum", [])
    wind = daily.get("wind_speed_10m_max", [])
    dates = daily.get("time", [])

    return {
        "period_start": dates[0] if dates else None,
        "period_end": dates[-1] if dates else None,
        "avg_temperature_max": _safe_avg(tmax),
        "avg_temperature_min": _safe_avg(tmin),
        "total_rainfall_mm": _safe_sum(rain),
        "avg_wind_speed_kph": _safe_avg(wind),
    }


def get_current_and_forecast(lat: float, lon: float, forecast_days: int = 3) -> dict:
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": lat,
        "longitude": lon,
        "current": [
            "temperature_2m",
            "relative_humidity_2m",
            "wind_speed_10m",
            "weather_code",
        ],
        "daily": [
            "weather_code",
            "temperature_2m_max",
            "temperature_2m_min",
            "rain_sum",
            "wind_speed_10m_max",
        ],
        "forecast_days": forecast_days,
        "timezone": "auto",
    }
    with httpx.Client(timeout=20.0) as client:
        response = client.get(url, params=params)
    if response.status_code >= 400:
        raise RuntimeError(f"Open-Meteo error ({response.status_code}): {response.text}")

    data = response.json()
    current = data.get("current", {})
    daily = data.get("daily", {})

    days = []
    dates = daily.get("time", [])
    codes = daily.get("weather_code", [])
    tmax = daily.get("temperature_2m_max", [])
    tmin = daily.get("temperature_2m_min", [])
    rain = daily.get("rain_sum", [])
    wind = daily.get("wind_speed_10m_max", [])
    for i in range(min(len(dates), forecast_days)):
        days.append(
            {
                "date": dates[i],
                "weather_code": codes[i] if i < len(codes) else None,
                "temp_max_c": tmax[i] if i < len(tmax) else None,
                "temp_min_c": tmin[i] if i < len(tmin) else None,
                "rain_mm": rain[i] if i < len(rain) else None,
                "wind_speed_kph": wind[i] if i < len(wind) else None,
            }
        )

    return {
        "current": {
            "temperature_c": current.get("temperature_2m"),
            "humidity_percent": current.get("relative_humidity_2m"),
            "wind_speed_kph": current.get("wind_speed_10m"),
            "weather_code": current.get("weather_code"),
        },
        "forecast_days": days,
    }
