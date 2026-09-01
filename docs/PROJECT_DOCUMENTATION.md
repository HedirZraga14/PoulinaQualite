# Documentation complète du projet Poulina

## 1. Présentation générale

Poulina est une plateforme web orientée qualité et conformité qui combine :

- une application métier Django pour gérer les utilisateurs, la structure organisationnelle et les évaluations ;
- une interface Angular pour l'exploitation opérationnelle et administrative ;
- un moteur de machine learning pour assister la décision ;
- une couche MLOps et observabilité pour suivre les modèles en production.

Le projet est pensé comme une solution unifiée : la saisie métier alimente les évaluations, les évaluations alimentent les modèles, les modèles sont suivis par le registre MLOps et les performances sont surveillées dans la stack Prometheus/Grafana/MLflow.

## 2. Architecture technique

### 2.1 Vue d'ensemble

```text
Angular SPA
    |
    v
Django API (/api/auth/*)
    |
    +--> SQL Server / SQLite
    +--> Modèles joblib dans /models
    +--> Registre MLOps dans /outputs/mlops
    +--> Endpoints monitoring /monitoring/*
    |
    v
Prometheus / Grafana / MLflow (Docker)
```

### 2.2 Répertoires principaux

- `stage/` : application principale.
- `stage/stage_project/` : configuration Django.
- `stage/user/` : logique métier, vues, modèles, ML status, monitoring.
- `stage/frontend/` : application Angular.
- `models/` : artefacts ML promus.
- `outputs/` : sorties de comparaison, runs MLOps et rapports.
- `monitoring/` : stack Docker de supervision.
- racine Python : scripts d'entraînement, notebooks, registre MLOps, tracking MLflow.

## 3. Backend Django

### 3.1 Rôle du backend

Le backend Django porte :

- l'authentification ;
- la gestion des rôles ;
- la gestion des utilisateurs, secteurs, filiales et laboratoires ;
- la création, modification, consultation et agrégation des évaluations ;
- l'inférence ML ;
- l'exposition du statut MLOps ;
- le monitoring HTTP et ML.

### 3.2 Configuration Django

Fichier principal : [stage/stage_project/settings.py](../stage/stage_project/settings.py)

Points importants :

- `AUTH_USER_MODEL = 'user.User'`
- lecture d'un fichier `.env` local ;
- `DB_ENGINE` peut basculer entre `sqlite` et `sqlserver` ;
- SQL Server est le mode par défaut ;
- `ALLOWED_HOSTS` et `CSRF_TRUSTED_ORIGINS` sont pilotés par variables d'environnement ;
- sessions en cookies signés ;
- middleware custom `ApiNoCacheMiddleware`.

### 3.3 Modèle de données

Fichier : [stage/user/models.py](../stage/user/models.py)

Le projet s'appuie sur un schéma de type flocon :

- `Sector` : secteur d'activité ;
- `Branch` : filiale rattachée à un secteur ;
- `Laboratoire` : laboratoire d'analyse ;
- `DateDim` : dimension temporelle ;
- `Evaluation` : table de faits qualité ;
- `User` : utilisateur authentifié par email.

Les rôles utilisateurs sont :

- `general_manager`
- `sector_manager`
- `user`

La table `Evaluation` contient notamment :

- `axe_evaluation`
- `criteres`
- `note`
- `ponderation`
- `observations`
- `moy_ponderation`
- `tx_conformite`
- `filiale_name`
- `code`
- `created_at`
- `updated_at`

### 3.4 API principales

Fichiers : [stage/stage_project/urls.py](../stage/stage_project/urls.py) et [stage/user/urls.py](../stage/user/urls.py)

Routes majeures :

- Auth :
  - `/api/auth/register/`
  - `/api/auth/login/`
  - `/api/auth/logout/`
  - `/api/auth/admin/login/`

- Référentiels :
  - `/api/auth/admin/users/`
  - `/api/auth/admin/branches/`
  - `/api/auth/admin/sectors/`
  - `/api/auth/admin/laboratoires/`
  - `/api/auth/scope/`

- Evaluations :
  - `/api/auth/evaluations/`
  - `/api/auth/evaluations-summary/`
  - `/api/auth/evaluations-overview/`
  - `/api/auth/evaluations-session/`
  - `/api/auth/user/evaluations/`
  - `/api/auth/user/evaluations-summary/`
  - `/api/auth/user/evaluations-overview/`
  - `/api/auth/user/evaluations-session/`

- Profil :
  - `/api/auth/user/profile/`
  - `/api/auth/user/password/`

- IA / MLOps :
  - `/api/auth/ml/predict/`
  - `/api/auth/ml/status/`

- Monitoring :
  - `/monitoring/health/`
  - `/monitoring/metrics/`

### 3.5 Logique métier importante

Le fichier [stage/user/views.py](../stage/user/views.py) concentre une grande partie de la logique métier.

