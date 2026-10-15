#!/usr/bin/env python3
"""Check Git-visible submission artifacts without printing credential values."""
import json
from pathlib import Path
import re
import subprocess
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
PATTERNS = [re.compile(p.encode()) for p in (
    r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----",
    r"AIza[0-9A-Za-z_-]{35}", r"gh[pousr]_[0-9A-Za-z]{30,}",
    r"AKIA[0-9A-Z]{16}", r"sk-(?:proj-)?[A-Za-z0-9_-]{40,}",
)]


def main():
    names = subprocess.check_output(["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"], cwd=ROOT).decode().split("\0")
    findings = []; scanned = 0
    for name in sorted(set(filter(None, names))):
        file = ROOT / name
        if not file.is_file(): continue
        if any(part in ("runtime", "private-data", "node_modules", ".aws", ".codex", ".agents") for part in file.parts):
            findings.append({"file": name, "reason": "private/runtime directory is Git-visible"}); continue
        if file.name == ".env" or re.search(r"\.(?:db|sqlite|sqlite3)(?:-|$)", file.name):
            findings.append({"file": name, "reason": "environment or database is Git-visible"}); continue
        if file.stat().st_size > 3_000_000: continue
        data = file.read_bytes()
        if b"\0" in data: continue
        scanned += 1
        if any(p.search(data) for p in PATTERNS):
            findings.append({"file": name, "reason": "credential pattern; value suppressed"})
    report = {"checked_at": datetime.now(timezone.utc).isoformat(), "text_files_scanned": scanned,
        "passed": not findings, "findings": findings,
        "scope": "heuristic scan of Git-visible text and forbidden runtime paths; does not prove absence of every secret or personal record",
        "rights": "owner confirmed redistribution rights; original code Apache-2.0; third-party terms retained"}
    (ROOT / "backend/validation/phase3-artifacts.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"passed": report["passed"], "text_files_scanned": scanned, "findings": findings[:10],
                      "total_findings": len(findings), "report": "backend/validation/phase3-artifacts.json"}, indent=2))
    raise SystemExit(1 if findings else 0)


if __name__ == "__main__": main()
