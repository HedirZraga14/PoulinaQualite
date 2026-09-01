from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
import time
from typing import Any

from django.db import connections
from django.http import HttpRequest, HttpResponse, JsonResponse
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest


PROJECT_ROOT = Path(__file__).resolve().parents[2]
MLOPS_REGISTRY_PATH = PROJECT_ROOT / "outputs" / "mlops" / "registry.json"
CLASSIFICATION_MODEL_PATH = PROJECT_ROOT / "models" / "objectif1_non_conformite.joblib"
REGRESSION_MODEL_PATH = PROJECT_ROOT / "models" / "objectif2_note.joblib"


HTTP_REQUESTS_TOTAL = Counter(
    "poulina_http_requests_total",
    "Nombre total de requetes HTTP servies par Django.",
    ["method", "route", "status"],
)
HTTP_REQUEST_DURATION_SECONDS = Histogram(
    "poulina_http_request_duration_seconds",
    "Temps de reponse des requetes HTTP.",
    ["method", "route"],
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10),
)
ML_INFERENCE_REQUESTS_TOTAL = Counter(
    "poulina_ml_inference_requests_total",
    "Nombre total de requetes d'inference ML.",
    ["outcome"],
)
ML_INFERENCE_DURATION_SECONDS = Histogram(
    "poulina_ml_inference_duration_seconds",
    "Temps d'execution de l'inference ML.",
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10),
)
ML_INFERENCE_ROWS = Histogram(
    "poulina_ml_inference_rows",
    "Nombre de lignes predites par requete ML.",
    buckets=(1, 5, 10, 20, 30, 43, 50, 75, 100),
)
ML_INFERENCE_NON_CONFORMITIES = Histogram(
    "poulina_ml_inference_non_conformities",
    "Nombre de non-conformites predites par requete ML.",
    buckets=(0, 1, 3, 5, 10, 20, 30, 43, 50),
)
ML_INFERENCE_LAST_AVERAGE_NOTE = Gauge(
    "poulina_ml_inference_last_average_note",
    "Derniere note moyenne predite.",
)
ML_MODEL_LOADS_TOTAL = Counter(
    "poulina_ml_model_loads_total",
    "Nombre de chargements ou rechargements des modeles ML.",
    ["outcome"],
)
MLOPS_REGISTRY_LAST_UPDATE_TIMESTAMP_SECONDS = Gauge(
    "poulina_mlops_registry_last_update_timestamp_seconds",
    "Timestamp de la derniere mise a jour du registre MLOps.",
)
MLOPS_PROMOTED_MODEL = Gauge(
    "poulina_mlops_promoted_model",
    "Modele promu courant pour chaque objectif.",
    ["objective", "task_type", "model_name"],
)
MLOPS_PROMOTED_METRIC = Gauge(
    "poulina_mlops_promoted_metric",
    "Metriques du modele promu.",
    ["objective", "model_name", "metric"],
)
MLOPS_TRAINING_ROWS = Gauge(
    "poulina_mlops_training_rows",
    "Nombre de lignes avant et apres augmentation pour le dernier run.",
    ["objective", "stage"],
)
MODEL_ARTIFACT_SIZE_BYTES = Gauge(
    "poulina_model_artifact_size_bytes",
    "Taille des artefacts de modeles deployes.",
    ["objective", "artifact_name"],
)
MODEL_ARTIFACT_UPDATED_AT = Gauge(
    "poulina_model_artifact_updated_at_timestamp_seconds",
    "Date de mise a jour des artefacts de modeles deployes.",
    ["objective", "artifact_name"],
)