Points notables :

- gestion de périmètre selon le rôle de l'utilisateur ;
- agrégation des lignes d'évaluation en sessions d'évaluation ;
- cache backend léger pour les résumés et compteurs d'évaluations ;
- invalidation de cache à chaque écriture sur les évaluations ;
- endpoints dédiés au dashboard et aux cartes d'accueil.

## 4. Frontend Angular

### 4.1 Rôle du frontend

Le frontend Angular fournit :

- l'authentification et la navigation applicative ;
- les espaces utilisateur, responsable de secteur et responsable général ;
- les formulaires de saisie ;
- les listes et tableaux administratifs ;
- le workspace "Prédiction et IA" ;
- la page "Améliorer" pour les indicateurs MLOps.

### 4.2 Stack frontend

Fichier : [stage/frontend/package.json](../stage/frontend/package.json)

Technologies principales :

- Angular 21
- RxJS
- TypeScript
- `xlsx` pour les imports/export et fichiers tabulaires

Scripts :

- `npm start` : lance le serveur de dev Angular avec proxy ;
- `npm run build` : build de production ;
- `npm run test` : tests frontend.

### 4.3 Organisation frontend

Fichiers majeurs :

- [app.ts](../stage/frontend/src/app/app.ts)
- [app.html](../stage/frontend/src/app/app.html)
- [app.css](../stage/frontend/src/app/app.css)

Le frontend est fortement centralisé dans `app.ts` et `app.html`, avec :

- la gestion des rôles ;
- les chargements API ;
- les notifications ;
- les vues dashboard ;
- les vues d'évaluations ;
- la vue IA/MLOps.

### 4.4 Fonctionnalités visibles

- tableau de bord d'accueil ;
- cartes synthétiques utilisateurs / managers / filiales / secteurs / évaluations ;
- écrans CRUD de gestion ;
- liste paginée des évaluations ;
- intégration Power BI ;
- vues de prédiction et d'amélioration ;
- affichage des URLs Prometheus, Grafana et MLflow côté administration.

## 5. Machine Learning

### 5.1 Finalité métier

Le ML répond à deux besoins :

1. détecter le risque de non-conformité ;
2. prévoir la note probable d'une évaluation.

Le vocabulaire métier retenu dans l'interface est volontairement simplifié :

- `Alerte non-conformité`
- `Prévision de note`
- `Fiabilité globale`
- `Écart moyen`

### 5.2 Source des données

Le chargement du dataset est fait par [notebook_sqlserver_loader.py](../notebook_sqlserver_loader.py), à partir de SQL Server.

Le dataset est ensuite préparé pour produire des colonnes adaptées aux deux objectifs :

- variables numériques ;
- variables catégorielles ;
- cible binaire `non_conforme` ;
- cible continue `note_num`.

### 5.3 Script principal d'entraînement

Fichier : [ml_augmented_training.py](../ml_augmented_training.py)

Ce script gère :

- le chargement des données ;
- l'augmentation des données ;
- le prétraitement ;
- l'évaluation comparative des modèles ;
- la sauvegarde du meilleur modèle ;
- la journalisation MLOps ;
- l'envoi d'un run vers MLflow.

### 5.4 Variables utilisées

Variables numériques de base :

- `critere_rang`
- `ponderation_num`
- `jour`
- `mois`
- `trimestre`
- `annee`
- `latitude`
- `longitude`

Variables catégorielles :

- `axe_evaluation`
- `criteres`
- `role_utilisateur`
- `utilisateur`
- `filiale`
- `secteur`

### 5.5 Prétraitement

Le pipeline scikit-learn applique :

- `SimpleImputer` sur les numériques ;
- `StandardScaler` sur les numériques ;
- `SimpleImputer(strategy="most_frequent")` sur les catégorielles ;
- `OneHotEncoder(handle_unknown="ignore")` sur les catégorielles.

Une étape de normalisation protège aussi contre les erreurs de type lors de l'inférence.

### 5.6 Objectif 1 : classification non-conformité

Type :

- apprentissage supervisé ;
- classification binaire.

Algorithmes comparés :

- `LogisticRegression`
- `RandomForestClassifier`
- `GradientBoostingClassifier`
- `SVC` RBF

Validation :

- `StratifiedKFold(n_splits=5, shuffle=True, random_state=42)`

Métriques :

- accuracy
- balanced accuracy
- precision
- recall
- F1
- ROC AUC

Règle métier :

- une non-conformité est définie par `note < 16`.

### 5.7 Objectif 2 : régression de note

Type :

- apprentissage supervisé ;
- régression.

Algorithmes comparés :

- `Ridge`
- `RandomForestRegressor`
- `GradientBoostingRegressor`
- `ExtraTreesRegressor`

Validation :

- `KFold(n_splits=5, shuffle=True, random_state=42)`

