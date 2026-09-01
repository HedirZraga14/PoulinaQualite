from __future__ import annotations

import json
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parent


def to_source(text: str) -> list[str]:
    return [line + "\n" for line in text.strip("\n").splitlines()]


def markdown_cell(text: str) -> dict:
    return {"cell_type": "markdown", "metadata": {}, "source": to_source(text)}


def code_cell(text: str) -> dict:
    return {
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": to_source(text),
    }


def notebook_metadata() -> dict:
    return {
        "kernelspec": {
            "display_name": "Python 3",
            "language": "python",
            "name": "python3",
        },
        "language_info": {
            "name": "python",
            "version": "3.13",
        },
    }


def objectif1_ml_code() -> str:
    return """
from pathlib import Path
from typing import Any

import joblib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import f1_score, make_scorer, precision_score, recall_score
from sklearn.model_selection import StratifiedKFold, cross_validate
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.svm import SVC

from notebook_sqlserver_loader import get_sqlserver_connection, load_ml_dataset_from_sqlserver


PROJECT_DIR = Path.cwd()
MODELS_DIR = PROJECT_DIR / "models"
OUTPUTS_DIR = PROJECT_DIR / "outputs"
MODELS_DIR.mkdir(exist_ok=True)
OUTPUTS_DIR.mkdir(exist_ok=True)

OBJECTIF1_NUMERIC_FEATURES = [
    "critere_rang",
    "ponderation_num",
    "jour",
    "mois",
    "trimestre",
    "annee",
    "latitude",
    "longitude",
]

OBJECTIF1_CATEGORICAL_FEATURES = [
    "role_utilisateur",
    "utilisateur",
    "filiale",
    "secteur",
]

OBJECTIF1_FEATURE_COLUMNS = [
    *OBJECTIF1_NUMERIC_FEATURES,
    *OBJECTIF1_CATEGORICAL_FEATURES,
]


def load_base_dataset(project_dir: Path | None = None, threshold: float = 16.0) -> pd.DataFrame:
    root = (project_dir or PROJECT_DIR).resolve()
    return load_ml_dataset_from_sqlserver(project_dir=root, threshold=threshold).copy()


def _build_preprocessor(numeric_features: list[str], categorical_features: list[str]) -> ColumnTransformer:
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

    for col in ["critere_rang", "jour", "mois", "trimestre", "annee"]:
        if col in augmented.columns:
            augmented[col] = augmented[col].round().astype(int)

    if "ponderation_num" in augmented.columns:
        augmented["ponderation_num"] = augmented["ponderation_num"].clip(lower=0.0)

    if majority_class not in augmented[target_col].unique():
        raise RuntimeError("La classe majoritaire a disparu apres SMOTE, ce qui est inattendu.")

    return augmented


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


def train_objectif1(project_dir: Path | None = None, save_model: bool = True) -> dict[str, Any]:
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
        joblib.dump(best_model, MODELS_DIR / "objectif1_non_conformite.joblib")
        comparison.to_csv(OUTPUTS_DIR / "objectif1_comparaison_modeles_augmented.csv", index=False)

    return {
        "comparison": comparison,
        "best_model_name": best_model_name,
        "best_model": best_model,
        "base_rows": len(df),
        "augmented_rows": len(augmented),
        "class_distribution_before": df["non_conforme"].value_counts().sort_index().to_dict(),
        "class_distribution_after": augmented["non_conforme"].value_counts().sort_index().to_dict(),
    }


def prediction_smoke_test(model: Pipeline, sample_frame: pd.DataFrame) -> pd.Series:
    return pd.Series(
        model.predict(
            _sanitize_feature_frame(
                sample_frame[OBJECTIF1_FEATURE_COLUMNS].copy(),
                numeric_features=OBJECTIF1_NUMERIC_FEATURES,
                categorical_features=OBJECTIF1_CATEGORICAL_FEATURES,
            )
        )
    )


with get_sqlserver_connection(PROJECT_DIR) as connection:
    cursor = connection.cursor()
    cursor.execute("SELECT DB_NAME(), @@SERVERNAME")
    print("Connexion active vers :", cursor.fetchone())
"""


