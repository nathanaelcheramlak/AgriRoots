#!/usr/bin/env python3
"""Run deterministic integration evaluations; save honest outcomes separately from real inference."""
import json
import argparse
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
CASES = {
    "complete_consistent_records": "test_real_mcp_graph_stops_at_review_and_is_idempotent",
    "missing_plot_history": "test_missing_history_blocks_draft",
    "stale_weather_and_unsupported_advice": "test_candidate_validation_rejects_stale_invented_and_inapplicable_support",
    "weather_unavailable": "test_graph_weather_retries_are_bounded",
    "conflicting_pest_reports": "test_conflicting_pest_reports_require_field_visit",
    "cross_office_access": "test_scope_and_privilege_escalation",
    "unapproved_release_and_reviewed_audio": "test_review_approval_release_and_exact_audio",
    "edit_after_approval": "test_new_version_invalidates_approval_and_preserves_history",
    "concurrent_release": "test_concurrent_release_publishes_once",
    "malicious_document_and_model_output": "test_untrusted_output_cannot_add_approval_or_recipient_fields",
    "restart_after_save": "test_interrupted_save_resumes_without_another_draft",
    "fresh_and_legacy_migrations": "test_migrations_fresh_and_legacy_copy",
    "reject_cancel_and_correct": "test_reject_cancel_replace_and_record_audits",
    "unverified_generated_claims": "test_generated_claims_are_retained_privately_and_excluded_from_advisory",
    "five_plot_citations_and_recovery": "test_five_plots_have_independent_citations_and_resumable_drafts",
    "planting_rules_and_coverage": "test_planting_rules_are_required_and_weather_window_is_complete",
    "offline_speech_limits": "test_local_speech_rejects_unreviewed_languages_and_oversized_text",
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default="backend/validation/final-integration.json")
    output = ROOT / parser.parse_args().output
    with tempfile.TemporaryDirectory() as directory:
        xml = Path(directory) / "results.xml"
        result = subprocess.run([sys.executable, "-m", "pytest", "-q", "-o", "faulthandler_timeout=45", f"--junitxml={xml}"],
            cwd=ROOT / "backend", env={**os.environ, "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1"})
        tests = list(ET.parse(xml).iter("testcase"))
        rows = []
        for task, name in CASES.items():
            matches = [t for t in tests if t.get("name") == name or t.get("name", "").startswith(name + "[")]
            passed = bool(matches) and all(not any(t.find(k) is not None for k in ("failure", "error", "skipped")) for t in matches)
            rows.append({"task": task, "test": name, "passed": passed,
                         "seconds": round(sum(float(t.get("time", 0)) for t in matches), 3)})
        report = {"executed_at": datetime.now(timezone.utc).isoformat(),
            "kind": "deterministic integration; explicit test model, synthetic forecasts and cached public document; real custom MCP stdio",
            "voice": "exact reviewed-text authorization test plus real local English/Amharic PCM synthesis; browser playback recorded separately",
            "database": "PostgreSQL" if os.environ.get("AGRIROOTS_TEST_DATABASE_URL", "").startswith("postgresql") else "SQLite",
            "tests": len(tests), "failed": sum(t.find("failure") is not None or t.find("error") is not None for t in tests),
            "skipped": sum(t.find("skipped") is not None for t in tests), "exit_code": result.returncode, "tasks": rows}
        output.write_text(json.dumps(report, indent=2) + "\n")
        print(f"Saved {output}")
        raise SystemExit(result.returncode or (0 if all(r["passed"] for r in rows) else 1))


if __name__ == "__main__": main()
