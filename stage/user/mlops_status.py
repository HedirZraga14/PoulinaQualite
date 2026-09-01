from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
MLOPS_DIR = PROJECT_ROOT / "outputs" / "mlops"
REGISTRY_PATH = MLOPS_DIR / "registry.json"
RUNS_DIR = MLOPS_DIR / "runs"
MODELS_DIR = PROJECT_ROOT / "models"


def _read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return default


def _read_recent_runs(limit_per_objective: int = 3) -> dict[str, list[dict[str, Any]]]:
    if not RUNS_DIR.exists():
        return {}

    recent: dict[str, list[dict[str, Any]]] = {}
    for path in RUNS_DIR.glob("*.jsonl"):
        rows = []
        for raw_line in path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        rows.sort(key=lambda item: item.get("started_at") or "", reverse=True)
        recent[path.stem] = rows[:limit_per_objective]
    return recent


def _artifact_status(name: str) -> dict[str, Any]:
    path = MODELS_DIR / name
    if not path.exists():
        return {
            "path": str(path),
            "exists": False,
        }
    stat = path.stat()
    return {
        "path": str(path),
        "exists": True,
        "size_bytes": int(stat.st_size),
        "updated_at": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
    }


def get_backend_mlops_status() -> dict[str, Any]:
    registry = _read_json(REGISTRY_PATH, {"updated_at": None, "objectives": {}})
    return {
        "updated_at": registry.get("updated_at"),
        "registry": registry.get("objectives", {}),
        "recent_runs": _read_recent_runs(limit_per_objective=3),
        "artifacts": {
            "objectif1_non_conformite.joblib": _artifact_status("objectif1_non_conformite.joblib"),
            "objectif2_note.joblib": _artifact_status("objectif2_note.joblib"),
        },
        "paths": {
            "mlops_dir": str(MLOPS_DIR),
            "registry_path": str(REGISTRY_PATH),
            "runs_dir": str(RUNS_DIR),
        },
        "monitoring": {
            "health_endpoint": "/monitoring/health/",
            "metrics_endpoint": "/monitoring/metrics/",
            "prometheus_url": "http://localhost:9090",
            "grafana_url": "http://localhost:3001",
            "mlflow_url": "http://localhost:5000",
        },
    }