Métriques :

- MAE
- RMSE
- R²

### 5.8 Augmentation des données

Objectif 1 :

- stratégie proche d'un SMOTE tabulaire mixte personnalisé ;
- interpolation sur les variables numériques ;
- mélange contrôlé sur les variables catégorielles ;
- rééquilibrage de la classe minoritaire.

Objectif 2 :

- bootstrap avec remise ;
- injection de bruit gaussien léger sur les variables numériques ;
- bruit modéré sur la cible `note_num`.

### 5.9 Artefacts générés

Modèles promus :

- [models/objectif1_non_conformite.joblib](../models/objectif1_non_conformite.joblib)
- [models/objectif2_note.joblib](../models/objectif2_note.joblib)

Sorties d'entraînement :

- `outputs/objectif1_comparaison_modeles_augmented.csv`
- `outputs/objectif2_comparaison_modeles_augmented.csv`
- `outputs/objectif1_confusion_matrix.png`
- `outputs/objectif2_regression_plot.png`

## 6. Inférence ML dans l'application

Fichier : [stage/user/ml_inference.py](../stage/user/ml_inference.py)

Responsabilités :

- charger les modèles `.joblib` ;
- recharger automatiquement les modèles si les fichiers changent ;
- transformer les payloads d'évaluations en DataFrame de features ;
- exécuter les prédictions classification + régression ;
- calculer les agrégats métier de synthèse ;
- publier des métriques de monitoring.

Règle métier importante :

- la non-conformité prédite finale est dérivée de la note prédite :
  - `predicted_non_conforme = predicted_note < 16`

Cela garantit la cohérence entre note, conformité et synthèse affichée.

## 7. MLOps

### 7.1 Registre local

Fichier : [mlops_registry.py](../mlops_registry.py)

Le registre local garde :

- l'état courant des objectifs ;
- le dernier modèle promu ;
- les métriques promues ;
- la traçabilité des runs ;
- les métadonnées runtime ;
- les informations d'artefact.

Fichiers générés :

- [outputs/mlops/registry.json](../outputs/mlops/registry.json)
- `outputs/mlops/runs/objectif1_non_conformite.jsonl`
- `outputs/mlops/runs/objectif2_prediction_note.jsonl`

### 7.2 Pipeline MLOps

Fichier : [run_mlops_pipeline.py](../run_mlops_pipeline.py)

Le pipeline :

1. entraîne l'objectif 1 ;
2. entraîne l'objectif 2 ;
3. met à jour le registre local ;
4. envoie les runs vers MLflow ;
5. imprime un résumé JSON du pipeline.

### 7.3 Interface d'administration

Fichier : [stage/user/mlops_status.py](../stage/user/mlops_status.py)

Le backend expose à l'UI :

- le registre courant ;
- les runs récents ;
- les artefacts ;
- les chemins utiles ;
- les URLs monitoring.

L'écran Angular "Améliorer" transforme ensuite ces données techniques en langage métier.

### 7.4 MLflow

Fichier : [mlflow_tracking.py](../mlflow_tracking.py)

Cette couche :

- crée ou récupère les expériences ;
- crée les runs ;
- envoie paramètres, métriques et tags via HTTP ;
- termine les runs avec le bon statut ;
- relie l'entraînement Python local à l'interface MLflow Docker.

## 8. Monitoring et observabilité

### 8.1 Module Django

Fichier : [stage/user/monitoring.py](../stage/user/monitoring.py)

Il expose :

- métriques HTTP ;
- métriques d'inférence ML ;
- métriques de chargement de modèles ;
- métriques du registre MLOps ;
- état des artefacts ;
- endpoint health ;
- endpoint metrics.

### 8.2 Endpoints

- `GET /monitoring/health/`
- `GET /monitoring/metrics/`

### 8.3 Exemples de métriques

- `poulina_http_requests_total`
- `poulina_http_request_duration_seconds`
- `poulina_ml_inference_requests_total`
- `poulina_ml_inference_duration_seconds`
- `poulina_mlops_promoted_metric`
- `poulina_model_artifact_size_bytes`

## 9. Docker

### 9.1 Stack Docker actuelle

Fichier : [monitoring/docker-compose.monitoring.yml](../monitoring/docker-compose.monitoring.yml)

Services :

- `prometheus`
- `grafana`
- `mlflow`

### 9.2 Ports

- Prometheus : `9090`
- Grafana : `3001`
- MLflow : `5000`

### 9.3 Images et volumes

- Prometheus utilise un fichier de configuration local.
- Grafana est provisionné via les dossiers `provisioning/` et `dashboards/`.
- MLflow persiste ses données dans :
  - `monitoring/mlflow/data`
  - `monitoring/mlflow/artifacts`

### 9.4 Commandes utiles

Démarrer :

