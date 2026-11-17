"""Build an observed report from JUnit, saved live evidence and deployment probes; makes no network calls."""

from datetime import datetime, timezone
import hashlib
from importlib.metadata import version
import json
from pathlib import Path
import subprocess
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parent
ACCEPTANCE = {
    "REST-01": ["two_rest_tools_are_registered_and_executed_without_code_changes"],
    "REST-02": ["two_rest_tools_are_registered_and_executed_without_code_changes"],
    "REST-03": ["invalid_arguments_never_reach_network"],
    "REST-04": [
        "header_credentials_are_encrypted_and_redacted",
        "platform_jwt_and_gemini_key_cannot_be_provider_credentials",
    ],
    "REST-05": ["provider_failure_and_no_data_are_distinct"],
    "REST-06": [
        "provider_failure_and_no_data_are_distinct",
        "two_rest_tools_are_registered_and_executed_without_code_changes",
    ],
    "REST-07": ["safe_reads_retry_within_shared_request_budget", "provider_failure_and_no_data_are_distinct"],
    "REST-08": [
        "reviewed_provider_adapter_uses_common_executor_and_transport",
        "internal_http_mcp_preserves_run_scope_and_persisted_review_draft",
    ],
    "MCP-01": ["sdk_discovery_paginates_and_invokes_real_protocol"],
    "MCP-02": ["partial_discovery_does_not_infer_removals"],
    "MCP-03": ["sdk_discovery_paginates_and_invokes_real_protocol"],
    "MCP-04": ["changed_discovery_revokes_old_definition_and_unchanged_is_stable"],
    "MCP-05": ["same_upstream_names_are_collision_safe"],
    "MCP-06": [
        "unstructured_and_tool_error_are_not_structured_success",
        "mcp_unhandled_artifacts_are_blocked_without_retrieval",
    ],
    "MCP-07": ["mcp_authenticated_clients_are_isolated_across_offices"],
    "MCP-08": ["unsupported_auth_transport_and_sdk_version_fail_honestly"],
    "POLICY-01": ["cross_office_management_jobs_credentials_and_evidence_denied"],
    "POLICY-02": [
        "revocation_blocks_pinned_runs_and_cache_hits",
        "wrong_digest_and_new_configuration_do_not_inherit_approval",
    ],
    "POLICY-03": [
        "scope_and_configuration_cannot_grant_network_exceptions",
        "dns_resolver_rejects_mixed_private_answers",
        "connect_proxy_pins_literal_resolved_public_address",
    ],
    "POLICY-04": [
        "hot_operator_policy_is_authoritative_and_fixture_exception_forbidden_in_production",
        "invalid_arguments_never_reach_network",
    ],
    "POLICY-05": [
        "unknown_model_tool_is_audited_and_never_dispatched",
        "mcp_schema_cannot_be_forged_from_a_description",
    ],
    "POLICY-06": ["configuration_cannot_execute_code_or_unsupported_effects"],
    "REGISTRY-01": ["new_approved_tool_appears_only_in_new_snapshots_without_restart"],
    "REGISTRY-02": ["emergency_revocation_between_reservation_and_final_gate_blocks_http"],
    "REGISTRY-03": ["parallel_calls_consume_one_shared_atomic_budget"],
    "CACHE-01": [
        "credential_rotation_invalidates_approval_cache_and_pinned_replay",
        "redis_cache_authenticates_partition_freshness_and_key_rotation",
    ],
    "MODEL-02": ["unknown_model_tool_is_audited_and_never_dispatched", "invalid_arguments_never_reach_network"],
}


def read_json(name):
    return json.loads((ROOT / "reports" / name).read_text(encoding="utf-8-sig"))


def junit(path):
    root = ET.parse(path).getroot()
    suites = list(root) if root.tag == "testsuites" else [root]
    cases = []
    for suite in suites:
        for case in suite.findall("testcase"):
            outcome = (
                "FAILED"
                if case.find("failure") is not None or case.find("error") is not None
                else "SKIPPED"
                if case.find("skipped") is not None
                else "PASSED"
            )
            cases.append(
                {
                    "test": case.get("classname") + "::" + case.get("name"),
                    "name": case.get("name"),
                    "outcome": outcome,
                    "seconds": float(case.get("time", 0)),
                }
            )
    counts = {key: sum(case["outcome"] == key for case in cases) for key in ["PASSED", "FAILED", "SKIPPED"]}
    return {
        "artifact": path.relative_to(ROOT).as_posix(),
        "timestamp": suites[0].get("timestamp"),
        "counts": counts,
        "duration_seconds": sum(float(s.get("time", 0)) for s in suites),
        "cases": cases,
    }


