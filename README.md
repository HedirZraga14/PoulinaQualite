# Documentation du projet Poulina

Ce dépôt regroupe une application de pilotage qualité construite autour de deux grands blocs :

- un backend Django pour la gestion métier, l'authentification, les évaluations et l'exposition des API ;
- un frontend Angular pour l'interface utilisateur, les espaces administrateur, les écrans d'évaluation et les vues IA/MLOps.

Le projet intègre également :

- un pipeline de machine learning pour la détection de non-conformité et la prévision de note ;
- une couche MLOps basée sur un registre de modèles local, des historiques de runs et MLflow ;
- une stack d'observabilité Docker avec Prometheus et Grafana.


## Structure principale

```text
ML_poulina/
├── stage/                         # Application Django + frontend Angular
│   ├── stage_project/             # Configuration Django
│   ├── user/                      # App principale métier et API
│   └── frontend/                  # Frontend Angular
├── models/                        # Modèles ML sérialisés (.joblib)
├── outputs/                       # Sorties d'entraînement, comparaisons, registre MLOps
├── monitoring/                    # Docker Compose Prometheus / Grafana / MLflow
├── ml_augmented_training.py       # Entraînement ML des 2 objectifs
├── mlops_registry.py              # Registre MLOps local
├── mlflow_tracking.py             # Pont de tracking MLflow
├── run_mlops_pipeline.py          # Pipeline d'entraînement complet
└── notebook_sqlserver_loader.py   # Chargement dataset depuis SQL Server
```

## Objectifs fonctionnels

Le projet couvre deux objectifs ML :

1. `Objectif 1` : alerte de non-conformité.
2. `Objectif 2` : prévision de note.

Et plusieurs besoins métier hors ML :

- gestion des utilisateurs, secteurs, filiales et laboratoires ;
- saisie et consultation des évaluations qualité ;
- tableaux de bord administrateur ;
- intégration Power BI ;
- page "Améliorer" pour le suivi IA, MLOps et monitoring.

## Démarrage rapide

### Backend Django

```powershell
cd "c:\Users\hedir\OneDrive\Desktop\ML_poulina\stage"
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

### Frontend Angular

```powershell
cd "\ML_poulina\stage\frontend"
npm install
npm start
```

### Pipeline ML + MLOps

```powershell
cd "\ML_poulina"
python run_mlops_pipeline.py
```

### Monitoring et MLflow

```powershell
docker compose -f "\ML_poulina\monitoring\docker-compose.monitoring.yml" up -d
```

Interfaces disponibles :

- Angular : `http://localhost:4200`
- Django : `http://127.0.0.1:8000`
- Prometheus : `http://localhost:9090`
- Grafana : `http://localhost:3001`
- MLflow : `http://localhost:5000`



