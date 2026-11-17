"""Import historical evidence, not credentials or a claim of current health."""

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

HANDLERS = {
    "open_meteo": "open_meteo.forecast",
    "nasa_power": "nasa_power.history",
    "chirps": "chirps.rainfall_history",
    "isda_soil": "isda.soil_profile",
    "fao_fpma": "fpma.ethiopia_prices",
    "fao_locust": "fao.locust_observations",
}
BLOCKERS = {
    "fao_wapor": "Historical raster verification retained; instrumented/budgeted range transport is not yet implemented.",
    "kindwise": "One historical crop-photo call verified. New calls require the separate authorized asset workflow and credit-use permission.",
    "nasa_power_mcp": "Historical manual-protocol result retained. Official-SDK verification is recorded separately in connector_live_results.json; no office connection is enabled by importing it.",
    "plantix": "Access request submitted; no issued API credential is configured.",
    "fao_gaez": "Catalog metadata only; numerical suitability extraction was not established.",
    "fao_asis": "Historical catalog access succeeded, but raster access returned HTTP 403.",
    "africas_talking": "Outbound delivery is not exposed to the companion. Sandbox diagnostics remain separate.",
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("results", type=Path)
    parser.add_argument("--output", type=Path, default=Path("reports/provider_inventory.json"))
    args = parser.parse_args()
    raw = args.results.read_bytes()
    document = json.loads(raw)
    providers = []
    for row in document["results"]:
        ident = row["provider_id"]
        status = "VERIFIED_LIVE" if row["status"] == "WORKING" else row["status"]
        scope = {
            "point": document.get("scope", {}).get("location"),
            "historical_start": document.get("scope", {}).get("historical_start"),
            "historical_end": document.get("scope", {}).get("historical_end"),
            "ethiopia_data_available": row.get("ethiopia_data_available"),
        }
        if ident == "kindwise":
            scope = {
                "image_sha256": row["sample_data"].get("image_sha256"),
                "ethiopia_data_available": None,
                "input_provenance": row.get("input_provenance"),
                "note": "Provider-published photo; no Ethiopian field accuracy established.",
            }
        providers.append(
            {
                "id": ident,
                "name": row["provider"],
                "category": row["category"],
                "historical_verification": {
                    "status": status,
                    "verified_at": row.get("tested_at_utc"),
                    "http_status": row.get("http_status"),
                    "scope": scope,
                    "limitations": row.get("limitations", []),
                    "result_digest": hashlib.sha256(json.dumps(row, sort_keys=True).encode()).hexdigest(),
                },
                "documentation": row.get("documentation"),
                "authentication_required": row.get("authentication_required"),
                "access_notes": row.get("free_tier"),
                "handler_id": HANDLERS.get(ident),
                "disposition": "REUSED_CONTROLLED_ADAPTER" if ident in HANDLERS else "INVENTORIED_DISABLED",
                "blocker": BLOCKERS.get(ident) or row.get("error"),
                "runtime_health": "NOT_TESTED_BY_INVENTORY_IMPORT",
                "historical_source_path": str(args.results.resolve()),
            }
        )
    output = {
        "imported_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_report": str(args.results.resolve()),
        "source_report_sha256": hashlib.sha256(raw).hexdigest(),
        "source_generated_at": document.get("generated_at_utc"),
        "historical_counts": document.get("counts"),
        "providers": providers,
        "note": "This file imports previously recorded evidence. It neither executes nor enables providers and contains no credentials.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Imported {len(providers)} historical provider checks; no network calls and no credential import.")


if __name__ == "__main__":
    main()