def main():
    primary = junit(ROOT / "validation/agri-mcp-final.xml")
    postgres = junit(ROOT / "validation/agri-mcp-postgres-redis.xml")
    hardening = junit(ROOT / "validation/agri-mcp-schema-hardening.xml")
    observed = [*primary["cases"], *postgres["cases"], *hardening['cases']]
    acceptance = []
    for ident, names in ACCEPTANCE.items():
        evidence = [case for case in observed if any(case["name"].startswith("test_" + name) for name in names)]
        passed = all(
            any(case["name"].startswith("test_" + name) and case["outcome"] == "PASSED" for case in evidence)
            for name in names
        )
        acceptance.append(
            {
                "id": ident,
                "status": "PASSED_FIXTURE"
                if passed and not any(c["outcome"] == "FAILED" for c in evidence)
                else "INCOMPLETE_OR_FAILED",
                "tests": sorted(set(case["test"] for case in evidence)),
                "type": "LOCAL_HTTP_PROTOCOL_MODEL_FIXTURES_AND_REAL_LOCAL_DATABASES",
            }
        )
    live = read_json("connector_live_results.json")
    for check in live["checks"]:
        acceptance.append(
            {
                "id": check["id"],
                "status": check["outcome"],
                "provider": check["provider"],
                "evidence": "reports/connector_live_results.json",
                "observed_at": live["executed_at_utc"],
                "reason": check.get("reason"),
                "agricultural_payload_validation": check.get("agricultural_payload_validation"),
            }
        )
    code_files = sorted(
        [*ROOT.glob("src/**/*.py"), ROOT / "pyproject.toml", ROOT / "uv.lock", ROOT / "requirements-connectors.lock"]
    )
    hasher = hashlib.sha256()
    for path in code_files:
        hasher.update(path.relative_to(ROOT).as_posix().encode() + b"\0" + path.read_bytes() + b"\0")
    implementation = {
        "version": "0.4.0",
        "branch": subprocess.check_output(["git", "branch", "--show-current"], cwd=REPO, text=True).strip(),
        "base_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO, text=True).strip(),
        "working_tree_code_sha256": hasher.hexdigest(),
        "code_files_hashed": len(code_files),
        "dependency_versions": {
            name: version(name)
            for name in [
                "mcp",
                "google-genai",
                "langgraph",
                "langgraph-checkpoint-postgres",
                "psycopg",
                "httpx",
                "redis",
                "espeakng-loader",
            ]
        },
    }
    journal = [junit(path) for path in sorted((ROOT / "validation").glob("agri-mcp-*.xml"))]
    for entry in journal:
        entry.pop("cases")
    deployment = read_json("connector_deployment_results.json")
    commands = {
        "full_regression": r".\.venv\Scripts\python.exe -m pytest -q --tb=short --junitxml=validation/agri-mcp-final.xml",
        "postgres_redis": r".\.venv\Scripts\python.exe scripts/test_connectors_postgres.py",
        "fixture_demo": r".\.venv\Scripts\python.exe scripts/demo_connectors.py",
        "live_public": r".\.venv\Scripts\python.exe scripts/demo_connectors.py --live",
        "compose": "docker compose -p agrilo-connectors-test -f compose.yaml -f compose.test.yaml --env-file private-data/compose.env up -d --build api worker mcp",
        "runtime_checks": deployment["command"],
        "historical_import": r".\.venv\Scripts\python.exe scripts/import_provider_inventory.py ..\..\f-test\reports\results.json",
    }
    report = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "implementation": implementation,
        "commands_executed": commands,
        "latest_full_regression": primary,
        "latest_postgres_redis": postgres,
        "final_schema_hardening": hardening,
        "acceptance": acceptance,
        "live_http_attempts": len(live["attempts"]),
        "deployment": deployment,
        "fixture_demo_report": "reports/connector_fixture_demo.json",
        "historical_inventory": "reports/provider_inventory.json",
        "earlier_run_journal": journal,
        "resolved_failures": [
            "Migration expectation updated for additive revision 4.",
            "SDK fixture list handler corrected to use the installed request signature.",
            "Credential-cache test corrected: a new authorized credential test can populate its own new-scope cache.",
            "Missing pinned espeakng-loader dependency restored; real English/Amharic synthesis now passes.",
        ],
        "blocked": [
            "MODEL-01: no configured Gemini API key or verified model access; only SDK/model fixtures ran.",
            "Plantix credential issuance and other inventory entries requiring account access remain outside configured office connections.",
        ],
        "deferred": [
            "Bounded OpenAPI importer",
            "Generic REST pagination",
            "Interactive OAuth/elicitation/sampling",
            "Tenant stdio/code plugins",
            "Private image asset workflow and new Kindwise credit calls",
            "Instrumented WaPOR raster/range transport",
            "CHIRPS geometry beyond the historical synthetic Adama fixture",
            "Full map/PostGIS FieldOps workflows and frontend",
            "Automatic companion advisory approval/release or external messaging",
        ],
        "limitations": [
            "Final schema hardening rejects regex patterns, quadratic uniqueness checks and unchecked formats; its separate fixture result is included rather than folded into an earlier full-suite count.",
            "Fixtures do not prove live availability or agronomic accuracy.",
            "Old report failures are retained as historical execution evidence; only latest runs determine acceptance.",
            "The live report predates final provenance/audit hardening; final changes were verified with protocol/database fixtures. Its real responses were not fabricated or relabeled.",
            "Live public checks used a synthetic plot context and real provider evidence. NASA MCP uses LST, not the REST adapter UTC request.",
            "Actual/estimated monetary costs remain unknown/null unless supplied; request caps are not dollar limits.",
            "Generic read-only POST and remote implementation behavior require administrator/provider trust.",
            "Legacy third-party Fetch subprocess HTTP traffic is bounded by its proxy but not individually counted as common-executor attempts.",
            "SQLite development cannot establish production cross-process revocation locking.",
        ],
    }
    out = ROOT / "reports/connector_test_results.json"
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    lines = [
        "# Connector implementation test report",
        "",
        f"Generated {report['generated_at_utc']}. Branch `{implementation['branch']}`, base `{implementation['base_commit']}`, implementation 0.4.0.",
        "",
        f"Final full regression: **{primary['counts']['PASSED']} passed, {primary['counts']['FAILED']} failed, {primary['counts']['SKIPPED']} skipped**. PostgreSQL/Redis connector suite: **{postgres['counts']['PASSED']} passed, {postgres['counts']['FAILED']} failed, {postgres['counts']['SKIPPED']} skipped**. These suites overlap and must not be added together.",
        "",
        "The default-suite skip is the opt-in dedicated Redis contract; that contract ran against real local Redis in the PostgreSQL/Redis suite. Real English/Amharic speech is included in the full run. No paid diagnosis call or real Gemini request was made.",
        "",
        "New live verification: **Open-Meteo REST and independently maintained NASA POWER MCP** both returned actual evidence through the management API/shared executor. The official SDK negotiated protocol 2025-03-26 with NASA POWER MCP Server 1.1.0-beta. Eight HTTP attempts were recorded. The saved NASA response also passed numeric, date, coordinate and unit validation; its time standard is LST. Real Gemini remains credential-blocked.",
        "",
        "Deployment verification used actual PostgreSQL 16, Redis 7, separate migration owner/application roles and the running API/worker/internal-MCP containers. Both health routes passed with zero provider calls; forbidden audit mutation was denied; checkpoints persisted across saver sessions; encrypted Redis data and real local speech passed. Deployed security/graph/main source hashes match the workspace.",
        "",
        "## Acceptance matrix",
        "",
        "| ID | Observed result |",
        "| --- | --- |",
    ]
    lines.extend(f"| {row['id']} | {row['status']} |" for row in acceptance)
    lines.extend(
        [
            "",
            "REST-07 covers bounded retry, response expansion and deadline behavior; generic pagination is unavailable. MCP-06 covers structured/text/error and unsupported-artifact handling; interactive capabilities remain unsupported and are never granted.",
            "",
            "## Reproduction",
            "",
            "Run from `backend/`. The PostgreSQL helper uses only the fixed disposable `agrilo_test` database on the dedicated localhost test port; its fixtures drop application tables. Never substitute an operational database.",
            "",
            "```powershell",
            *commands.values(),
            "```",
            "",
            "## Artifacts and provenance",
            "",
            "- [Full JUnit result](../validation/agri-mcp-final.xml)",
            "- [PostgreSQL/Redis JUnit result](../validation/agri-mcp-postgres-redis.xml)",
            "- [Machine-readable acceptance, test cases and exact dependency versions](connector_test_results.json)",
            "- [Saved live requests/results and attempt trace](connector_live_results.json)",
            "- [Actual deployment probes](connector_deployment_results.json)",
            "- [Persistent fixture demo](connector_fixture_demo.json)",
            "- [Historical API inventory](provider_inventory.json)",
            "",
            f"Final working-tree code/dependency fingerprint: `{implementation['working_tree_code_sha256']}`. Test timestamps are retained in JUnit. Earlier incremental reports are journaled separately; they include failures fixed during implementation and are not represented as current failures.",
            "",
            "## Blocked and deferred",
            "",
        ]
    )
    lines.extend("- " + item for item in report["blocked"] + report["deferred"])
    lines.extend(["", "## Limits", ""])
    lines.extend("- " + item for item in report["limitations"])
    (ROOT / "reports/CONNECTOR_TEST_REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("Observed test report generated:", primary["counts"], postgres["counts"])


if __name__ == "__main__":
    main()
