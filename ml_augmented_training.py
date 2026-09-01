from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import ExtraTreesRegressor, GradientBoostingClassifier, GradientBoostingRegressor, RandomForestClassifier, RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.metrics import accuracy_score, balanced_accuracy_score, f1_score, make_scorer, mean_absolute_error, mean_squared_error, precision_score, r2_score, recall_score, roc_auc_score
from sklearn.model_selection import KFold, StratifiedKFold, cross_validate
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.svm import SVC

from mlflow_tracking import log_training_run_to_mlflow
from mlops_registry import record_training_run
from notebook_sqlserver_loader import load_ml_dataset_from_sqlserver


PROJECT_DIR = Path(__file__).resolve().parent
MODELS_DIR = PROJECT_DIR / "models"
OUTPUTS_DIR = PROJECT_DIR / "outputs"

BASE_NUMERIC_FEATURES = [
    "critere_rang",
    "ponderation_num",
    "jour",
    "mois",
    "trimestre",
    "annee",
    "latitude",
    "longitude",
]

BASE_CATEGORICAL_FEATURES = [
    "role_utilisateur",
    "utilisateur",
    "filiale",
    "secteur",
]

OBJECTIF1_NUMERIC_FEATURES = BASE_NUMERIC_FEATURES
OBJECTIF1_CATEGORICAL_FEATURES = ["axe_evaluation", "criteres", *BASE_CATEGORICAL_FEATURES]
OBJECTIF2_NUMERIC_FEATURES = BASE_NUMERIC_FEATURES
OBJECTIF2_CATEGORICAL_FEATURES = ["axe_evaluation", "criteres", *BASE_CATEGORICAL_FEATURES]
OBJECTIF1_FEATURE_COLUMNS = [
    *OBJECTIF1_NUMERIC_FEATURES,
    *OBJECTIF1_CATEGORICAL_FEATURES,
]
OBJECTIF2_FEATURE_COLUMNS = [
    *OBJECTIF2_NUMERIC_FEATURES,
    *OBJECTIF2_CATEGORICAL_FEATURES,
]
ALL_NUMERIC_FEATURES = list(dict.fromkeys([*OBJECTIF1_NUMERIC_FEATURES, *OBJECTIF2_NUMERIC_FEATURES]))
ALL_CATEGORICAL_FEATURES = list(dict.fromkeys([*OBJECTIF1_CATEGORICAL_FEATURES, *OBJECTIF2_CATEGORICAL_FEATURES]))


@dataclass
class Objective1Result:
    comparison: pd.DataFrame
    best_model_name: str
    best_model: Pipeline
    base_rows: int
    augmented_rows: int
    class_distribution_before: dict[int, int]
    class_distribution_after: dict[int, int]
    mlflow_tracking: dict[str, Any] | None = None


@dataclass
class Objective2Result:
    comparison: pd.DataFrame
    best_model_name: str
    best_model: Pipeline
    base_rows: int
    augmented_rows: int
    mlflow_tracking: dict[str, Any] | None = None


def load_base_dataset(project_dir: Path | None = None, threshold: float = 16.0) -> pd.DataFrame:
    root = (project_dir or PROJECT_DIR).resolve()
    df = load_ml_dataset_from_sqlserver(project_dir=root, threshold=threshold).copy()
    return df


def build_objectif1_augmented_dataset(project_dir: Path | None = None) -> tuple[pd.DataFrame, pd.DataFrame]:
    df = load_base_dataset(project_dir, threshold=16.0)
    augmented = _mixed_smote_augment(
        df=df,
        target_col="non_conforme",
        numeric_cols=OBJECTIF1_NUMERIC_FEATURES,
        categorical_cols=OBJECTIF1_CATEGORICAL_FEATURES,
        random_state=42,
    )
    return df, augmented


def build_objectif2_augmented_dataset(project_dir: Path | None = None) -> tuple[pd.DataFrame, pd.DataFrame]:
    df = load_base_dataset(project_dir, threshold=16.0)
    augmented = _bootstrap_regression_augment(
        df=df,
        numeric_cols=OBJECTIF2_NUMERIC_FEATURES,
        target_col="note_num",
        multiplier=1.0,
        noise_scale=0.04,
        random_state=42,
    )
    return df, augmented


