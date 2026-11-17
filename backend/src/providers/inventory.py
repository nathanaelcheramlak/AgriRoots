import json
from pathlib import Path


def inventory():
    path = Path(__file__).resolve().parents[2] / "reports/provider_inventory.json"
    return (
        json.loads(path.read_text(encoding="utf-8"))
        if path.is_file()
        else {"providers": [], "note": "Historical inventory has not been imported"}
    )
