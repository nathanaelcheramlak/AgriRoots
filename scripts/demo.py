#!/usr/bin/env python3
"""Start the isolated synthetic demo: python3 scripts/demo.py. Ctrl-C stops all services."""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import platform
import secrets
import shutil
import signal
import socket
import subprocess
import sys
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
RUNTIME = BACKEND / "runtime"


def run(args, cwd=BACKEND, env=None):
    subprocess.run([str(x) for x in args], cwd=cwd, env=env, check=True)


def main():
    started = time.monotonic()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Verify readiness, then shut down")
    parser.add_argument("--compute-cost-per-hour", type=float, default=0, help="Operator's assumed hourly host rate in USD; zero means unpriced")
    args = parser.parse_args()
    if not 0 <= args.compute_cost_per_hour < float("inf"):
        parser.error("Compute cost must be finite and nonnegative")
    if platform.system() != "Linux" or platform.machine() != "x86_64" or sys.version_info < (3, 11):
        raise SystemExit("The pinned demo supports Linux x86_64 and Python 3.11–3.13 (tested: 3.13).")
    if not shutil.which("npm") or (sys.version_info >= (3, 14) and not shutil.which("uv")):
        raise SystemExit("Install Node.js 22.12+ with npm, and either uv or Python 3.11–3.13.")
    RUNTIME.mkdir(exist_ok=True)
    lock = (RUNTIME / "demo.lock").open("w")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        raise SystemExit("A demo launcher is already running.")
    for port in (8000, 8081, 4173):
        with socket.socket() as probe:
            probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try: probe.bind(("127.0.0.1", port))
            except OSError: raise SystemExit(f"Port {port} is occupied; stop the existing service and retry.")
    venv = RUNTIME / "demo-venv"
    python = venv / "bin/python"
    requirements = BACKEND / "requirements-demo.lock"
    digest = hashlib.sha256(requirements.read_bytes()).hexdigest()
    stamp = venv / "requirements.sha256"
    if not stamp.exists() or stamp.read_text() != digest:
        if shutil.which("uv"):
            if not python.exists(): run(["uv", "venv", "--python", "3.13", venv])
            run(["uv", "pip", "sync", "--python", python, requirements])
        else:
            if not python.exists(): run([sys.executable, "-m", "venv", venv])
            run([python, "-m", "pip", "install", "-r", requirements])
        stamp.write_text(digest)
    # Do not inherit operator/cloud credentials into this synthetic workflow.
    env = {k: v for k, v in os.environ.items() if k in ("PATH", "HOME", "LANG", "LC_ALL", "TMPDIR", "LD_LIBRARY_PATH")}
    secret = RUNTIME / "demo-jwt-key"
    if not secret.exists():
        fd = os.open(secret, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w") as stream: stream.write(secrets.token_urlsafe(48))
    secret.chmod(0o600)
    database = RUNTIME / "demo.db"
    env.update(DATABASE_URL=f"sqlite:///{database}", JWT_SECRET_KEY=secret.read_text(),
               DEBUG="false", PYTHONUNBUFFERED="1", ADVISORY_MODEL_KEY_FILE=str(RUNTIME / "model-api-key"),
               ADVISORY_COMPUTE_COST_PER_HOUR=str(args.compute_cost_per_hour), ADVISORY_AUDIO_PROVIDER="local")
    # A dedicated cwd has no .env. All server subprocesses still need src imports.
    env["PYTHONPATH"] = str(BACKEND)
    seeded = not database.exists()
    if seeded: run([python, "-m", "src.cli.seed_phase2"], cwd=RUNTIME, env=env)
    else: run([python, "-c", "from src.db.schema_migrations import migrate; from src.db.session import engine; migrate(engine)"], cwd=RUNTIME, env=env)
    run([python, BACKEND / "scripts/local_model.py", "--download-only"], cwd=RUNTIME, env=env)
    frontend = ROOT / "frontend"
    npm_env = {**env, "VITE_API_BASE_URL": "http://127.0.0.1:8000"}
    npm_env["npm_config_cache"] = os.environ.get("npm_config_cache", str(RUNTIME / "npm-cache"))
    run(["npm", "ci", "--no-audit", "--no-fund"], cwd=frontend, env=npm_env)
    run(["npm", "run", "build"], cwd=frontend, env=npm_env)
    processes = []
    logs = []
    def start(name, command, cwd=RUNTIME):
        log = (RUNTIME / f"{name}.log").open("w")
        logs.append(log)
        processes.append(subprocess.Popen([str(x) for x in command], cwd=cwd, env=env,
                                         stdout=log, stderr=subprocess.STDOUT, start_new_session=True))
    def alive():
        if any(p.poll() is not None for p in processes):
            raise RuntimeError("A service exited; inspect backend/runtime/{api,worker,model,frontend}.log")
    def wait_url(url, seconds=120):
        until = time.monotonic() + seconds
        while time.monotonic() < until:
            alive()
            try:
                with urllib.request.urlopen(url, timeout=2) as response:
                    if response.status == 200: return
            except (OSError, ValueError): pass
            time.sleep(.5)
        raise RuntimeError(f"Readiness timeout: {url}")
    def stop(_signal, _frame): raise KeyboardInterrupt
    signal.signal(signal.SIGTERM, stop)
    try:
        start("model", [python, BACKEND / "scripts/local_model.py"])
        wait_url("http://127.0.0.1:8081/health")
        start("api", [python, "-m", "uvicorn", "src.main:app", "--host", "127.0.0.1", "--port", "8000"])
        wait_url("http://127.0.0.1:8000/health")
        # Verify DB scope, model authentication and actual MCP stdio handshakes.
        run([python, "-m", "src.cli.check_demo"], cwd=RUNTIME, env=env)
        start("worker", [python, "-m", "src.cli.advisory_worker"])
        start("frontend", [frontend / "node_modules/.bin/vite", "preview", "--host", "127.0.0.1", "--port", "4173", "--strictPort"], cwd=frontend)
        wait_url("http://127.0.0.1:4173/auth-options")
        time.sleep(2); alive()
        (BACKEND / "validation/final-startup.json").write_text(json.dumps({
            "checked_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "status": "ready",
            "platform": platform.platform(), "python": subprocess.check_output([python, "--version"], text=True).strip(),
            "database": "dedicated synthetic SQLite demo.db", "new_seed": seeded,
            "elapsed_seconds": round(time.monotonic() - started, 2),
            "checks": ["migrations", "synthetic office and current records", "authenticated local model identity",
                       "custom MCP stdio", "borrowed MCP stdio", "live weather", "public guidance cache",
                       "frontend HTTP", "worker alive"],
            "scope": "native host; cached model/dependencies; not a clean VM or offline guarantee"
        }, indent=2) + "\n")
        print("READY: http://127.0.0.1:4173/workspace\nSynthetic officer: +251900000002; farmer: +251900000003\nPassword: SyntheticDemo123!\nLocal demo only. Ctrl-C stops all services; data and model cache persist.", flush=True)
        if not args.check:
            while True: alive(); time.sleep(1)
    finally:
        for p in reversed(processes):
            if p.poll() is None: os.killpg(p.pid, signal.SIGTERM)
        for p in processes:
            try: p.wait(timeout=10)
            except subprocess.TimeoutExpired: os.killpg(p.pid, signal.SIGKILL); p.wait()
        for log in logs: log.close()


if __name__ == "__main__":
    try: main()
    except KeyboardInterrupt: print("Demo stopped.")
