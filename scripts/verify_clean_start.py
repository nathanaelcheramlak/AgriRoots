#!/usr/bin/env python3
"""Verify startup from isolated public source with no installed app or database."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reuse-model-downloads", action="store_true", help="Reuse only hash-verified model/runtime archives; environment/database remain fresh")
    args = parser.parse_args()
    started = time.monotonic()
    files = subprocess.check_output(["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"], cwd=ROOT).decode().split("\0")
    with tempfile.TemporaryDirectory(prefix="agriroots-clean-") as directory:
        checkout = Path(directory) / "source"; checkout.mkdir()
        digest = hashlib.sha256()
        for name in sorted(set(filter(None, files))):
            source = ROOT / name
            if not source.is_file(): continue
            if any(p in ("runtime", "node_modules", "private-data", ".git") for p in Path(name).parts) or source.name == ".env":
                raise RuntimeError("Refusing Git-visible private/runtime material: " + name)
            destination = checkout / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
            digest.update(name.encode()); digest.update(hashlib.sha256(source.read_bytes()).digest())
        if args.reuse_model_downloads:
            manifest = json.loads((ROOT / "backend/local_model.lock.json").read_text())
            runtime = checkout / "backend/runtime"; runtime.mkdir()
            for entry in (manifest["model"], manifest["runtime"]):
                source = ROOT / "backend/runtime" / entry["file"]
                if hashlib.sha256(source.read_bytes()).hexdigest() != entry["sha256"]:
                    raise RuntimeError("Model cache checksum mismatch")
                try: os.link(source, runtime / entry["file"])
                except OSError: shutil.copy2(source, runtime / entry["file"])
        env = {**os.environ, "npm_config_cache": str(Path(directory) / "npm-cache")}
        # Python wheel cache is permitted; no venv/site-packages are copied.
        log_path = Path(directory) / "startup.log"
        with log_path.open("w") as log:
            result = subprocess.run([sys.executable, "scripts/demo.py", "--check"], cwd=checkout, env=env,
                                    stdout=log, stderr=subprocess.STDOUT, timeout=1800)
        ready = checkout / "backend/validation/final-startup.json"
        report = {"executed_at": datetime.now(timezone.utc).isoformat(), "passed": result.returncode == 0,
            "elapsed_seconds": round(time.monotonic() - started, 2), "source_tree_sha256": digest.hexdigest(),
            "fresh": ["source tree", "Python environment", "npm dependencies/cache", "database", "JWT/model keys", "model extraction"],
            "cached": ["host prerequisites", "Python package download cache"] + (["checksum-verified model/runtime downloads"] if args.reuse_model_downloads else []),
            "scope": "isolated source checkout on current Linux host; not a separate VM", "exit_code": result.returncode,
            "readiness": json.loads(ready.read_text()) if ready.exists() and result.returncode == 0 else None}
        if result.returncode: report["failure_log_tail"] = log_path.read_text()[-5000:]
        (ROOT / "backend/validation/final-clean-start.json").write_text(json.dumps(report, indent=2) + "\n")
        print(json.dumps(report, indent=2))
        raise SystemExit(result.returncode)


if __name__ == "__main__": main()
