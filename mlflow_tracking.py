from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
from typing import Any
from urllib import error, parse, request

import numpy as np
import pandas as pd


DEFAULT_TRACKING_URI = os.environ.get("MLFLOW_TRACKING_URI", "http://127.0.0.1:5000").rstrip("/")


def _now_ms() -> int:
    return int(datetime.now(timezone.utc).timestamp() * 1000)


def _stringify(value: Any) -> str:
    if isinstance(value, Path):
        return str(value.resolve())
    if isinstance(value, (dict, list, tuple)):
        return json.dumps(value, ensure_ascii=False, default=str)
    if pd.isna(value) if not isinstance(value, (str, bytes, bytearray)) else False:
        return ""
    return str(value)


def _is_number(value: Any) -> bool:
    if isinstance(value, bool):
        return False
    if isinstance(value, (int, float, np.integer, np.floating)):
        try:
            return np.isfinite(float(value))
        except (TypeError, ValueError):
            return False
    return False


def _mlflow_request(
    method: str,
    path: str,
    *,
    payload: dict[str, Any] | None = None,
    query: dict[str, Any] | None = None,
    tracking_uri: str = DEFAULT_TRACKING_URI,
) -> dict[str, Any]:
    url = f"{tracking_uri}{path}"
    if query:
        url = f"{url}?{parse.urlencode(query, doseq=True)}"

    data = None
    headers: dict[str, str] = {}
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"

    req = request.Request(url, data=data, headers=headers, method=method)
    try:
        with request.urlopen(req, timeout=30) as response:
            raw = response.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"MLflow HTTP {exc.code} on {path}: {raw}") from exc
    except error.URLError as exc:
        raise RuntimeError(f"MLflow unreachable on {tracking_uri}: {exc.reason}") from exc


def _ensure_experiment(experiment_name: str, tracking_uri: str) -> str:
    try:
        response = _mlflow_request(
            "GET",
            "/api/2.0/mlflow/experiments/get-by-name",
            query={"experiment_name": experiment_name},
            tracking_uri=tracking_uri,
        )
        experiment = response.get("experiment", {})
        experiment_id = experiment.get("experiment_id")
        if experiment_id:
            return str(experiment_id)
    except RuntimeError as exc:
        if "HTTP 404" not in str(exc) and "RESOURCE_DOES_NOT_EXIST" not in str(exc):
            raise

    response = _mlflow_request(
        "POST",
        "/api/2.0/mlflow/experiments/create",
        payload={"name": experiment_name},
        tracking_uri=tracking_uri,
    )
    return str(response["experiment_id"])


def _create_run(
    *,
    experiment_id: str,
    run_name: str,
    tracking_uri: str,
    tags: dict[str, Any] | None = None,
) -> str:
    response = _mlflow_request(
        "POST",
        "/api/2.0/mlflow/runs/create",
        payload={
            "experiment_id": experiment_id,
            "start_time": _now_ms(),
            "run_name": run_name,
            "tags": [
                {"key": key, "value": _stringify(value)}
                for key, value in (tags or {}).items()
            ],
        },
        tracking_uri=tracking_uri,
    )
    info = response.get("run", {}).get("info", {})
    run_id = info.get("run_id") or info.get("run_uuid")
    if not run_id:
        raise RuntimeError("MLflow did not return a run_id.")
    return str(run_id)


def _update_run_status(run_id: str, status: str, tracking_uri: str) -> None:
    _mlflow_request(
        "POST",
        "/api/2.0/mlflow/runs/update",
        payload={
            "run_id": run_id,
            "status": status,
            "end_time": _now_ms(),
        },
        tracking_uri=tracking_uri,
    )


def _log_batch(
    run_id: str,
    *,
    params_payload: dict[str, Any] | None = None,
    metrics_payload: dict[str, float] | None = None,
    tags_payload: dict[str, Any] | None = None,
    tracking_uri: str,
) -> None:
    params = [
        {"key": key, "value": _stringify(value)[:8000]}
        for key, value in (params_payload or {}).items()
        if value is not None
    ]
    metrics = [
        {
            "key": key,
            "value": float(value),
            "timestamp": _now_ms(),
            "step": 0,
        }
        for key, value in (metrics_payload or {}).items()
        if _is_number(value)
    ]
    tags = [
        {"key": key, "value": _stringify(value)}
        for key, value in (tags_payload or {}).items()
        if value is not None
    ]

    if not params and not metrics and not tags:
        return

    _mlflow_request(
        "POST",
        "/api/2.0/mlflow/runs/log-batch",
        payload={
            "run_id": run_id,
            "params": params,
            "metrics": metrics,
            "tags": tags,
        },
        tracking_uri=tracking_uri,
    )