def _build_preprocessor(
    numeric_features: list[str],
    categorical_features: list[str],
) -> ColumnTransformer:
    return ColumnTransformer(
        transformers=[
            (
                "num",
                Pipeline(
                    steps=[
                        ("imputer", SimpleImputer(strategy="constant", fill_value=0.0, keep_empty_features=True)),
                        ("scaler", StandardScaler()),
                    ]
                ),
                numeric_features,
            ),
            (
                "cat",
                Pipeline(
                    steps=[
                        ("imputer", SimpleImputer(strategy="most_frequent")),
                        ("onehot", OneHotEncoder(handle_unknown="ignore", sparse_output=False)),
                    ]
                ),
                categorical_features,
            ),
        ]
    )


def _sanitize_feature_frame(
    frame: pd.DataFrame,
    numeric_features: list[str],
    categorical_features: list[str],
) -> pd.DataFrame:
    cleaned = frame.copy()

    for col in numeric_features:
        if col in cleaned.columns:
            cleaned[col] = pd.to_numeric(cleaned[col], errors="coerce")

    for col in categorical_features:
        if col in cleaned.columns:
            series = cleaned[col].astype("object")
            cleaned[col] = series.where(pd.notna(series), np.nan)

    return cleaned


def _mixed_smote_augment(
    df: pd.DataFrame,
    target_col: str,
    numeric_cols: list[str],
    categorical_cols: list[str],
    random_state: int = 42,
) -> pd.DataFrame:
    counts = df[target_col].value_counts()
    if len(counts) < 2:
        return df.copy()

    majority_class = counts.idxmax()
    minority_class = counts.idxmin()
    n_to_create = int(counts.max() - counts.min())
    if n_to_create <= 0:
        return df.copy()

    rng = np.random.default_rng(random_state)
    minority_df = df[df[target_col] == minority_class].reset_index(drop=True)
    synthetic_rows: list[dict[str, Any]] = []

    for synthetic_index in range(n_to_create):
        idx_a, idx_b = rng.integers(0, len(minority_df), size=2)
        row_a = minority_df.iloc[idx_a]
        row_b = minority_df.iloc[idx_b]
        lam = float(rng.random())
        synthetic: dict[str, Any] = {}

        for col in numeric_cols:
            a_val = row_a[col]
            b_val = row_b[col]
            if pd.isna(a_val) and pd.isna(b_val):
                synthetic[col] = np.nan
                continue
            if pd.isna(a_val):
                synthetic[col] = float(b_val)
                continue
            if pd.isna(b_val):
                synthetic[col] = float(a_val)
                continue
            synthetic[col] = float(a_val) + lam * (float(b_val) - float(a_val))

        for col in categorical_cols:
            synthetic[col] = row_a[col] if rng.random() < 0.5 else row_b[col]

        synthetic[target_col] = minority_class
        synthetic["audit_group"] = f"smote_{minority_class}_{synthetic_index}"
        synthetic["note_num"] = float(min(row_a.get("note_num", 15.0), row_b.get("note_num", 15.0)))
        synthetic["niveau_performance"] = "synthetique_smote"
        synthetic["pk_evaluation"] = -1
        synthetic["id_eval"] = -1
        synthetic_rows.append(synthetic)

    augmented = pd.concat([df, pd.DataFrame(synthetic_rows)], ignore_index=True, sort=False)

    int_like_cols = ["critere_rang", "jour", "mois", "trimestre", "annee"]
    for col in int_like_cols:
        if col in augmented.columns:
            augmented[col] = augmented[col].round().astype(int)

    if "ponderation_num" in augmented.columns:
        augmented["ponderation_num"] = augmented["ponderation_num"].clip(lower=0.0)

    if majority_class not in augmented[target_col].unique():
        raise RuntimeError("La classe majoritaire a disparu après SMOTE, ce qui est inattendu.")

    return augmented