def objectif2_ml_code() -> str:
    return """
from pathlib import Path
from typing import Any

import joblib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import ExtraTreesRegressor, GradientBoostingRegressor, RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.model_selection import KFold, cross_validate
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from notebook_sqlserver_loader import get_sqlserver_connection, load_ml_dataset_from_sqlserver


PROJECT_DIR = Path.cwd()
MODELS_DIR = PROJECT_DIR / "models"
OUTPUTS_DIR = PROJECT_DIR / "outputs"
MODELS_DIR.mkdir(exist_ok=True)
OUTPUTS_DIR.mkdir(exist_ok=True)

OBJECTIF2_NUMERIC_FEATURES = [
    "critere_rang",
    "ponderation_num",
    "jour",
    "mois",
    "trimestre",
    "annee",
    "latitude",
    "longitude",
]

OBJECTIF2_CATEGORICAL_FEATURES = [
    "axe_evaluation",
    "criteres",
    "role_utilisateur",
    "utilisateur",
    "filiale",
    "secteur",
]

OBJECTIF2_FEATURE_COLUMNS = [
    *OBJECTIF2_NUMERIC_FEATURES,
    *OBJECTIF2_CATEGORICAL_FEATURES,
]


def load_base_dataset(project_dir: Path | None = None, threshold: float = 16.0) -> pd.DataFrame:
    root = (project_dir or PROJECT_DIR).resolve()
    return load_ml_dataset_from_sqlserver(project_dir=root, threshold=threshold).copy()


def _build_preprocessor(numeric_features: list[str], categorical_features: list[str]) -> ColumnTransformer:
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

    for col in ["critere_rang", "jour", "mois", "trimestre", "annee"]:
        if col in sampled.columns:
            sampled[col] = sampled[col].round().astype(int)

    if "ponderation_num" in sampled.columns:
        sampled["ponderation_num"] = pd.to_numeric(sampled["ponderation_num"], errors="coerce").fillna(0.0).clip(lower=0.0)

    return pd.concat([df, sampled], ignore_index=True, sort=False)


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


def train_objectif2(project_dir: Path | None = None, save_model: bool = True) -> dict[str, Any]:
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
        rows.append(
            {
                "modele": name,
                "mae": float(-np.mean(scores["test_neg_mae"])),
                "rmse": float(-np.mean(scores["test_neg_rmse"])),
                "r2": float(np.mean(scores["test_r2"])),
            }
        )
        trained_pipelines[name] = pipeline

    comparison = pd.DataFrame(rows).sort_values(["r2", "mae"], ascending=[False, True]).reset_index(drop=True)
    best_model_name = str(comparison.iloc[0]["modele"])
    best_model = trained_pipelines[best_model_name]
    best_model.fit(X, y)

    if save_model:
        joblib.dump(best_model, MODELS_DIR / "objectif2_note.joblib")
        comparison.to_csv(OUTPUTS_DIR / "objectif2_comparaison_modeles_augmented.csv", index=False)

    return {
        "comparison": comparison,
        "best_model_name": best_model_name,
        "best_model": best_model,
        "base_rows": len(df),
        "augmented_rows": len(augmented),
    }


def prediction_smoke_test(model: Pipeline, sample_frame: pd.DataFrame) -> pd.Series:
    return pd.Series(
        model.predict(
            _sanitize_feature_frame(
                sample_frame[OBJECTIF2_FEATURE_COLUMNS].copy(),
                numeric_features=OBJECTIF2_NUMERIC_FEATURES,
                categorical_features=OBJECTIF2_CATEGORICAL_FEATURES,
            )
        )
    )


with get_sqlserver_connection(PROJECT_DIR) as connection:
    cursor = connection.cursor()
    cursor.execute("SELECT DB_NAME(), @@SERVERNAME")
    print("Connexion active vers :", cursor.fetchone())
"""


