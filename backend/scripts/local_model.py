"""Download, verify and serve the tested local CPU model. No cloud inference."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import secrets
import tarfile
import urllib.request

ROOT = Path(__file__).resolve().parents[1]


def download(url, path, digest):
    if not path.exists():
        print(f"Downloading {path.name}...", flush=True)
        partial = path.with_suffix(path.suffix + ".part")
        with urllib.request.urlopen(url, timeout=60) as response, partial.open("wb") as output:
            while chunk := response.read(1024 * 1024): output.write(chunk)
        partial.rename(path)
    with path.open("rb") as stream:
        actual = hashlib.file_digest(stream, "sha256").hexdigest()
    if actual != digest:
        raise SystemExit(f"Checksum mismatch for {path.name}; remove the incomplete file and retry")


def main(download_only=False):
    if platform.system() != "Linux" or platform.machine() != "x86_64":
        raise SystemExit("This tested binary is for Linux x86_64. Build the pinned llama.cpp revision for other hosts.")
    manifest = json.loads((ROOT / "local_model.lock.json").read_text())
    runtime = ROOT / "runtime"; runtime.mkdir(exist_ok=True)
    engine, model = manifest["runtime"], manifest["model"]
    download(engine["url"], runtime / engine["file"], engine["sha256"])
    download(f"https://huggingface.co/{model['repository']}/resolve/{model['revision']}/{model['file']}", runtime / model["file"], model["sha256"])
    executable = runtime / "llama" / ("llama-" + engine["tag"]) / "llama-server"
    if not executable.exists():
        (runtime / "llama").mkdir(exist_ok=True)
        with tarfile.open(runtime / engine["file"]) as bundle:
            bundle.extractall(runtime / "llama", filter="data")
    key_file = runtime / "model-api-key"
    if not key_file.exists():
        descriptor = os.open(key_file, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "w") as stream: stream.write(secrets.token_urlsafe(32) + "\n")
    key_file.chmod(0o600)
    if download_only:
        print("Pinned model and runtime verified. Local API key stored in ignored runtime storage.")
        return
    os.execv(executable, [str(executable), "-m", str(runtime / model["file"]), "--alias", model["alias"],
        "--host", "127.0.0.1", "--port", "8081", "-c", "8192", "-t", "4", "--parallel", "1", "--jinja",
        "--no-webui", "--api-key-file", str(key_file), "--cors-origins", "http://127.0.0.1:8000"])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument("--download-only", action="store_true")
    main(parser.parse_args().download_only)