def _bootstrap_regression_augment(
    df: pd.DataFrame,
    numeric_cols: list[str],
    target_col: str,
    multiplier: float = 1.0,
    noise_scale: float = 0.04,
    random_state: int = 42,
) -> pd.DataFrame:
    extra_count = int(len(df) * multiplier)
    if extra_count <= 0:
        return df.copy()

    rng = np.random.default_rng(random_state)
    sampled = df.sample(n=extra_count, replace=True, random_state=random_state).reset_index(drop=True).copy()

    for col in numeric_cols:
        if col not in sampled.columns or col == target_col:
            continue
        series = pd.to_numeric(sampled[col], errors="coerce")
        if int(series.notna().sum()) == 0:
            continue
        std = float(series.std(skipna=True) or 0.0)
        if std <= 0:
            continue
        noise = rng.normal(0.0, std * noise_scale, size=len(sampled))
        sampled[col] = (series.fillna(series.median()) + noise)

    sampled[target_col] = (
        pd.to_numeric(sampled[target_col], errors="coerce").fillna(df[target_col].median())
        + rng.normal(0.0, 0.35, size=len(sampled))
    ).clip(0.0, 20.0)
    sampled["audit_group"] = [f"boot_{index}" for index in range(len(sampled))]

    int_like_cols = ["critere_rang", "jour", "mois", "trimestre", "annee"]
    for col in int_like_cols:
        if col in sampled.columns:
            sampled[col] = sampled[col].round().astype(int)

    if "ponderation_num" in sampled.columns:
        sampled["ponderation_num"] = pd.to_numeric(sampled["ponderation_num"], errors="coerce").fillna(0.0).clip(lower=0.0)

    return pd.concat([df, sampled], ignore_index=True, sort=False)


def _classification_models() -> dict[str, Any]:
    return {
        "logistic_regression": LogisticRegression(max_iter=2000, class_weight="balanced", random_state=42),
        "random_forest": RandomForestClassifier(
            n_estimators=350,
            max_depth=10,
            min_samples_leaf=2,
            class_weight="balanced_subsample",
            random_state=42,
            n_jobs=-1,
        ),
        "gradient_boosting": GradientBoostingClassifier(
            n_estimators=220,
            learning_rate=0.05,
            max_depth=3,
            random_state=42,
        ),
        "svc_rbf": SVC(
            C=6.0,
            kernel="rbf",
            gamma=0.03,
            probability=True,
            class_weight="balanced",
            random_state=42,
        ),
    }


def _regression_models() -> dict[str, Any]:
    return {
        "ridge_regression": Ridge(alpha=1.0),
        "random_forest_regressor": RandomForestRegressor(
            n_estimators=400,
            max_depth=12,
            min_samples_leaf=2,
            random_state=42,
            n_jobs=-1,
        ),
        "gradient_boosting_regressor": GradientBoostingRegressor(
            n_estimators=240,
            learning_rate=0.05,
            max_depth=3,
            random_state=42,
        ),
        "extra_trees_regressor": ExtraTreesRegressor(
            n_estimators=350,
            max_depth=14,
            min_samples_leaf=2,
            random_state=42,
            n_jobs=-1,
        ),
    }