def _comparison_payload(comparison: pd.DataFrame) -> tuple[dict[str, Any], dict[str, float]]:
    params_payload: dict[str, Any] = {}
    metrics_payload: dict[str, float] = {}
    if comparison.empty:
        return params_payload, metrics_payload

    for rank, row in enumerate(comparison.head(3).itertuples(index=False), start=1):
        row_dict = row._asdict()
        model_name = row_dict.get("modele", f"model_{rank}")
        params_payload[f"ranking.rank_{rank}.model_name"] = model_name
        for key, value in row_dict.items():
            if key == "modele":
                continue
            metric_key = f"ranking.rank_{rank}.{key}"
            if _is_number(value):
                metrics_payload[metric_key] = float(value)
            else:
                params_payload[metric_key] = value
    return params_payload, metrics_payload


def log_training_run_to_mlflow(
    *,
    experiment_name: str,
    run_name: str,
    objective_name: str,
    task_type: str,
    best_model_name: str,
    comparison: pd.DataFrame,
    training_payload: dict[str, Any],
    model_path: Path | None,
    comparison_path: Path | None,
    tracking_uri: str = DEFAULT_TRACKING_URI,
) -> dict[str, Any]:
    run_id: str | None = None
    try:
        experiment_id = _ensure_experiment(experiment_name, tracking_uri)
        run_id = _create_run(
            experiment_id=experiment_id,
            run_name=run_name,
            tracking_uri=tracking_uri,
            tags={
                "objective_name": objective_name,
                "task_type": task_type,
                "best_model_name": best_model_name,
                "tracking_bridge": "custom_mlops_registry",
            },
        )

        best_metrics = training_payload.get("best_metrics", {})
        comparison_params, comparison_metrics = _comparison_payload(comparison)
        data_summary = training_payload.get("data_summary", {})
        artifact = training_payload.get("artifact") or {}
        runtime_environment = training_payload.get("runtime_environment", {})

        params_payload = {
            "objective_name": objective_name,
            "task_type": task_type,
            "best_model_name": best_model_name,
            "base_rows": training_payload.get("base_rows"),
            "augmented_rows": training_payload.get("augmented_rows"),
            "training_config": training_payload.get("training_config", {}),
            "comparison_csv_path": comparison_path.resolve() if comparison_path else None,
            "model_artifact_path": model_path.resolve() if model_path else None,
            **comparison_params,
        }
        metrics_payload = {
            "dataset.base_rows": float(training_payload.get("base_rows", 0)),
            "dataset.augmented_rows": float(training_payload.get("augmented_rows", 0)),
            **{
                f"best.{key}": float(value)
                for key, value in best_metrics.items()
                if key != "modele" and _is_number(value)
            },
            **{
                f"data_summary.{key}": float(value)
                for key, value in data_summary.items()
                if _is_number(value)
            },
            **{
                f"artifact.{key}": float(value)
                for key, value in artifact.items()
                if _is_number(value)
            },
            **comparison_metrics,
        }
        tags_payload = {
            "mlops_run_id": training_payload.get("run_id"),
            "run_status": training_payload.get("status"),
            "runtime_environment": runtime_environment,
            "data_summary": {
                key: value
                for key, value in data_summary.items()
                if not _is_number(value)
            },
        }

        _log_batch(
            run_id,
            params_payload=params_payload,
            metrics_payload=metrics_payload,
            tags_payload=tags_payload,
            tracking_uri=tracking_uri,
        )
        _update_run_status(run_id, "FINISHED", tracking_uri)

        return {
            "enabled": True,
            "status": "completed",
            "tracking_uri": tracking_uri,
            "experiment_name": experiment_name,
            "experiment_id": experiment_id,
            "run_id": run_id,
            "ui_url": f"{tracking_uri}/#/experiments/{experiment_id}/runs/{run_id}",
        }
    except Exception as exc:
        if run_id:
            try:
                _update_run_status(run_id, "FAILED", tracking_uri)
            except Exception:
                pass
        return {
            "enabled": True,
            "status": "error",
            "tracking_uri": tracking_uri,
            "experiment_name": experiment_name,
            "message": str(exc),
        }
