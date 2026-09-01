# Analyse DS - poulina_DW

## Objectif 1 corrige

Le seuil de non-conformite a ete corrige selon votre regle metier:

- **non conforme si `note < 16`**

## Comparaison des modeles - Objectif 1

| modele | accuracy_mean | accuracy_std | balanced_accuracy_mean | balanced_accuracy_std | precision_mean | precision_std | recall_mean | recall_std | f1_mean | f1_std | roc_auc_mean | roc_auc_std |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| gradient_boosting_classifier | 0.448 | 0.180 | 0.506 | 0.022 | 0.565 | 0.328 | 0.713 | 0.404 | 0.405 | 0.314 | 0.554 | 0.191 |
| random_forest_classifier | 0.564 | 0.017 | 0.561 | 0.021 | 0.647 | 0.350 | 0.394 | 0.219 | 0.358 | 0.200 | 0.648 | 0.101 |
| logistic_regression | 0.567 | 0.242 | 0.427 | 0.127 | 0.245 | 0.254 | 0.354 | 0.410 | 0.286 | 0.308 | 0.555 | 0.329 |
| baseline_dummy | 0.343 | 0.163 | 0.500 | 0.000 | 0.017 | 0.030 | 0.250 | 0.433 | 0.033 | 0.056 | 0.500 | 0.000 |

**Modele retenu:** `gradient_boosting_classifier`

Metriques en prediction croisee:
- Accuracy: **0.448**
- Balanced accuracy: **0.470**
- Precision: **0.421**
- Recall: **0.664**
- F1: **0.515**

## Lecture rapide par filiale

| secteur | filiale | note_moyenne | taux_non_conformite | volume |
| --- | --- | --- | --- | --- |
| Agro | Agromed | 11.256 | 1.000 | 43 |
| Aliment | Premix | 12.837 | 1.000 | 43 |
| Avicole | couvoir cedria | 13.419 | 0.674 | 43 |
| Avicole | couvoir ennajeh | 15.093 | 0.488 | 43 |
| Aliment | Nutrimix sfax | 16.651 | 0.233 | 43 |
| Agro | Gipa | 18.000 | 0.093 | 43 |
| Aliment | SNA tunis | 18.326 | 0.047 | 43 |
| Agro | Sokapo | 20.000 | 0.000 | 43 |

## Remarque

Le DSO 2 reste inchange. Seul l'objectif de classification a ete recalcule avec le nouveau seuil `16`.
