from __future__ import annotations

from pathlib import Path
import os
from typing import Any
import warnings

import pandas as pd
import pyodbc


MONTH_TO_NUMBER = {
    "janvier": 1,
    "fevrier": 2,
    "fevrier": 2,
    "mars": 3,
    "avril": 4,
    "mai": 5,
    "juin": 6,
    "juillet": 7,
    "aout": 8,
    "septembre": 9,
    "octobre": 10,
    "novembre": 11,
    "decembre": 12,
}

DATASET_SQL = """
WITH evaluation_base AS (
    SELECT
        e.line_pk AS pk_evaluation,
        e.id AS id_eval,
        CAST(e.id AS varchar(100)) AS audit_group,
        ROW_NUMBER() OVER (PARTITION BY e.id ORDER BY e.line_pk) AS critere_rang,
        COALESCE(NULLIF(e.axe_evaluation, ''), 'Sans axe') AS axe_evaluation,
        COALESCE(NULLIF(e.criteres, ''), 'Sans critere') AS criteres,
        TRY_CONVERT(float, REPLACE(NULLIF(e.note, ''), ',', '.')) AS note_num,
        TRY_CONVERT(float, REPLACE(NULLIF(e.ponderation, ''), ',', '.')) AS ponderation_num,
        d.mois AS mois_label,
        d.trimestre AS trimestre_label,
        TRY_CONVERT(int, d.annee) AS annee,
        COALESCE(NULLIF(u.role, ''), 'user') AS role_utilisateur,
        LTRIM(RTRIM(COALESCE(NULLIF(u.first_name, ''), '') + ' ' + COALESCE(NULLIF(u.last_name, ''), ''))) AS utilisateur_nom,
        u.email AS utilisateur_email,
        COALESCE(NULLIF(e.filiale_name, ''), b.name) AS filiale,
        s.name AS secteur
    FROM user_evaluation e
    LEFT JOIN user_datedim d ON e.date_id = d.id
    LEFT JOIN user_user u ON e.user_id = u.id
    LEFT JOIN user_branch b ON e.filiale_id = b.id
    LEFT JOIN user_sector s ON COALESCE(b.sector_id, u.sector_id) = s.id
)
SELECT
    pk_evaluation,
    id_eval,
    audit_group,
    critere_rang,
    axe_evaluation,
    criteres,
    note_num,
    ponderation_num,
    mois_label,
    trimestre_label,
    annee,
    role_utilisateur,
    utilisateur_nom,
    utilisateur_email,
    filiale,
    secteur
FROM evaluation_base
WHERE note_num IS NOT NULL
ORDER BY id_eval, critere_rang
"""


def _load_env_file(path: Path) -> None:
    if not path.exists():
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def _project_root(project_dir: Path | None = None) -> Path:
    return (project_dir or Path.cwd()).resolve()


def _load_notebook_env(project_dir: Path | None = None) -> None:
    root = _project_root(project_dir)
    _load_env_file(root / "stage" / ".env")