def train_objectif1(project_dir: Path | None = None, save_model: bool = True) -> Objective1Result:
    root = (project_dir or PROJECT_DIR).resolve()
    df = load_base_dataset(root, threshold=16.0)
    augmented = _mixed_smote_augment(
        df=df,
        target_col="non_conforme",
        numeric_cols=OBJECTIF1_NUMERIC_FEATURES,
        categorical_cols=OBJECTIF1_CATEGORICAL_FEATURES,
        random_state=42,
    )

    X = _sanitize_feature_frame(
        augmented[OBJECTIF1_FEATURE_COLUMNS].copy(),
        numeric_features=OBJECTIF1_NUMERIC_FEATURES,
        categorical_features=OBJECTIF1_CATEGORICAL_FEATURES,
    )
    y = augmented["non_conforme"].astype(int)
    preprocessor = _build_preprocessor(OBJECTIF1_NUMERIC_FEATURES, OBJECTIF1_CATEGORICAL_FEATURES)
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)

    scoring = {
        "accuracy": "accuracy",
        "balanced_accuracy": "balanced_accuracy",
        "precision": make_scorer(precision_score, zero_division=0),
        "recall": make_scorer(recall_score, zero_division=0),
        "f1": make_scorer(f1_score, zero_division=0),
        "roc_auc": "roc_auc",
    }

    rows: list[dict[str, Any]] = []
    trained_pipelines: dict[str, Pipeline] = {}
    for name, estimator in _classification_models().items():
        pipeline = Pipeline(
            steps=[
                ("preprocessor", preprocessor),
                ("classifier", estimator),
            ]
        )
        scores = cross_validate(pipeline, X, y, cv=cv, scoring=scoring, n_jobs=1)
        row = {"modele": name}
        for metric_name in scoring:
            row[metric_name] = float(np.mean(scores[f"test_{metric_name}"]))
        rows.append(row)
        trained_pipelines[name] = pipeline

    comparison = pd.DataFrame(rows).sort_values(["accuracy", "f1", "roc_auc"], ascending=False).reset_index(drop=True)
    best_model_name = str(comparison.iloc[0]["modele"])
    best_model = trained_pipelines[best_model_name]
    best_model.fit(X, y)

    if save_model:
        MODELS_DIR.mkdir(parents=True, exist_ok=True)
        OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
        joblib.dump(best_model, MODELS_DIR / "objectif1_non_conformite.joblib")
        comparison.to_csv(OUTPUTS_DIR / "objectif1_comparaison_modeles_augmented.csv", index=False)

    model_path = (MODELS_DIR / "objectif1_non_conformite.joblib") if save_model else None
    comparison_path = (OUTPUTS_DIR / "objectif1_comparaison_modeles_augmented.csv") if save_model else None

    mlops_payload = record_training_run(
        objective_name="objectif1_non_conformite",
        task_type="classification",
        comparison=comparison,
        best_model_name=best_model_name,
        model_path=model_path,
        base_rows=len(df),
        augmented_rows=len(augmented),
        training_config={
            "threshold_non_conformite": 16.0,
            "cross_validation": "StratifiedKFold(n_splits=5, shuffle=True, random_state=42)",
            "augmentation": "custom_smote_mixed_tabular",
            "numeric_features": OBJECTIF1_NUMERIC_FEATURES,
            "categorical_features": OBJECTIF1_CATEGORICAL_FEATURES,
        },
        data_summary={
            "class_distribution_before": df["non_conforme"].value_counts().sort_index().to_dict(),
            "class_distribution_after": augmented["non_conforme"].value_counts().sort_index().to_dict(),
        },
    )

    mlflow_tracking = log_training_run_to_mlflow(
        experiment_name="Poulina - Objectif 1 - Alerte non-conformite",
        run_name=f"objectif1-{best_model_name}-{mlops_payload['run_id']}",
        objective_name="objectif1_non_conformite",
        task_type="classification",
        best_model_name=best_model_name,
        comparison=comparison,
        training_payload=mlops_payload,
        model_path=model_path,
        comparison_path=comparison_path,
    )

    return Objective1Result(
        comparison=comparison,
        best_model_name=best_model_name,
        best_model=best_model,
        base_rows=len(df),
        augmented_rows=len(augmented),
        class_distribution_before=df["non_conforme"].value_counts().sort_index().to_dict(),
        class_distribution_after=augmented["non_conforme"].value_counts().sort_index().to_dict(),
        mlflow_tracking=mlflow_tracking,
    )


