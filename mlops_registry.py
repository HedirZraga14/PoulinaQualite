from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
from typing import Any

import joblib
import numpy as np
import pandas as pd
import sklearn


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUTS_DIR = PROJECT_DIR / "outputs"
MLOPS_DIR = OUTPUTS_DIR / "mlops"
RUNS_DIR = MLOPS_DIR / "runs"
REGISTRY_PATH = MLOPS_DIR / "registry.json"


def _ensure_dirs() -> None:
    RUNS_DIR.mkdir(parents=True, exist_ok=True)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _json_ready(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_ready(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_ready(item) for item in value]
    if isinstance(value, tuple):
        return [_json_ready(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return float(value)
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if pd.isna(value) if not isinstance(value, (str, bytes, bytearray)) else False:
        return None
    return value


def _read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return default


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    serialized = json.dumps(_json_ready(payload), indent=2, ensure_ascii=False)
    path.write_text(serialized + "\n", encoding="utf-8")


def _append_jsonl(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    serialized = json.dumps(_json_ready(payload), ensure_ascii=False)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(serialized + "\n")


def _sha256(path: Path) -> str | None:
    if not path.exists():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _runtime_environment() -> dict[str, Any]:
    return {
        "python_version": platform.python_version(),
        "sklearn_version": sklearn.__version__,
        "pandas_version": pd.__version__,
        "numpy_version": np.__version__,
        "joblib_version": joblib.__version__,
        "platform": platform.platform(),
    }


def _model_artifact(path: Path | None) -> dict[str, Any] | None:
    if path is None:
        return None
    resolved = path.resolve()
    if not resolved.exists():
        return {
            "path": str(resolved),
            "exists": False,
        }
    stat = resolved.stat()
    return {
        "path": str(resolved),
        "exists": True,
        "size_bytes": int(stat.st_size),
        "updated_at": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
        "sha256": _sha256(resolved),
    }


def _best_metrics(comparison: pd.DataFrame, best_model_name: str) -> dict[str, Any]:
    if comparison.empty:
        return {}
    row = comparison.loc[comparison["modele"] == best_model_name]
    if row.empty:
        row = comparison.iloc[[0]]
    return _json_ready(row.iloc[0].to_dict())


def _top_models(comparison: pd.DataFrame, limit: int = 3) -> list[dict[str, Any]]:
    if comparison.empty:
        return []
    return _json_ready(comparison.head(limit).to_dict(orient="records"))


def record_training_run(
    *,
    objective_name: str,
    task_type: str,
    comparison: pd.DataFrame,
    best_model_name: str,
    model_path: Path | None,
    base_rows: int,
    augmented_rows: int,
    training_config: dict[str, Any],
    data_summary: dict[str, Any] | None = None,
) -> dict[str, Any]:
    _ensure_dirs()

    started_at = _now_iso()
    run_id = f"{objective_name}_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
    best_metrics = _best_metrics(comparison, best_model_name)

    payload = {
        "run_id": run_id,
        "objective_name": objective_name,
        "task_type": task_type,
        "started_at": started_at,
        "status": "completed",
        "best_model_name": best_model_name,
        "best_metrics": best_metrics,
        "top_models": _top_models(comparison),
        "base_rows": int(base_rows),
        "augmented_rows": int(augmented_rows),
        "training_config": training_config,
        "data_summary": data_summary or {},
        "artifact": _model_artifact(model_path),
        "runtime_environment": _runtime_environment(),
    }

    _append_jsonl(RUNS_DIR / f"{objective_name}.jsonl", payload)

    registry = _read_json(
        REGISTRY_PATH,
        {
            "updated_at": None,
            "objectives": {},
        },
    )
    registry["updated_at"] = _now_iso()
    registry.setdefault("objectives", {})
    registry["objectives"][objective_name] = {
        "objective_name": objective_name,
        "task_type": task_type,
        "current_run_id": run_id,
        "promoted_model_name": best_model_name,
        "promoted_metrics": best_metrics,
        "artifact": _model_artifact(model_path),
        "base_rows": int(base_rows),
        "augmented_rows": int(augmented_rows),
        "training_config": training_config,
        "runtime_environment": _runtime_environment(),
        "latest_top_models": _top_models(comparison),
        "latest_data_summary": data_summary or {},
        "updated_at": _now_iso(),
    }
    _write_json(REGISTRY_PATH, registry)
    return payload


def _read_recent_runs(limit_per_objective: int = 3) -> dict[str, list[dict[str, Any]]]:
    _ensure_dirs()
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


def get_mlops_status() -> dict[str, Any]:
    _ensure_dirs()
    registry = _read_json(REGISTRY_PATH, {"updated_at": None, "objectives": {}})
    return {
        "updated_at": registry.get("updated_at"),
        "registry": registry.get("objectives", {}),
        "recent_runs": _read_recent_runs(limit_per_objective=3),
        "paths": {
            "mlops_dir": str(MLOPS_DIR.resolve()),
            "registry_path": str(REGISTRY_PATH.resolve()),
            "runs_dir": str(RUNS_DIR.resolve()),
        },
    }
