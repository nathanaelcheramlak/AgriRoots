"""Run real frontend → disposable FastAPI → LangGraph → fixture providers → evidence.

No operational database, user, provider key or live model is changed or called.
"""
import json
import os
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT.parent / "agrilo-fieldops-frontend"


def main():
    skills = "--skills" in sys.argv
    plugins = "--plugins" in sys.argv or skills
    if not (FRONTEND / "package.json").is_file():
        raise SystemExit("The repository agrilo-fieldops-frontend directory is required")
    with tempfile.TemporaryDirectory(prefix="agrilo-home-run-", ignore_cleanup_errors=True) as temporary:
        ready = Path(temporary) / "ready.json"
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            port = listener.getsockname()[1]
        env = {**os.environ, "AGRI_HOME_FIXTURE": "1", "AGRI_HOME_PORT": str(port), "AGRI_HOME_READY": str(ready),
               "FIELDOPS_BACKEND_URL": f"http://127.0.0.1:{port}", "VITE_API_MODE": "http", "VITE_API_BASE_URL": "/backend"}
        if plugins:
            env["AGRI_PLUGINS_FIXTURE"] = "1"
        if skills:
            env["AGRI_SKILLS_FIXTURE"] = "1"
        runtime = None
        with (Path(temporary) / "backend.log").open("w", encoding="utf-8") as log:
            backend = subprocess.Popen([sys.executable, "tests/home_browser_server.py"], cwd=ROOT, env=env, stdout=log, stderr=log, creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0)
            try:
                for _ in range(120):
                    if ready.exists():
                        runtime = Path(json.loads(ready.read_text(encoding="utf-8"))["runtime"])
                        break
                    if backend.poll() is not None:
                        saved = ROOT / "private-data/home-browser-startup.log"
                        saved.parent.mkdir(exist_ok=True)
                        log.flush()
                        saved.write_text((Path(temporary) / "backend.log").read_text(encoding="utf-8"), encoding="utf-8")
                        raise RuntimeError("Disposable Home backend failed to start; inspect private-data/home-browser-startup.log")
                    time.sleep(.5)
                else:
                    raise RuntimeError("Disposable backend startup timed out")
                config = "playwright.skills.config.ts" if skills else "playwright.plugins.config.ts" if plugins else "playwright.home.config.ts"
                result = subprocess.run([shutil.which("node") or "node", "node_modules/@playwright/test/cli.js", "test", "--config", config],
                                        cwd=FRONTEND, env=env, check=False)
                return result.returncode
            finally:
                if backend.poll() is None:
                    if os.name == "nt": backend.send_signal(signal.CTRL_BREAK_EVENT)
                    else: backend.terminate()
                try: backend.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    if os.name == "nt": subprocess.run(["taskkill", "/PID", str(backend.pid), "/T", "/F"], capture_output=True, check=False)
                    else: backend.kill()
                    backend.wait(timeout=5)
                # Delete only the verified temp directory created by this isolated fixture.
                if runtime and runtime.name.startswith("agrilo-home-browser-") and runtime.parent.resolve() == Path(tempfile.gettempdir()).resolve():
                    for attempt in range(10):
                        try:
                            shutil.rmtree(runtime)
                            break
                        except OSError:
                            time.sleep(.2)


if __name__ == "__main__":
    raise SystemExit(main())
