"""Prebuilt agriculture skills and reviewed templates; no credentials and no automatic execution."""

from src.providers.factory import HANDLERS, template


def agriculture_pack():
    skills = [
        (
            "weather_screening",
            "Explain the dated forecast and its limitations; never infer a full growing season.",
            ["weather.forecast"],
            ["soil.profile", "rainfall.history"],
        ),
        (
            "soil_profile",
            "Explain mapped soil estimates, depth, units and uncertainty. They are not laboratory measurements.",
            ["soil.profile"],
            ["weather.forecast"],
        ),
        (
            "rainfall_history",
            "Explain historical rainfall and climate; do not label it a current forecast.",
            ["climate.history"],
            ["rainfall.history"],
        ),
        (
            "market_context",
            "Explain historical Ethiopian market prices with currency, unit and observation date. They are not buyer offers.",
            ["market.prices"],
            [],
        ),
        (
            "locust_context",
            "Summarize dated reported observations. Missing reports do not establish low pest risk.",
            ["pests.regional_reports"],
            [],
        ),
        (
            "crop_health",
            "Require an authorized crop image and an enabled diagnosis provider. Describe suspected diagnoses and limitations only.",
            ["crop.diagnosis"],
            [],
        ),
    ]
    return {
        "name": "agriculture_core",
        "version": 2,
        "description": "Reviewed agricultural templates. Installation creates disabled drafts; credential and capability blockers remain visible.",
        "connections": [
            {
                "template_id": key.replace(".", "_"),
                "configuration": template(key)["connection"],
                "tools": template(key)["operations"],
            }
            for key in HANDLERS
        ],
        "skills": [
            {
                "name": name,
                "description": name.replace("_", " "),
                "instructions": instructions,
                "required_capabilities": required,
                "optional_capabilities": optional,
            }
            for name, instructions, required, optional in skills
        ],
    }