def build_objectif1_notebook() -> dict:
    cells = [
        markdown_cell(
            """
# Objectif 1 - Prediction de la non-conformite

- **Type d'apprentissage** : classification supervisee binaire
- **Cible** : `non_conforme` avec la regle `note < 16`
- **Algorithmes utilises** :
  - `logistic_regression`
  - `random_forest`
  - `gradient_boosting`
  - `svc_rbf`
- **Technique d'augmentation** : SMOTE tabulaire maison

Ce notebook contient directement les fonctions ML, le code des algorithmes, la phase d'entrainement, la comparaison des modeles et la sauvegarde du meilleur modele.
"""
        ),
        code_cell(
            """
import sys
from pathlib import Path

print(f"Python executable: {sys.executable}")
print(f"Python version: {sys.version}")
print(f"Working directory: {Path.cwd()}")
"""
        ),
        code_cell(
            """
%pip install pandas matplotlib seaborn scikit-learn joblib pyodbc
"""
        ),
        markdown_cell(
            """
## 1. Fonctions ML et code des algorithmes
"""
        ),
        code_cell(objectif1_ml_code()),
        markdown_cell(
            """
## 2. Chargement des donnees depuis SQL Server
"""
        ),
        code_cell(
            """
df_base, df_aug = build_objectif1_augmented_dataset(PROJECT_DIR)

print("Shape base :", df_base.shape)
print("Shape apres augmentation + SMOTE :", df_aug.shape)
print("Distribution avant :", df_base["non_conforme"].value_counts().sort_index().to_dict())
print("Distribution apres :", df_aug["non_conforme"].value_counts().sort_index().to_dict())

display(df_base.head())
"""
        ),
        markdown_cell(
            """
## 3. Visualisation de l'equilibrage des classes
"""
        ),
        code_cell(
            """
before_counts = df_base["non_conforme"].value_counts().sort_index().rename(index={0: "Conforme", 1: "Non conforme"})
after_counts = df_aug["non_conforme"].value_counts().sort_index().rename(index={0: "Conforme", 1: "Non conforme"})

fig, axes = plt.subplots(1, 2, figsize=(12, 4))
sns.barplot(x=before_counts.index, y=before_counts.values, ax=axes[0], palette="Blues_d")
axes[0].set_title("Avant data augmentation")
axes[0].set_ylabel("Nombre de lignes")

sns.barplot(x=after_counts.index, y=after_counts.values, ax=axes[1], palette="Greens_d")
axes[1].set_title("Apres SMOTE tabulaire")
axes[1].set_ylabel("Nombre de lignes")

plt.tight_layout()
plt.show()
"""
        ),
        markdown_cell(
            """
## 4. Entrainement, comparaison des modeles et sauvegarde
"""
        ),
        code_cell(
            """
result_obj1 = train_objectif1(project_dir=PROJECT_DIR, save_model=True)
comparison_obj1 = result_obj1["comparison"].copy()

display(comparison_obj1.round(4))
"""
        ),
        code_cell(
            """
best_model_path = MODELS_DIR / "objectif1_non_conformite.joblib"
best_model = joblib.load(best_model_path)

print("Meilleur modele :", result_obj1["best_model_name"])
print("Modele sauvegarde dans :", best_model_path)
print(comparison_obj1.round(4))
"""
        ),
        markdown_cell(
            """
## 4.1 Visualisation comparative des algorithmes
"""
        ),
        code_cell(
            """
fig, axes = plt.subplots(1, 3, figsize=(18, 4))

sns.barplot(data=comparison_obj1, x="modele", y="accuracy", ax=axes[0], palette="Blues_d")
axes[0].set_title("Comparaison Accuracy")
axes[0].tick_params(axis="x", rotation=20)

sns.barplot(data=comparison_obj1, x="modele", y="f1", ax=axes[1], palette="Greens_d")
axes[1].set_title("Comparaison F1")
axes[1].tick_params(axis="x", rotation=20)

sns.barplot(data=comparison_obj1, x="modele", y="roc_auc", ax=axes[2], palette="Oranges_d")
axes[2].set_title("Comparaison ROC AUC")
axes[2].tick_params(axis="x", rotation=20)

plt.tight_layout()
plt.show()
"""
        ),
        markdown_cell(
            """
## 5. Test rapide du modele deploye
"""
        ),
        code_cell(
            """
sample_predictions = prediction_smoke_test(best_model, df_base.head(5))
pd.DataFrame(
    {
        "critere_rang": df_base.head(5)["critere_rang"].tolist(),
        "filiale": df_base.head(5)["filiale"].tolist(),
        "note_reelle": df_base.head(5)["note_num"].tolist(),
        "prediction_non_conforme": sample_predictions.tolist(),
    }
)
"""
        ),
    ]
    return {
        "cells": cells,
        "metadata": notebook_metadata(),
        "nbformat": 4,
        "nbformat_minor": 5,
    }


