from __future__ import annotations

from pathlib import Path
import json

import joblib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    ConfusionMatrixDisplay,
    accuracy_score,
    balanced_accuracy_score,
    f1_score,
    make_scorer,
    precision_score,
    recall_score,
)
from sklearn.model_selection import StratifiedGroupKFold, cross_val_predict, cross_validate
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUTS_DIR = PROJECT_DIR / "outputs"
MODELS_DIR = PROJECT_DIR / "models"
THRESHOLD = 16.0


def load_dataset() -> pd.DataFrame:
    dataset_path = OUTPUTS_DIR / "poulina_dw_dataset.csv"
    df = pd.read_csv(dataset_path)
    df["non_conforme"] = (df["note_num"] < THRESHOLD).astype(int)
    df.to_csv(dataset_path, index=False)
    return df


def build_preprocessor() -> ColumnTransformer:
    numeric_features = [
        "critere_rang",
        "ponderation_num",
        "jour",
        "mois",
        "trimestre",
        "annee",
        "latitude",
        "longitude",
    ]
    categorical_features = [
        "role_utilisateur",
        "utilisateur",
        "filiale",
        "secteur",
    ]

    return ColumnTransformer(
        transformers=[
            (
                "num",
                Pipeline(
                    steps=[
                        ("imputer", SimpleImputer(strategy="median")),
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


def build_models() -> dict[str, Pipeline]:
    preprocessor = build_preprocessor()
    return {
        "baseline_dummy": Pipeline(
            steps=[
                ("preprocessor", preprocessor),
                ("model", DummyClassifier(strategy="prior")),
            ]
        ),
        "logistic_regression": Pipeline(
            steps=[
                ("preprocessor", preprocessor),
                ("model", LogisticRegression(max_iter=2000, class_weight="balanced", random_state=42)),
            ]
        ),
        "random_forest_classifier": Pipeline(
            steps=[
                ("preprocessor", preprocessor),
                (
                    "model",
                    RandomForestClassifier(
                        n_estimators=300,
                        min_samples_leaf=2,
                        class_weight="balanced",
                        random_state=42,
                    ),
                ),
            ]
        ),
        "gradient_boosting_classifier": Pipeline(
            steps=[
                ("preprocessor", preprocessor),
                ("model", GradientBoostingClassifier(random_state=42)),
            ]
        ),
    }


def get_feature_names(preprocessor: ColumnTransformer) -> list[str]:
    return list(preprocessor.get_feature_names_out())


def save_feature_importance(model_pipeline: Pipeline) -> None:
    preprocessor = model_pipeline.named_steps["preprocessor"]
    model = model_pipeline.named_steps["model"]
    feature_names = get_feature_names(preprocessor)

    if hasattr(model, "feature_importances_"):
        importances = model.feature_importances_
    elif hasattr(model, "coef_"):
        coef = model.coef_
        importances = np.mean(np.abs(coef), axis=0) if coef.ndim == 2 else np.abs(coef)
    else:
        return

    (
        pd.DataFrame({"feature": feature_names, "importance": importances})
        .sort_values("importance", ascending=False)
        .head(15)
        .to_csv(OUTPUTS_DIR / "objectif1_feature_importance.csv", index=False)
    )


def dataframe_to_markdown(df: pd.DataFrame) -> str:
    display_df = df.copy()
    for column in display_df.columns:
        if pd.api.types.is_float_dtype(display_df[column]):
            display_df[column] = display_df[column].map(lambda x: f"{x:.3f}")
    headers = [str(col) for col in display_df.columns]
    separator = ["---"] * len(headers)
    lines = ["| " + " | ".join(headers) + " |", "| " + " | ".join(separator) + " |"]
    for _, row in display_df.iterrows():
        lines.append("| " + " | ".join(str(value) for value in row.tolist()) + " |")
    return "\n".join(lines)


def build_report(df: pd.DataFrame, results: pd.DataFrame, best_model_name: str, metrics: dict[str, float]) -> str:
    top_filiales = (
        df.groupby(["secteur", "filiale"])
        .agg(
            note_moyenne=("note_num", "mean"),
            taux_non_conformite=("non_conforme", "mean"),
            volume=("pk_evaluation", "count"),
        )
        .sort_values(by=["taux_non_conformite", "note_moyenne"], ascending=[False, True])
        .reset_index()
    )

    results_md = dataframe_to_markdown(results)
    filiales_md = dataframe_to_markdown(top_filiales)

    return f"""# Analyse DS - poulina_DW

## Objectif 1 corrige

Le seuil de non-conformite a ete corrige selon votre regle metier:

- **non conforme si `note < 16`**

## Comparaison des modeles - Objectif 1

{results_md}

**Modele retenu:** `{best_model_name}`

Metriques en prediction croisee:
- Accuracy: **{metrics['accuracy']:.3f}**
- Balanced accuracy: **{metrics['balanced_accuracy']:.3f}**
- Precision: **{metrics['precision']:.3f}**
- Recall: **{metrics['recall']:.3f}**
- F1: **{metrics['f1']:.3f}**

## Lecture rapide par filiale

{filiales_md}

## Remarque

Le DSO 2 reste inchange. Seul l'objectif de classification a ete recalcule avec le nouveau seuil `16`.
"""


def main() -> None:
    df = load_dataset()
    feature_columns = [
        "critere_rang",
        "ponderation_num",
        "jour",
        "mois",
        "trimestre",
        "annee",
        "latitude",
        "longitude",
        "role_utilisateur",
        "utilisateur",
        "filiale",
        "secteur",
    ]
    X = df[feature_columns]
    y = df["non_conforme"]
    groups = df["audit_group"]

    scoring = {
        "accuracy": "accuracy",
        "balanced_accuracy": "balanced_accuracy",
        "precision": make_scorer(precision_score, zero_division=0),
        "recall": make_scorer(recall_score, zero_division=0),
        "f1": make_scorer(f1_score, zero_division=0),
        "roc_auc": "roc_auc",
    }

    cv = StratifiedGroupKFold(n_splits=4, shuffle=True, random_state=42)
    rows: list[dict[str, float | str]] = []
    models = build_models()

    for model_name, pipeline in models.items():
        scores = cross_validate(
            pipeline,
            X,
            y,
            cv=cv,
            groups=groups,
            scoring=scoring,
            n_jobs=-1,
            error_score="raise",
        )
        row: dict[str, float | str] = {"modele": model_name}
        for metric in scoring:
            row[f"{metric}_mean"] = float(np.mean(scores[f"test_{metric}"]))
            row[f"{metric}_std"] = float(np.std(scores[f"test_{metric}"]))
        rows.append(row)

    results = pd.DataFrame(rows).sort_values(
        by=["f1_mean", "recall_mean", "balanced_accuracy_mean"],
        ascending=False,
    )
    results.to_csv(OUTPUTS_DIR / "objectif1_comparaison_modeles.csv", index=False)

    best_model_name = str(results.iloc[0]["modele"])
    best_model = models[best_model_name]
    predictions = cross_val_predict(
        best_model,
        X,
        y,
        cv=cv,
        groups=groups,
        method="predict",
        n_jobs=-1,
    )

    metrics = {
        "accuracy": float(accuracy_score(y, predictions)),
        "balanced_accuracy": float(balanced_accuracy_score(y, predictions)),
        "precision": float(precision_score(y, predictions, zero_division=0)),
        "recall": float(recall_score(y, predictions, zero_division=0)),
        "f1": float(f1_score(y, predictions, zero_division=0)),
    }

    fig, ax = plt.subplots(figsize=(6, 5))
    ConfusionMatrixDisplay.from_predictions(y, predictions, ax=ax, colorbar=False)
    ax.set_title("Objectif 1 - Matrice de confusion (seuil < 16)")
    fig.tight_layout()
    fig.savefig(OUTPUTS_DIR / "objectif1_confusion_matrix.png", dpi=160)
    plt.close(fig)

    best_model.fit(X, y)
    joblib.dump(best_model, MODELS_DIR / "objectif1_non_conformite.joblib")
    save_feature_importance(best_model)

    report = build_report(df, results, best_model_name, metrics)
    (OUTPUTS_DIR / "rapport_ds_poulina.md").write_text(report, encoding="utf-8")

    summary_path = OUTPUTS_DIR / "run_summary.json"
    summary = {}
    if summary_path.exists():
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
    summary["objectif1_threshold"] = 16
    summary["best_classification_model"] = best_model_name
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print(json.dumps({"best_model": best_model_name, "threshold": 16, **metrics}, indent=2))


if __name__ == "__main__":
    main()