def _bool_env(name: str, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _month_to_number(value: Any) -> int:
    text = str(value or "").strip().lower()
    if text.isdigit():
        month_num = int(text)
        return month_num if 1 <= month_num <= 12 else 1
    return MONTH_TO_NUMBER.get(text, 1)


def _trimestre_from_value(value: Any, month_number: int) -> int:
    text = str(value or "").strip().upper()
    if text.startswith("T") and text[1:].isdigit():
        return int(text[1:])
    if text.isdigit():
        return int(text)
    return ((month_number - 1) // 3) + 1


def _performance_label(note: float) -> str:
    if note >= 18:
        return "eleve"
    if note >= 16:
        return "conforme"
    if note >= 10:
        return "moyen"
    return "faible"


def build_sqlserver_connection_string(project_dir: Path | None = None) -> str:
    _load_notebook_env(project_dir)

    driver = os.environ.get("MSSQL_DRIVER", "ODBC Driver 18 for SQL Server").strip() or "ODBC Driver 18 for SQL Server"
    host = os.environ.get("MSSQL_HOST", r"HEDIRE\MSSQLSERVER05").strip() or r"HEDIRE\MSSQLSERVER05"
    port = os.environ.get("MSSQL_PORT", "1433").strip()
    database = os.environ.get("MSSQL_NAME", "stage_db").strip() or "stage_db"
    user = os.environ.get("MSSQL_USER", "").strip()
    password = os.environ.get("MSSQL_PASSWORD", "").strip()
    encrypt = os.environ.get("MSSQL_ENCRYPT", "yes").strip() or "yes"
    trust_cert = os.environ.get("MSSQL_TRUST_SERVER_CERTIFICATE", "yes").strip() or "yes"
    trusted_connection = _bool_env("MSSQL_TRUSTED_CONNECTION", True)

    server = host
    if port and "\\" not in host and "," not in host:
        server = f"{host},{port}"

    parts = [
        f"DRIVER={{{driver}}}",
        f"SERVER={server}",
        f"DATABASE={database}",
        f"Encrypt={encrypt}",
        f"TrustServerCertificate={trust_cert}",
    ]

    if trusted_connection and not user:
        parts.append("Trusted_Connection=yes")
    else:
        parts.append(f"UID={user}")
        parts.append(f"PWD={password}")

    return ";".join(parts)


def get_sqlserver_connection(project_dir: Path | None = None) -> pyodbc.Connection:
    connection_string = build_sqlserver_connection_string(project_dir)
    return pyodbc.connect(connection_string)


def load_ml_dataset_from_sqlserver(project_dir: Path | None = None, threshold: float = 16.0) -> pd.DataFrame:
    with get_sqlserver_connection(project_dir) as connection:
        with warnings.catch_warnings():
            warnings.filterwarnings(
                "ignore",
                message="pandas only supports SQLAlchemy connectable",
                category=UserWarning,
            )
            df = pd.read_sql(DATASET_SQL, connection)

    if df.empty:
        raise RuntimeError("Aucune ligne exploitable n'a ete trouvee dans SQL Server.")

    df["mois"] = df["mois_label"].map(_month_to_number).astype(int)
    df["trimestre"] = [
        _trimestre_from_value(trimestre, mois)
        for trimestre, mois in zip(df["trimestre_label"], df["mois"])
    ]
    df["jour"] = 1
    df["annee"] = pd.to_numeric(df["annee"], errors="coerce").fillna(2026).astype(int)
    df["ponderation_num"] = pd.to_numeric(df["ponderation_num"], errors="coerce").fillna(0.0)
    df["note_num"] = pd.to_numeric(df["note_num"], errors="coerce")
    df = df.dropna(subset=["note_num"]).copy()
    df["utilisateur"] = df["utilisateur_nom"].fillna("").str.strip()
    df.loc[df["utilisateur"] == "", "utilisateur"] = df.loc[df["utilisateur"] == "", "utilisateur_email"].fillna("")
    df["filiale"] = df["filiale"].fillna("")
    df["secteur"] = df["secteur"].fillna("")
    df["role_utilisateur"] = df["role_utilisateur"].fillna("user")
    df["latitude"] = pd.NA
    df["longitude"] = pd.NA
    df["non_conforme"] = (df["note_num"] < threshold).astype(int)
    df["niveau_performance"] = df["note_num"].map(_performance_label)

    ordered_columns = [
        "pk_evaluation",
        "id_eval",
        "audit_group",
        "critere_rang",
        "axe_evaluation",
        "criteres",
        "note_num",
        "ponderation_num",
        "non_conforme",
        "niveau_performance",
        "jour",
        "mois",
        "trimestre",
        "annee",
        "role_utilisateur",
        "utilisateur",
        "filiale",
        "secteur",
        "latitude",
        "longitude",
    ]
    return df[ordered_columns].copy()