def _json_read(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return default


def _parse_iso_datetime(value: str | None) -> float | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


def _normalize_route(request: HttpRequest) -> str:
    resolver_match = getattr(request, "resolver_match", None)
    route = getattr(resolver_match, "route", None)
    if route:
        return f"/{route.lstrip('/')}"
    path = request.path or "/"
    if len(path) > 80:
        return path[:77] + "..."
    return path


def observe_http_request(request: HttpRequest, response: HttpResponse | None, duration: float) -> None:
    method = (request.method or "GET").upper()
    route = _normalize_route(request)
    status = str(getattr(response, "status_code", 500))
    HTTP_REQUESTS_TOTAL.labels(method=method, route=route, status=status).inc()
    HTTP_REQUEST_DURATION_SECONDS.labels(method=method, route=route).observe(max(duration, 0.0))


def record_ml_model_load(outcome: str) -> None:
    ML_MODEL_LOADS_TOTAL.labels(outcome=outcome).inc()


def record_ml_inference_success(*, rows_count: int, non_conformities: int, average_note: float, duration: float) -> None:
    ML_INFERENCE_REQUESTS_TOTAL.labels(outcome="success").inc()
    ML_INFERENCE_DURATION_SECONDS.observe(max(duration, 0.0))
    ML_INFERENCE_ROWS.observe(max(rows_count, 0))
    ML_INFERENCE_NON_CONFORMITIES.observe(max(non_conformities, 0))
    ML_INFERENCE_LAST_AVERAGE_NOTE.set(float(average_note))


def record_ml_inference_failure(duration: float) -> None:
    ML_INFERENCE_REQUESTS_TOTAL.labels(outcome="failure").inc()
    ML_INFERENCE_DURATION_SECONDS.observe(max(duration, 0.0))


def sync_mlops_registry_metrics() -> None:
    registry = _json_read(MLOPS_REGISTRY_PATH, {"updated_at": None, "objectives": {}})
    objectives = registry.get("objectives", {})

    MLOPS_PROMOTED_MODEL.clear()
    MLOPS_PROMOTED_METRIC.clear()
    MLOPS_TRAINING_ROWS.clear()
    MODEL_ARTIFACT_SIZE_BYTES.clear()
    MODEL_ARTIFACT_UPDATED_AT.clear()

    last_update_ts = _parse_iso_datetime(registry.get("updated_at"))
    if last_update_ts is not None:
      MLOPS_REGISTRY_LAST_UPDATE_TIMESTAMP_SECONDS.set(last_update_ts)

    for objective, payload in objectives.items():
        task_type = str(payload.get("task_type", "unknown"))
        model_name = str(payload.get("promoted_model_name", "unknown"))
        MLOPS_PROMOTED_MODEL.labels(
            objective=objective,
            task_type=task_type,
            model_name=model_name,
        ).set(1)

        for metric_name, metric_value in (payload.get("promoted_metrics") or {}).items():
            if metric_name == "modele":
                continue
            try:
                numeric_value = float(metric_value)
            except (TypeError, ValueError):
                continue
            MLOPS_PROMOTED_METRIC.labels(
                objective=objective,
                model_name=model_name,
                metric=metric_name,
            ).set(numeric_value)

        base_rows = payload.get("base_rows")
        augmented_rows = payload.get("augmented_rows")
        if isinstance(base_rows, (int, float)):
            MLOPS_TRAINING_ROWS.labels(objective=objective, stage="base").set(float(base_rows))
        if isinstance(augmented_rows, (int, float)):
            MLOPS_TRAINING_ROWS.labels(objective=objective, stage="augmented").set(float(augmented_rows))

        artifact = payload.get("artifact") or {}
        artifact_name = Path(str(artifact.get("path", objective))).name
        size_bytes = artifact.get("size_bytes")
        if isinstance(size_bytes, (int, float)):
            MODEL_ARTIFACT_SIZE_BYTES.labels(objective=objective, artifact_name=artifact_name).set(float(size_bytes))
        artifact_updated_at = _parse_iso_datetime(artifact.get("updated_at"))
        if artifact_updated_at is not None:
            MODEL_ARTIFACT_UPDATED_AT.labels(objective=objective, artifact_name=artifact_name).set(artifact_updated_at)


def _check_database_health() -> dict[str, Any]:
    try:
        with connections["default"].cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
        return {"status": "up"}
    except Exception as exc:  # noqa: BLE001
        return {"status": "down", "detail": str(exc)}


def health_view(request: HttpRequest) -> JsonResponse:
    db_status = _check_database_health()
    models_status = {
        "objectif1_non_conformite": CLASSIFICATION_MODEL_PATH.exists(),
        "objectif2_note": REGRESSION_MODEL_PATH.exists(),
    }
    app_status = "up" if db_status["status"] == "up" and all(models_status.values()) else "degraded"
    return JsonResponse(
        {
            "status": app_status,
            "database": db_status,
            "models": models_status,
            "timestamp": time.time(),
        },
        status=200 if app_status == "up" else 503,
    )


def metrics_view(request: HttpRequest) -> HttpResponse:
    sync_mlops_registry_metrics()
    return HttpResponse(generate_latest(), content_type=CONTENT_TYPE_LATEST)
