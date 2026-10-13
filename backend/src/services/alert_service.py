from src.db.models.user import UserProfile
from src.integrations.weather.open_meteo import get_current_and_forecast
from src.services.advisory_service import parse_lat_lon, split_crops
from src.services.language import normalize_app_language


def _crop_phrase(profile: UserProfile, language: str) -> str:
    crops = split_crops(profile.crops_grown)
    if not crops:
        if language == "am":
            return "ሰብሎችዎ"
        return "your crops"
    if len(crops) == 1:
        return crops[0]
    return ", ".join(crops[:2])


def _risk_date(day: dict, language: str) -> str:
    if day.get("date"):
        return str(day["date"])
    if language == "am":
        return "በሚቀጥሉት ቀናት አንዱ"
    return "one of the next days"


def _add_alert(
    alerts: list[dict],
    *,
    alert_type: str,
    severity: str,
    title: str,
    message: str,
    action_text: str,
) -> None:
    alerts.append(
        {
            "alert_type": alert_type,
            "severity": severity,
            "title": title,
            "message": message,
            "action_text": action_text,
        }
    )


def build_weather_alerts(
    profile: UserProfile,
    language_code: str | None = None,
) -> tuple[str, dict, list[dict]]:
    language = normalize_app_language(language_code or profile.preferred_language, default="en")
    coords = parse_lat_lon(profile.location)
    if not coords:
        if language == "am":
            raise ValueError("ትክክለኛ የቦታ መረጃ አልተገኘም። ቦታዎን በ 'lat,lon' ቅርጸት ያስቀምጡ።")
        raise ValueError("No valid coordinates found. Save location as 'lat,lon' in profile.")

    lat, lon = coords
    location_used = profile.location or f"{lat},{lon}"
    raw_weather = get_current_and_forecast(lat, lon, forecast_days=5)
    crop_text = _crop_phrase(profile, language)
    forecast_days = raw_weather.get("forecast_days", [])
    alerts: list[dict] = []

    total_rain = 0.0
    dry_days = 0
    hottest_day: dict | None = None
    windiest_day: dict | None = None
    coldest_day: dict | None = None

    for day in forecast_days:
        rain = float(day.get("rain_mm") or 0)
        wind = float(day.get("wind_speed_kph") or 0)
        temp_max = day.get("temp_max_c")
        temp_min = day.get("temp_min_c")

        total_rain += rain
        if rain <= 0.5:
            dry_days += 1

        if hottest_day is None or float(temp_max or -999) > float(hottest_day.get("temp_max_c") or -999):
            hottest_day = day
        if windiest_day is None or wind > float(windiest_day.get("wind_speed_kph") or 0):
            windiest_day = day
        if coldest_day is None or float(temp_min or 999) < float(coldest_day.get("temp_min_c") or 999):
            coldest_day = day

        if rain >= 20:
            if language == "am":
                _add_alert(
                    alerts,
                    alert_type="heavy_rain",
                    severity="high",
                    title=f"በ{_risk_date(day, language)} ከባድ ዝናብ ይጠበቃል",
                    message=f"ከባድ ዝናብ በ{crop_text} እና በእርሻ ስራዎ ላይ ችግር ሊፈጥር ይችላል።",
                    action_text=(
                        "የውሃ መውጫ መንገዶችን ያጽዱ፣ ከዝናብ በፊት ማዳበሪያ አይጨምሩ፣ "
                        "እና አየሩ እስኪረጋጋ ድረስ መርጨትን ያዘግዩ።"
                    ),
                )
            else:
                _add_alert(
                    alerts,
                    alert_type="heavy_rain",
                    severity="high",
                    title=f"Heavy rain expected on {_risk_date(day, language)}",
                    message=f"Heavy rain may affect {crop_text} and field work.",
                    action_text=(
                        "Clear drainage paths, avoid fertilizer application before the rain, "
                        "and delay spraying chemicals until the weather is calmer."
                    ),
                )
        elif rain >= 10:
            if language == "am":
                _add_alert(
                    alerts,
                    alert_type="moderate_rain",
                    severity="medium",
                    title=f"በ{_risk_date(day, language)} ዝናብ ይጠበቃል",
                    message=f"ዝናብ ሊኖር ስለሚችል የ{crop_text} የእርሻ ስራን በጥንቃቄ ያቅዱ።",
                    action_text=(
                        "ዝናቡ ቀላል ከሆነ ብቻ ማዳበሪያ ይጨምሩ፣ የተሰበሰቡ ሰብሎችን ይጠብቁ፣ "
                        "እና በዝናብ ጊዜ መርጨትን ያስወግዱ።"
                    ),
                )
            else:
                _add_alert(
                    alerts,
                    alert_type="moderate_rain",
                    severity="medium",
                    title=f"Rain expected on {_risk_date(day, language)}",
                    message=f"Rain is likely, so plan farm work for {crop_text} carefully.",
                    action_text=(
                        "Apply fertilizer only if the rain is light, protect harvested crops, "
                        "and avoid spraying during rainfall."
                    ),
                )

    if total_rain >= 45:
        if language == "am":
            _add_alert(
                alerts,
                alert_type="wet_week",
                severity="high",
                title="በሚቀጥሉት 5 ቀናት ብዙ ዝናብ ይጠበቃል",
                message="በቀጣዮቹ ቀናት ብዙ ዝናብ ሊኖር ይችላል።",
                action_text=(
                    "ውሃ እንዳይቆም ይከታተሉ፣ የውሃ መውጫን ያሻሽሉ፣ "
                    "እና ከዝናቡ በኋላ በሰብሎች ላይ የፈንገስ በሽታ ምልክቶችን ይፈትሹ።"
                ),
            )
        else:
            _add_alert(
                alerts,
                alert_type="wet_week",
                severity="high",
                title="Very wet 5-day forecast",
                message="The next few days may bring a lot of rain.",
                action_text=(
                    "Watch for waterlogging, improve drainage, and check crops for fungal disease signs "
                    "after the rainy days."
                ),
            )

    if windiest_day and float(windiest_day.get("wind_speed_kph") or 0) >= 35:
        if language == "am":
            _add_alert(
                alerts,
                alert_type="strong_wind",
                severity="medium",
                title=f"በ{_risk_date(windiest_day, language)} ጠንካራ ነፋስ ሊኖር ይችላል",
                message="ጠንካራ ነፋስ ደካማ ተክሎችን ሊጎዳ እና የመርጨት ጥራትን ሊቀንስ ይችላል።",
                action_text="ወጣት ተክሎችን ከተቻለ ይደግፉ፣ በጠንካራ ነፋስ ጊዜ መድሃኒት ወይም ማዳበሪያ መርጨትን ያስወግዱ።",
            )
        else:
            _add_alert(
                alerts,
                alert_type="strong_wind",
                severity="medium",
                title=f"Strong wind risk on {_risk_date(windiest_day, language)}",
                message="Strong wind can damage weak plants and reduce spraying quality.",
                action_text="Support young plants where possible and avoid pesticide or fertilizer spraying during strong wind.",
            )

    if hottest_day and float(hottest_day.get("temp_max_c") or 0) >= 32:
        severity = "high" if float(hottest_day.get("temp_max_c") or 0) >= 35 else "medium"
        if language == "am":
            _add_alert(
                alerts,
                alert_type="high_temperature",
                severity=severity,
                title=f"በ{_risk_date(hottest_day, language)} ሞቃት አየር ይጠበቃል",
                message=f"ከፍተኛ ሙቀት በ{crop_text} ላይ በተለይም በወጣት ተክሎች ላይ ጭንቀት ሊፈጥር ይችላል።",
                action_text="በጠዋት ወይም በማታ ውሃ ያጠጡ፣ ካለ ሙልች ይጠቀሙ፣ እና በቀትር ሰዓት ተከላን ያስወግዱ።",
            )
        else:
            _add_alert(
                alerts,
                alert_type="high_temperature",
                severity=severity,
                title=f"Hot weather expected on {_risk_date(hottest_day, language)}",
                message=f"High temperature may stress {crop_text}, especially young plants.",
                action_text="Water early morning or evening, use mulch if available, and avoid transplanting at midday.",
            )

    if coldest_day and float(coldest_day.get("temp_min_c") or 99) <= 5:
        if language == "am":
            _add_alert(
                alerts,
                alert_type="low_temperature",
                severity="medium",
                title=f"በ{_risk_date(coldest_day, language)} ቀዝቃዛ ሌሊት ሊኖር ይችላል",
                message="ዝቅተኛ ሙቀት የሰብል እድገትን ሊያዘግይ ወይም ችግኞችን ሊጨንቅ ይችላል።",
                action_text="ችግኞችን ከተቻለ ይጠብቁ፣ እና በማታ መጨረሻ ውሃ ማጠጣትን ያስወግዱ።",
            )
        else:
            _add_alert(
                alerts,
                alert_type="low_temperature",
                severity="medium",
                title=f"Cold night risk on {_risk_date(coldest_day, language)}",
                message="Low temperature may slow crop growth or stress seedlings.",
                action_text="Protect seedlings where possible and avoid watering late in the evening.",
            )

    if dry_days >= 4 and total_rain <= 2:
        if language == "am":
            _add_alert(
                alerts,
                alert_type="dry_spell",
                severity="medium",
                title="ደረቅ ቀናት ይጠበቃሉ",
                message=f"በሚቀጥሉት 5 ቀናት ለ{crop_text} በጣም ትንሽ ዝናብ ይጠበቃል።",
                action_text="ከተቻለ ውሃ ማጠጣትን ያቅዱ፣ አፈሩን በሙልች ይሸፍኑ፣ እና በጠንካራ ሙቀት ላይ አላስፈላጊ ማረምን ያስወግዱ።",
            )
        else:
            _add_alert(
                alerts,
                alert_type="dry_spell",
                severity="medium",
                title="Dry days ahead",
                message=f"Very little rain is expected for {crop_text} in the next 5 days.",
                action_text="Plan irrigation if available, keep soil covered with mulch, and avoid unnecessary weeding under strong heat.",
            )

    if not alerts:
        if language == "am":
            _add_alert(
                alerts,
                alert_type="weather_clear",
                severity="low",
                title="ትልቅ የአየር ሁኔታ አደጋ አልተገኘም",
                message="በሚቀጥሉት 5 ቀናት ለእርሻዎ ትልቅ የአየር ሁኔታ አደጋ አይታይም።",
                action_text="መደበኛ የእርሻ ስራዎን ይቀጥሉ፣ ግን ማዳበሪያ ከመጨመር ወይም ከመርጨት በፊት እንደገና አስጠንቅቂያዎችን ይፈትሹ።",
            )
        else:
            _add_alert(
                alerts,
                alert_type="weather_clear",
                severity="low",
                title="No major weather risk found",
                message="The next 5 days do not show a major weather danger for your farm.",
                action_text="Continue normal farm work, but check alerts again before fertilizer application or spraying.",
            )

    severity_order = {"high": 0, "medium": 1, "low": 2}
    alerts.sort(key=lambda item: severity_order.get(item["severity"], 3))
    return location_used, raw_weather, alerts[:5]