```powershell
docker compose -f "c:\Users\hedir\OneDrive\Desktop\ML_poulina\monitoring\docker-compose.monitoring.yml" up -d
```

Voir les conteneurs :

```powershell
docker ps
```

Voir les logs MLflow :

```powershell
docker logs poulina-mlflow
```

Arrêter :

```powershell
docker compose -f "c:\Users\hedir\OneDrive\Desktop\ML_poulina\monitoring\docker-compose.monitoring.yml" down
```

## 10. Déploiement

### 10.1 Développement local

Backend :

```powershell
cd "c:\Users\hedir\OneDrive\Desktop\ML_poulina\stage"
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

Frontend :

```powershell
cd "c:\Users\hedir\OneDrive\Desktop\ML_poulina\stage\frontend"
npm install
npm start
```

Monitoring :

```powershell
docker compose -f "c:\Users\hedir\OneDrive\Desktop\ML_poulina\monitoring\docker-compose.monitoring.yml" up -d
```

### 10.2 Déploiement backend

Pour un déploiement plus stable, il est recommandé de :

- passer `DEBUG` à `False` ;
- utiliser un vrai secret Django ;
- renseigner `ALLOWED_HOSTS` et `CSRF_TRUSTED_ORIGINS` ;
- sécuriser les credentials SQL Server et SMTP par variables d'environnement ;
- servir Django derrière un reverse proxy.

### 10.3 Déploiement frontend

Build Angular :

```powershell
cd "c:\Users\hedir\OneDrive\Desktop\ML_poulina\stage\frontend"
npm run build
```

Le build produit les artefacts statiques à publier derrière un serveur web.

### 10.4 Déploiement ML

Pour mettre à jour les modèles :

```powershell
cd "c:\Users\hedir\OneDrive\Desktop\ML_poulina"
python run_mlops_pipeline.py
```

Cela :

- régénère les `.joblib` ;
- met à jour le registre MLOps ;
- crée les runs MLflow.

### 10.5 Déploiement monitoring

La stack monitoring peut être déployée indépendamment de Django/Angular tant que :

- Prometheus peut atteindre `/monitoring/metrics/` ;
- Grafana peut joindre Prometheus ;
- MLflow conserve ses volumes.

## 11. Variables d'environnement recommandées

### Django

- `DJANGO_SECRET_KEY`
- `DJANGO_ALLOWED_HOSTS`
- `DJANGO_CSRF_TRUSTED_ORIGINS`
- `DB_ENGINE`
- `MSSQL_NAME`
- `MSSQL_HOST`
- `MSSQL_PORT`
- `MSSQL_USER`
- `MSSQL_PASSWORD`
- `MSSQL_TRUSTED_CONNECTION`
- `GMAIL_USER`
- `GMAIL_APP_PASSWORD`

### MLflow

- `MLFLOW_TRACKING_URI`

Par défaut, le pont MLflow utilise :

- `http://127.0.0.1:5000`

## 12. Flux opérationnel conseillé

1. L'utilisateur saisit ou charge des évaluations.
2. Django enregistre les lignes et calcule les indicateurs métier.
3. Angular affiche les résumés, compteurs et listes filtrées.
4. Le pipeline ML réentraîne les modèles si nécessaire.
5. Les meilleurs modèles sont sauvegardés en `.joblib`.
6. Le registre MLOps est mis à jour.
7. MLflow reçoit les runs d'entraînement.
8. Django recharge automatiquement les modèles si leurs fichiers changent.
9. Prometheus et Grafana surveillent le comportement applicatif.

## 13. Limites et points d'attention

- la couche frontend est très concentrée dans `app.ts` et `app.html`, ce qui peut compliquer l'évolutivité ;
- les artefacts ML sont journalisés vers MLflow sous forme de chemins locaux, pas encore uploadés comme artefacts hébergés MLflow ;
- le backend combine beaucoup de responsabilités dans `views.py` ;
- les secrets par défaut doivent être sécurisés avant tout déploiement réel ;
- l'inférence dépend de la compatibilité des versions scikit-learn avec les `.joblib`.

## 14. Fichiers clés à connaître

- [README.md](../README.md)
- [stage/stage_project/settings.py](../stage/stage_project/settings.py)
- [stage/user/views.py](../stage/user/views.py)
- [stage/user/models.py](../stage/user/models.py)
- [stage/user/ml_inference.py](../stage/user/ml_inference.py)
- [stage/frontend/src/app/app.ts](../stage/frontend/src/app/app.ts)
- [ml_augmented_training.py](../ml_augmented_training.py)
- [mlops_registry.py](../mlops_registry.py)
- [mlflow_tracking.py](../mlflow_tracking.py)
- [run_mlops_pipeline.py](../run_mlops_pipeline.py)
- [monitoring/docker-compose.monitoring.yml](../monitoring/docker-compose.monitoring.yml)