def train_objectif2(project_dir: Path | None = None, save_model: bool = True) -> Objective2Result:
    root = (project_dir or PROJECT_DIR).resolve()
    df = load_base_dataset(root, threshold=16.0)
    augmented = _bootstrap_regression_augment(
        df=df,
        numeric_cols=OBJECTIF2_NUMERIC_FEATURES,
        target_col="note_num",
        multiplier=1.0,
        noise_scale=0.04,
        random_state=42,
    )

    X = _sanitize_feature_frame(
        augmented[OBJECTIF2_FEATURE_COLUMNS].copy(),
        numeric_features=OBJECTIF2_NUMERIC_FEATURES,
        categorical_features=OBJECTIF2_CATEGORICAL_FEATURES,
    )
    y = augmented["note_num"].astype(float)
    preprocessor = _build_preprocessor(OBJECTIF2_NUMERIC_FEATURES, OBJECTIF2_CATEGORICAL_FEATURES)
    cv = KFold(n_splits=5, shuffle=True, random_state=42)

    scoring = {
        "neg_mae": "neg_mean_absolute_error",
        "neg_rmse": "neg_root_mean_squared_error",
        "r2": "r2",
    }

    rows: list[dict[str, Any]] = []
    trained_pipelines: dict[str, Pipeline] = {}
    for name, estimator in _regression_models().items():
        pipeline = Pipeline(
            steps=[
                ("preprocessor", preprocessor),
                ("regressor", estimator),
            ]
        )
        scores = cross_validate(pipeline, X, y, cv=cv, scoring=scoring, n_jobs=1)
        row = {
            "modele": name,
            "mae": float(-np.mean(scores["test_neg_mae"])),
            "rmse": float(-np.mean(scores["test_neg_rmse"])),
            "r2": float(np.mean(scores["test_r2"])),
        }
        rows.append(row)
        trained_pipelines[name] = pipeline

    comparison = pd.DataFrame(rows).sort_values(["r2", "mae"], ascending=[False, True]).reset_index(drop=True)
    best_model_name = str(comparison.iloc[0]["modele"])
    best_model = trained_pipelines[best_model_name]
    best_model.fit(X, y)

    if save_model:
        MODELS_DIR.mkdir(parents=True, exist_ok=True)
        OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
        joblib.dump(best_model, MODELS_DIR / "objectif2_note.joblib")
        comparison.to_csv(OUTPUTS_DIR / "objectif2_comparaison_modeles_augmented.csv", index=False)

    model_path = (MODELS_DIR / "objectif2_note.joblib") if save_model else None
    comparison_path = (OUTPUTS_DIR / "objectif2_comparaison_modeles_augmented.csv") if save_model else None

    mlops_payload = record_training_run(
        objective_name="objectif2_prediction_note",
        task_type="regression",
        comparison=comparison,
        best_model_name=best_model_name,
        model_path=model_path,
        base_rows=len(df),
        augmented_rows=len(augmented),
        training_config={
            "threshold_non_conformite_reference": 16.0,
            "cross_validation": "KFold(n_splits=5, shuffle=True, random_state=42)",
            "augmentation": "bootstrap_regression_with_noise",
            "numeric_features": OBJECTIF2_NUMERIC_FEATURES,
            "categorical_features": OBJECTIF2_CATEGORICAL_FEATURES,
        },
        data_summary={
            "target_note_min": float(df["note_num"].min()),
            "target_note_max": float(df["note_num"].max()),
            "target_note_mean": float(df["note_num"].mean()),
        },
    )

    mlflow_tracking = log_training_run_to_mlflow(
        experiment_name="Poulina - Objectif 2 - Prevision de note",
        run_name=f"objectif2-{best_model_name}-{mlops_payload['run_id']}",
        objective_name="objectif2_prediction_note",
        task_type="regression",
        best_model_name=best_model_name,
        comparison=comparison,
        training_payload=mlops_payload,
        model_path=model_path,
        comparison_path=comparison_path,
    )

    return Objective2Result(
        comparison=comparison,
        best_model_name=best_model_name,
        best_model=best_model,
        base_rows=len(df),
        augmented_rows=len(augmented),
        mlflow_tracking=mlflow_tracking,
    )


def prediction_smoke_test(model: Pipeline, sample_frame: pd.DataFrame) -> pd.Series:
    return pd.Series(
        model.predict(
            _sanitize_feature_frame(
                sample_frame.copy(),
                numeric_features=ALL_NUMERIC_FEATURES,
                categorical_features=ALL_CATEGORICAL_FEATURES,
            )
        )
    )