def build_objectif2_notebook() -> dict:
    cells = [
        markdown_cell(
            """
# Objectif 2 - Prediction de la note

- **Type d'apprentissage** : regression supervisee
- **Cible** : `note_num` sur 20
- **Algorithmes utilises** :
  - `ridge_regression`
  - `random_forest_regressor`
  - `gradient_boosting_regressor`
  - `extra_trees_regressor`
- **Technique d'augmentation** : bootstrap controle avec bruit gaussien

Ce notebook contient directement les fonctions ML, le code des algorithmes, la phase d'entrainement, la comparaison des modeles et la sauvegarde du meilleur modele.
"""
        ),
        code_cell(
            """
import sys
from pathlib import Path

print(f"Python executable: {sys.executable}")
print(f"Python version: {sys.version}")
print(f"Working directory: {Path.cwd()}")
"""
        ),
        code_cell(
            """
%pip install pandas matplotlib seaborn scikit-learn joblib pyodbc
"""
        ),
        markdown_cell(
            """
## 1. Fonctions ML et code des algorithmes
"""
        ),
        code_cell(objectif2_ml_code()),
        markdown_cell(
            """
## 2. Chargement des donnees depuis SQL Server
"""
        ),
        code_cell(
            """
df_base, df_aug = build_objectif2_augmented_dataset(PROJECT_DIR)

print("Shape base :", df_base.shape)
print("Shape apres data augmentation :", df_aug.shape)
print("Statistiques note avant :")
print(df_base["note_num"].describe().round(3))
print("Statistiques note apres :")
print(df_aug["note_num"].describe().round(3))

display(df_base.head())
"""
        ),
        markdown_cell(
            """
## 3. Visualisation de la distribution des notes
"""
        ),
        code_cell(
            """
fig, axes = plt.subplots(1, 2, figsize=(12, 4))
sns.histplot(df_base["note_num"], kde=True, ax=axes[0], color="#2563eb")
axes[0].set_title("Distribution initiale des notes")

sns.histplot(df_aug["note_num"], kde=True, ax=axes[1], color="#059669")
axes[1].set_title("Distribution apres bootstrap")

plt.tight_layout()
plt.show()
"""
        ),
        markdown_cell(
            """
## 4. Entrainement, comparaison des modeles et sauvegarde
"""
        ),
        code_cell(
            """
result_obj2 = train_objectif2(project_dir=PROJECT_DIR, save_model=True)
comparison_obj2 = result_obj2["comparison"].copy()
comparison_obj2 = comparison_obj2.assign(
    rang_global=range(1, len(comparison_obj2) + 1)
)[["rang_global", "modele", "mae", "rmse", "r2"]]

display(comparison_obj2.round(4))
"""
        ),
        code_cell(
            """
best_model_path = MODELS_DIR / "objectif2_note.joblib"
best_model = joblib.load(best_model_path)

print("Meilleur modele :", result_obj2["best_model_name"])
print("Modele sauvegarde dans :", best_model_path)
print(comparison_obj2.round(4))
"""
        ),
        markdown_cell(
            """
## 4.1 Visualisation comparative des algorithmes
"""
        ),
        code_cell(
            """
fig, axes = plt.subplots(1, 3, figsize=(18, 4))

sns.barplot(data=comparison_obj2, x="modele", y="mae", ax=axes[0], palette="Blues_d")
axes[0].set_title("Comparaison MAE")
axes[0].tick_params(axis="x", rotation=20)

sns.barplot(data=comparison_obj2, x="modele", y="rmse", ax=axes[1], palette="Greens_d")
axes[1].set_title("Comparaison RMSE")
axes[1].tick_params(axis="x", rotation=20)

sns.barplot(data=comparison_obj2, x="modele", y="r2", ax=axes[2], palette="Oranges_d")
axes[2].set_title("Comparaison R2")
axes[2].tick_params(axis="x", rotation=20)

plt.tight_layout()
plt.show()
"""
        ),
        markdown_cell(
            """
## 5. Test rapide du modele deploye
"""
        ),
        code_cell(
            """
sample_predictions = prediction_smoke_test(best_model, df_base.head(5))
pd.DataFrame(
    {
        "critere_rang": df_base.head(5)["critere_rang"].tolist(),
        "filiale": df_base.head(5)["filiale"].tolist(),
        "note_reelle": df_base.head(5)["note_num"].tolist(),
        "note_predite": sample_predictions.round(2).tolist(),
    }
)
"""
        ),
    ]
    return {
        "cells": cells,
        "metadata": notebook_metadata(),
        "nbformat": 4,
        "nbformat_minor": 5,
    }


def write_notebook(path: Path, notebook: dict) -> None:
    path.write_text(json.dumps(notebook, ensure_ascii=False, indent=1), encoding="utf-8")


def main() -> None:
    write_notebook(PROJECT_DIR / "notbook_obj1.ipynb", build_objectif1_notebook())
    write_notebook(PROJECT_DIR / "notbook_obj2.ipynb", build_objectif2_notebook())
    print("Notebooks generes :", PROJECT_DIR / "notbook_obj1.ipynb", "et", PROJECT_DIR / "notbook_obj2.ipynb")


if __name__ == "__main__":
    main()
