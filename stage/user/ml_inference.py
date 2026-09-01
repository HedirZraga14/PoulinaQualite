from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json
import math
from typing import Any
import time

import joblib
import numpy as np
import pandas as pd

from .monitoring import record_ml_inference_failure, record_ml_inference_success, record_ml_model_load
from .models import Branch, DateDim, User


class ModelInferenceError(RuntimeError):
    """Raised when ML models cannot be loaded or executed."""


PROJECT_ROOT = Path(__file__).resolve().parents[2]
MODELS_DIR = PROJECT_ROOT / "models"
MLOPS_REGISTRY_PATH = PROJECT_ROOT / "outputs" / "mlops" / "registry.json"
CLASSIFICATION_MODEL_PATH = MODELS_DIR / "objectif1_non_conformite.joblib"
REGRESSION_MODEL_PATH = MODELS_DIR / "objectif2_note.joblib"
NON_CONFORMITE_THRESHOLD = 16.0
NUMERIC_FEATURES = [
    "critere_rang",
    "ponderation_num",
    "jour",
    "mois",
    "trimestre",
    "annee",
    "latitude",
    "longitude",
]
CATEGORICAL_FEATURES = [
    "axe_evaluation",
    "criteres",
    "role_utilisateur",
    "utilisateur",
    "filiale",
    "secteur",
]

MONTH_TO_NUMBER = {
    "janvier": 1,
    "février": 2,
    "fevrier": 2,
    "mars": 3,
    "avril": 4,
    "mai": 5,
    "juin": 6,
    "juillet": 7,
    "août": 8,
    "aout": 8,
    "septembre": 9,
    "octobre": 10,
    "novembre": 11,
    "décembre": 12,
    "decembre": 12,
}


@dataclass
class PreparedRow:
    row_index: int
    axe_evaluation: str
    criteres: str
    ponderation_num: float
    actual_note: float | None


def _safe_float(value: Any) -> float | None:
    text = str(value or "").strip().replace(",", ".")
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _safe_int(value: Any, default: int) -> int:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError, AttributeError):
        return default


def _normalize_text(value: Any) -> str:
    return str(value or "").strip()


def _month_to_number(label: Any) -> int:
    month_name = _normalize_text(label).lower()
    if month_name.isdigit():
        month_num = int(month_name)
        return month_num if 1 <= month_num <= 12 else 1
    return MONTH_TO_NUMBER.get(month_name, 1)


