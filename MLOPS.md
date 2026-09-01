# Documentation MLOps

## 1. Objectif

La couche MLOps du projet Poulina sert à rendre le cycle de vie des modèles plus traçable et plus exploitable.

Elle couvre :

- l'entraînement des deux objectifs ML ;
- la promotion automatique du meilleur modèle de chaque objectif ;
- la génération des artefacts `.joblib` ;
- l'historisation locale des runs ;
- l'exposition du statut MLOps dans l'application ;
- le tracking des runs dans MLflow ;
- la supervision avec Prometheus et Grafana.

## 2. Composants impliqués

### Entraînement

- [ml_augmented_training.py](ml_augmented_training.py)

### Registre local

- [mlops_registry.py](mlops_registry.py)

### Tracking MLflow

- [mlflow_tracking.py](mlflow_tracking.py)

### Pipeline complet

- [run_mlops_pipeline.py](run_mlops_pipeline.py)

### Backend MLOps status

- [stage/user/mlops_status.py](stage/user/mlops_status.py)

### Monitoring

- [stage/user/monitoring.py](stage/user/monitoring.py)
- [monitoring/docker-compose.monitoring.yml](monitoring/docker-compose.monitoring.yml)

## 3. Cycle de vie d'un run

1. Le pipeline charge les données depuis SQL Server.
2. Les datasets sont préparés et augmentés.
3. Plusieurs algorithmes sont comparés par validation croisée.
4. Le meilleur modèle est entraîné sur le dataset retenu.
5. Le modèle est sauvegardé dans `models/`.
6. Le registre local MLOps est mis à jour.
7. Un run MLflow est créé avec métriques, paramètres et tags.
8. Le backend Django recharge automatiquement les modèles si les fichiers changent.

## 4. Fichiers générés

### Modèles promus

- `models/objectif1_non_conformite.joblib`
- `models/objectif2_note.joblib`

### Registre local

- `outputs/mlops/registry.json`
- `outputs/mlops/runs/objectif1_non_conformite.jsonl`
- `outputs/mlops/runs/objectif2_prediction_note.jsonl`

### Sorties d'analyse

- `outputs/objectif1_comparaison_modeles_augmented.csv`
- `outputs/objectif2_comparaison_modeles_augmented.csv`

## 5. Commandes utiles

### Lancer un entraînement complet

```powershell
cd "c:\Users\hedir\OneDrive\Desktop\ML_poulina"
python run_mlops_pipeline.py
```

### Démarrer la supervision

```powershell
docker compose -f "c:\Users\hedir\OneDrive\Desktop\ML_poulina\monitoring\docker-compose.monitoring.yml" up -d
```

### Vérifier les conteneurs

```powershell
docker ps
```

### Voir les logs MLflow

```powershell
docker logs poulina-mlflow
```

## 6. MLflow

### URL

- `http://localhost:5000`

### Ce qui est loggé

- nom du meilleur modèle ;
- métriques principales du meilleur modèle ;
- dimensions du dataset avant et après augmentation ;
- top des meilleurs modèles ;
- tags de contexte ;
- chemins locaux des artefacts.

### Limite actuelle

Les fichiers d'artefacts ne sont pas encore uploadés comme artefacts MLflow hébergés ; ils sont référencés par leurs chemins locaux.

## 7. Monitoring

### Health check

- `http://127.0.0.1:8000/monitoring/health/`

### Metrics Prometheus

- `http://127.0.0.1:8000/monitoring/metrics/`

### Interfaces

- Prometheus : `http://localhost:9090`
- Grafana : `http://localhost:3001`
- MLflow : `http://localhost:5000`

## 8. Intégration dans l'application

Le endpoint `/api/auth/ml/status/` renvoie :

- les modèles promus ;
- les métriques de référence ;
- les runs récents ;
- les informations d'artefacts ;
- les URLs de monitoring.

Ces informations sont affichées dans l'espace Angular `Prédiction et IA > Améliorer`.

## 9. Variables d'environnement utiles

- `MLFLOW_TRACKING_URI`
- `DJANGO_ALLOWED_HOSTS`
- `DJANGO_CSRF_TRUSTED_ORIGINS`
- `DB_ENGINE`
- `MSSQL_*`

## 10. Recommandations

- conserver la même version de scikit-learn entre entraînement et inférence ;
- ne pas supprimer manuellement `registry.json` pendant l'exécution ;
- sécuriser les credentials avant déploiement ;
- sauvegarder les volumes MLflow si l'historique doit être conservé ;
- monitorer régulièrement le endpoint `/monitoring/health/`.