def _compute_trimestre(month_number: int) -> int:
    return ((max(1, min(12, month_number)) - 1) // 3) + 1


def _user_display_name(user: User | None) -> str:
    if user is None:
        return ""
    full_name = f"{user.first_name or ''} {user.last_name or ''}".strip()
    return full_name or user.email or ""


def _resolve_branch_from_payload(item: dict[str, Any], user: User | None) -> Branch | None:
    code = _normalize_text(item.get("code"))
    if code.isdigit():
        branch = Branch.objects.select_related("sector").filter(code=int(code)).first()
        if branch:
            return branch

    filiale_name = _normalize_text(item.get("filiale") or item.get("filiale_name"))
    if filiale_name:
        branch = Branch.objects.select_related("sector").filter(name__iexact=filiale_name).first()
        if branch:
            return branch

    if user and getattr(user, "branch_id", None):
        return Branch.objects.select_related("sector").filter(pk=user.branch_id).first()
    return None


def _resolve_branch_with_cache(
    item: dict[str, Any],
    user: User | None,
    cache_by_code: dict[str, Branch | None],
    cache_by_name: dict[str, Branch | None],
    default_user_branch: Branch | None,
) -> Branch | None:
    # Skip DB work when payload already carries the fields the models need.
    filiale_name = _normalize_text(item.get("filiale") or item.get("filiale_name"))
    secteur_name = _normalize_text(item.get("secteur") or item.get("secteur_name"))
    if filiale_name and secteur_name:
        return None

    code = _normalize_text(item.get("code"))
    if code.isdigit():
        if code not in cache_by_code:
            cache_by_code[code] = Branch.objects.select_related("sector").filter(code=int(code)).first()
        if cache_by_code[code]:
            return cache_by_code[code]

    if filiale_name:
        key = filiale_name.casefold()
        if key not in cache_by_name:
            cache_by_name[key] = Branch.objects.select_related("sector").filter(name__iexact=filiale_name).first()
        if cache_by_name[key]:
            return cache_by_name[key]

    return default_user_branch


def _resolve_sector_name(item: dict[str, Any], user: User | None, branch: Branch | None) -> str:
    sector_name = _normalize_text(item.get("secteur") or item.get("secteur_name"))
    if sector_name:
        return sector_name
    if branch and branch.sector:
        return branch.sector.name
    if user and getattr(user, "sector", None):
        return user.sector.name
    managed_sector = getattr(user, "managed_sector", None) if user else None
    return managed_sector.name if managed_sector else ""


def _resolve_filiale_name(item: dict[str, Any], user: User | None, branch: Branch | None) -> str:
    filiale_name = _normalize_text(item.get("filiale") or item.get("filiale_name"))
    if filiale_name:
        return filiale_name
    if branch:
        return branch.name
    if user and getattr(user, "branch", None):
        return user.branch.name
    return ""


def _resolve_user_name(item: dict[str, Any], user: User | None) -> str:
    payload_name = _normalize_text(item.get("user_name") or item.get("auditeur") or item.get("utilisateur"))
    return payload_name or _user_display_name(user)


_MODEL_CACHE: tuple[Any, Any] | None = None
_MODEL_SIGNATURE: tuple[float, float] | None = None


def _current_model_signature() -> tuple[float, float]:
    return (
        CLASSIFICATION_MODEL_PATH.stat().st_mtime,
        REGRESSION_MODEL_PATH.stat().st_mtime,
    )


def _load_models(force_reload: bool = False) -> tuple[Any, Any]:
    global _MODEL_CACHE, _MODEL_SIGNATURE

    if not CLASSIFICATION_MODEL_PATH.exists():
        raise ModelInferenceError(f"Modèle introuvable: {CLASSIFICATION_MODEL_PATH}")
    if not REGRESSION_MODEL_PATH.exists():
        raise ModelInferenceError(f"Modèle introuvable: {REGRESSION_MODEL_PATH}")

    signature = _current_model_signature()
    if not force_reload and _MODEL_CACHE is not None and _MODEL_SIGNATURE == signature:
        return _MODEL_CACHE

    try:
        classification_model = joblib.load(CLASSIFICATION_MODEL_PATH)
        regression_model = joblib.load(REGRESSION_MODEL_PATH)
        record_ml_model_load("reload_success" if force_reload else "load_success")
    except Exception as exc:  # noqa: BLE001
        record_ml_model_load("reload_failure" if force_reload else "load_failure")
        raise ModelInferenceError(f"Impossible de charger les modèles ML: {exc}") from exc

    _MODEL_CACHE = (classification_model, regression_model)
    _MODEL_SIGNATURE = signature
    return _MODEL_CACHE


try:
    _load_models()
except Exception:
    # Keep app startup resilient; endpoint will report a clear error if loading still fails later.
    pass


def _sanitize_feature_frame(frame: pd.DataFrame) -> pd.DataFrame:
    cleaned = frame.copy()

    for col in NUMERIC_FEATURES:
        if col in cleaned.columns:
            cleaned[col] = pd.to_numeric(cleaned[col], errors="coerce")

    for col in CATEGORICAL_FEATURES:
        if col in cleaned.columns:
            series = cleaned[col].astype("object")
            cleaned[col] = series.where(pd.notna(series), np.nan)

    return cleaned


def _build_feature_frame(evaluations: list[dict[str, Any]], user: User | None) -> tuple[pd.DataFrame, list[PreparedRow]]:
    feature_rows: list[dict[str, Any]] = []
    prepared_rows: list[PreparedRow] = []
    branch_cache_by_code: dict[str, Branch | None] = {}
    branch_cache_by_name: dict[str, Branch | None] = {}
    default_user_branch = None

    if user and getattr(user, "branch_id", None):
        default_user_branch = Branch.objects.select_related("sector").filter(pk=user.branch_id).first()

    for index, item in enumerate(evaluations, start=1):
        branch = _resolve_branch_with_cache(
            item,
            user,
            branch_cache_by_code,
            branch_cache_by_name,
            default_user_branch,
        )
        month_number = _month_to_number(item.get("month") or item.get("mois"))
        year_value = _safe_int(item.get("year") or item.get("annee"), 2026)
        actual_note = _safe_float(item.get("note"))
        ponderation_num = _safe_float(item.get("ponderation")) or 0.0

        feature_rows.append(
            {
                "critere_rang": index,
                "ponderation_num": ponderation_num,
                "jour": _safe_int(item.get("jour"), 1),
                "mois": month_number,
                "trimestre": _compute_trimestre(month_number),
                "annee": year_value,
                "latitude": math.nan,
                "longitude": math.nan,
                "axe_evaluation": _normalize_text(item.get("axe_evaluation")) or "Sans axe",
                "criteres": _normalize_text(item.get("criteres")) or "Sans critere",
                "role_utilisateur": getattr(user, "role", "") or _normalize_text(item.get("role_utilisateur")),
                "utilisateur": _resolve_user_name(item, user),
                "filiale": _resolve_filiale_name(item, user, branch),
                "secteur": _resolve_sector_name(item, user, branch),
            }
        )
        prepared_rows.append(
            PreparedRow(
                row_index=index - 1,
                axe_evaluation=_normalize_text(item.get("axe_evaluation")),
                criteres=_normalize_text(item.get("criteres")),
                ponderation_num=ponderation_num,
                actual_note=actual_note,
            )
        )

    return pd.DataFrame(feature_rows), prepared_rows


def _current_best_models() -> dict[str, str]:
    defaults = {
        "classification": "svc_rbf",
        "regression": "random_forest_regressor",
    }
    if not MLOPS_REGISTRY_PATH.exists():
        return defaults
    try:
        registry = json.loads(MLOPS_REGISTRY_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return defaults

    objectives = registry.get("objectives", {})
    classification = objectives.get("objectif1_non_conformite", {})
    regression = objectives.get("objectif2_prediction_note", {})
    return {
        "classification": classification.get("promoted_model_name", defaults["classification"]),
        "regression": regression.get("promoted_model_name", defaults["regression"]),
    }


def _performance_label(note: float) -> str:
    if note >= 18:
        return "eleve"
    if note >= NON_CONFORMITE_THRESHOLD:
        return "conforme"
    if note >= 10:
        return "moyen"
    return "faible"


def predict_evaluations(evaluations: list[dict[str, Any]], user: User | None) -> dict[str, Any]:
    if not evaluations:
        raise ModelInferenceError("Aucune évaluation à prédire.")

    inference_started_at = time.perf_counter()
    classification_model, regression_model = _load_models()
    feature_frame, prepared_rows = _build_feature_frame(evaluations, user)
    feature_frame = _sanitize_feature_frame(feature_frame)

    try:
        classification_predictions = classification_model.predict(feature_frame)
        regression_predictions = regression_model.predict(feature_frame)
        prediction_probabilities = None
        if hasattr(classification_model, "predict_proba"):
            probabilities = classification_model.predict_proba(feature_frame)
            classes = list(getattr(classification_model, "classes_", []))
            class_one_index = classes.index(1) if 1 in classes else None
            if class_one_index is not None:
                prediction_probabilities = probabilities[:, class_one_index]
    except Exception as exc:  # noqa: BLE001
        # Retry once after refreshing the cached models in case files changed while the server was running.
        try:
            classification_model, regression_model = _load_models(force_reload=True)
            classification_predictions = classification_model.predict(feature_frame)
            regression_predictions = regression_model.predict(feature_frame)
            prediction_probabilities = None
            if hasattr(classification_model, "predict_proba"):
                probabilities = classification_model.predict_proba(feature_frame)
                classes = list(getattr(classification_model, "classes_", []))
                class_one_index = classes.index(1) if 1 in classes else None
                if class_one_index is not None:
                    prediction_probabilities = probabilities[:, class_one_index]
        except Exception as retry_exc:  # noqa: BLE001
            record_ml_inference_failure(time.perf_counter() - inference_started_at)
            raise ModelInferenceError(f"Erreur lors de l'inférence ML: {retry_exc}") from retry_exc

    rows_payload: list[dict[str, Any]] = []
    predicted_notes: list[float] = []
    non_conformity_count = 0

    for index, prepared in enumerate(prepared_rows):
        predicted_note = round(float(regression_predictions[index]), 2)
        predicted_note = min(20.0, max(0.0, predicted_note))
        # Business rule: a criterion is non-conforming iff predicted note < 16.
        predicted_non_conforme = predicted_note < NON_CONFORMITE_THRESHOLD
        probability = (
            round(float(prediction_probabilities[index]) * 100.0, 1)
            if prediction_probabilities is not None
            else None
        )

        if predicted_non_conforme:
            non_conformity_count += 1
        predicted_notes.append(predicted_note)

        rows_payload.append(
            {
                "row_index": prepared.row_index,
                "axe_evaluation": prepared.axe_evaluation,
                "criteres": prepared.criteres,
                "ponderation_num": prepared.ponderation_num,
                "predicted_note": predicted_note,
                "predicted_level": _performance_label(predicted_note),
                "predicted_non_conforme": predicted_non_conforme,
                "probability_non_conformite": probability,
                "actual_note": prepared.actual_note,
                "actual_non_conforme": (
                    prepared.actual_note < NON_CONFORMITE_THRESHOLD if prepared.actual_note is not None else None
                ),
            }
        )

    total_rows = len(rows_payload)
    average_note = round(sum(predicted_notes) / total_rows, 2) if predicted_notes else 0.0
    conformity_count = total_rows - non_conformity_count
    conformity_pct = round((conformity_count / total_rows) * 100.0, 1) if total_rows else 0.0
    top_risks = sorted(
        rows_payload,
        key=lambda item: (
            item["predicted_non_conforme"],
            item["probability_non_conformite"] if item["probability_non_conformite"] is not None else -1.0,
            -item["predicted_note"],
        ),
        reverse=True,
    )[:5]

    record_ml_inference_success(
        rows_count=total_rows,
        non_conformities=non_conformity_count,
        average_note=average_note,
        duration=time.perf_counter() - inference_started_at,
    )

    return {
        "summary": {
            "threshold_non_conformite": NON_CONFORMITE_THRESHOLD,
            "predicted_average_note": average_note,
            "predicted_conformity_pct": conformity_pct,
            "predicted_conformity_count": conformity_count,
            "predicted_non_conformities": non_conformity_count,
            "total_rows": total_rows,
            "best_models": _current_best_models(),
        },
        "rows": rows_payload,
        "top_risks": top_risks,
    }
