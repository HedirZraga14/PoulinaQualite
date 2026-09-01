# Analyse Du Projet

## 1. Vue D'Ensemble

Ce projet est une application web de pilotage et de suivi des evaluations qualite au sein de plusieurs filiales du groupe.  
Elle couvre a la fois :

- la gestion des utilisateurs et des roles,
- la gestion des secteurs, filiales et laboratoires,
- la saisie et la consultation des evaluations,
- le calcul de moyennes et de taux de conformite,
- l'export PDF,
- un assistant conversationnel integre.

Le projet repond a un besoin de centralisation du controle qualite, avec une vision differenciee selon le role connecte.

## 2. Analyse Metier

### 2.1 Objectif metier

L'objectif principal est de structurer et industrialiser le suivi qualite des laboratoires et filiales, dans une logique de gouvernance groupe.

L'application permet de :

- collecter les evaluations par periode,
- consolider les resultats par filiale, secteur et utilisateur,
- suivre la conformite globale,
- piloter les actions de management qualite,
- offrir une tracabilite plus forte des controles.

### 2.2 Acteurs metier

Le projet distingue 3 profils :

1. `Administrateur` / `general_manager`
   - gere les utilisateurs, responsables, secteurs, filiales et laboratoires,
   - consulte toutes les evaluations,
   - accede aux details, exports et tableaux de bord,
   - recoit des notifications sur les nouvelles evaluations et nouveaux utilisateurs.

2. `Responsable de secteur` / `sector_manager`
   - suit les utilisateurs rattaches a son secteur,
   - consulte les evaluations des filiales de son secteur,
   - peut intervenir sur les donnees relevant de son perimetre.

3. `Utilisateur`
   - consulte son espace personnel,
   - gere son profil,
   - saisit ou consulte ses evaluations,
   - voit ses propres resultats et exports.

### 2.3 Objets metier principaux

- `Secteur` : niveau d'organisation principal
- `Filiale` : entite rattachee a un secteur
- `Laboratoire` : unite ou reference d'analyse
- `Utilisateur` : acteur du systeme avec role et rattachement
- `DateDim` : dimension temporelle
- `Evaluation` : fait metier central contenant les notes, ponderations et observations

### 2.4 Regles metier visibles dans le code

- un utilisateur simple est rattache a une filiale et indirectement a un secteur,
- un responsable de secteur est rattache a un secteur gere,
- l'administrateur voit tout,
- le responsable secteur ne voit que les evaluations de son secteur,
- le simple utilisateur ne voit que ses propres evaluations,
- les calculs de conformite reposent sur les notes et ponderations,
- le branding est important dans les exports et dans l'interface,
- l'application cherche a offrir une UX rapide avec cache session, toasts et indicateurs de chargement.

### 2.5 Valeur metier du projet

Le projet apporte une valeur forte sur :

- la standardisation des evaluations,
- la reduction de la dispersion des donnees,
- la lisibilite du pilotage qualite,
- le controle par role,
- la professionnalisation du reporting.

En pratique, c'est un outil de gouvernance qualite plus qu'un simple formulaire de saisie.

## 3. Analyse Fonctionnelle

### 3.1 Modules fonctionnels

Les modules actuellement identifies sont :

- authentification et inscription,
- tableau de bord administrateur,
- gestion des utilisateurs,
- gestion des secteurs,
- gestion des filiales,
- gestion des laboratoires,
- gestion des evaluations,
- detail et regroupement des evaluations par axes,
- export PDF,
- profil utilisateur,
- changement de mot de passe,
- chatbot integre.

### 3.2 Parcours clefs

#### Parcours administrateur

- connexion,
- acces au dashboard,
- administration des referentiels,
- consultation de toutes les evaluations,
- suivi des notifications,
- gestion unifiee des utilisateurs et responsables.

#### Parcours responsable de secteur

- connexion,
- acces a son espace secteur,
- consultation des utilisateurs de son secteur,
- suivi des evaluations des filiales rattachees,
- consultation detaillee et export.

#### Parcours utilisateur

- connexion ou inscription,
- acces a l'accueil personnel,
- consultation de ses evaluations,
- saisie ou suivi de checklist,
- export PDF,
- utilisation du chatbot.

## 4. Analyse Technique

### 4.1 Stack technique

Le projet repose sur :

- `Django` pour le backend,
- `Angular` pour le frontend,
- `SQL Server` comme base principale,
- `session cookies` pour l'authentification,
- `ODBC Driver 18` pour la connexion SQL Server.

### 4.2 Structure technique observee

#### Backend

Fichiers structurants :

- [user/models.py](file:///c:/Users/hedir/OneDrive/Desktop/stage/user/models.py)
- [user/views.py](file:///c:/Users/hedir/OneDrive/Desktop/stage/user/views.py)
- [user/urls.py](file:///c:/Users/hedir/OneDrive/Desktop/stage/user/urls.py)
- [stage_project/settings.py](file:///c:/Users/hedir/OneDrive/Desktop/stage/stage_project/settings.py)

Le backend centralise :

- les regles de role et de scope,
- les CRUD administratifs,
- les calculs et agregations d'evaluations,
- la gestion du chatbot,
- les retours JSON consommes par Angular.

#### Frontend

Fichiers structurants :

- [frontend/src/app/app.ts](file:///c:/Users/hedir/OneDrive/Desktop/stage/frontend/src/app/app.ts)
- [frontend/src/app/app.html](file:///c:/Users/hedir/OneDrive/Desktop/stage/frontend/src/app/app.html)
- [frontend/src/styles.css](file:///c:/Users/hedir/OneDrive/Desktop/stage/frontend/src/styles.css)

Le frontend est tres centralise dans le composant principal.  
Il porte :

- l'authentification,
- le routing logique par role,
- les tableaux d'administration,
- les formulaires,
- les exports,
- le chatbot,
- les notifications,
- le theme clair/sombre.

### 4.3 Modele de donnees

Le modele suit une logique proche d'un schema en flocon :

- dimensions : `Sector`, `Branch`, `Laboratoire`, `DateDim`,
- fait principal : `Evaluation`,
- acteur transversal : `User`.

Points forts :

- bonne separation entre referentiels et faits,
- presence de `created_at` / `updated_at` sur `Evaluation`,
- lien direct `User -> sector` utile pour le filtrage.

Point notable :

- certains champs sont denormalises dans `Evaluation` pour compatibilite import/export, ce qui est pratique mais demande une vigilance de coherence.

### 4.4 API backend

Les routes montrent une API REST legere, orientee besoins de l'application :

- auth : `register`, `login`, `logout`, `scope`
- admin : `admin/users`, `admin/branches`, `admin/sectors`, `admin/evaluations`, `admin/laboratoires`
- user : `user/evaluations`, `user/profile`, `user/password`
- transverse : `chatbot`, `evaluations-summary`, `checklist-template`

Cette API est lisible et adaptee a une SPA Angular.

### 4.5 Gestion de la performance

Des optimisations ont deja ete integrees :

- `CONN_MAX_AGE = 300` pour la base,
- session backend en `signed_cookies`,
- cache session cote frontend,
- timeout sur les requetes critiques,
- `finalize` pour reinitialiser les etats de chargement,
- chargement progressif du scope.

Cela montre que la performance est un enjeu concret du projet, notamment sur la connexion et les gros ecrans admin.

### 4.6 UX et UI

Le frontend porte une vraie logique produit :

- charte graphique homogene,
- mode clair / sombre,
- toasts de confirmation,
- barre d'activite,
- tables et cartes modernisees,
- chatbot popup,
- interfaces personnalisees selon le role.

Le projet est donc a mi-chemin entre application de gestion interne et produit d'entreprise soigne.

## 5. Points Forts Du Projet

- bonne couverture fonctionnelle pour un outil interne,
- separation metier claire entre administrateur, responsable et utilisateur,
- modele de donnees coherent avec le domaine,
- interface deja riche et orientee usage reel,
- effort visible sur la performance et la lisibilite,
- presence d'exports et de chatbot qui augmentent la valeur percue.

## 6. Limites Et Risques Techniques

### 6.1 Forte centralisation du frontend

`app.ts` et `app.html` concentrent beaucoup de responsabilites.  
Cela accelere les evolutions courtes, mais rend le projet plus difficile a maintenir a moyen terme.

Risque :

- regressions plus frequentes,
- lisibilite en baisse,
- tests plus difficiles a isoler.

### 6.2 Logique metier tres concentree dans `views.py`

Le fichier backend principal porte a la fois :

- auth,
- CRUD,
- filtres,
- calculs,
- chatbot,
- debug.

Risque :

- couplage fort,
- dette technique croissante,
- difficulte a separer les responsabilites.

### 6.3 Quelques marqueurs de mode dev

Dans `settings.py`, on observe :

- `DEBUG = True`,
- credentials SMTP par defaut,
- configuration plutot locale.

Pour une mise en production, il faudra renforcer :

- securite,
- secret management,
- environnement,
- observabilite.

### 6.4 Validation et tests

Le projet montre plusieurs validations par build et checks, mais on ne voit pas encore une base de tests automatisee structuree.

Risque :

- les regressions fonctionnelles peuvent augmenter avec la richesse des ecrans.

## 7. Recommandations Metier Et Techniques

### 7.1 Priorites metier

1. stabiliser les parcours critiques :
   - connexion,
   - consultation des evaluations,
   - export PDF,
   - gestion des utilisateurs.

2. clarifier les regles de calcul :
   - moyenne par axe,
   - conformite globale,
   - perimetre exact des responsables secteur.

3. formaliser les indicateurs de pilotage :
   - evaluations par periode,
   - conformite moyenne par secteur,
   - evolutions dans le temps.

### 7.2 Priorites techniques

1. decomposer le frontend en composants metier :
   - auth,
   - admin users,
   - admin evaluations,
   - chatbot,
   - profile.

2. isoler le backend en couches :
   - services metier,
   - serializers/reponses,
   - helpers de calcul,
   - integration IA.

3. introduire une base de tests :
   - tests unitaires sur calculs et filtres,
   - tests API sur scopes par role,
   - tests UI critiques.

4. preparer une configuration production :
   - secrets en environnement,
   - `DEBUG=False`,
   - logs propres,
   - gestion d'erreurs standardisee.

## 8. Conclusion

Le projet est deja plus avance qu'un simple prototype.  
Il s'agit d'une vraie application metier de gouvernance qualite, avec une profondeur fonctionnelle importante et une UX deja travaillee.

Sur le plan metier, il repond a un besoin clair de pilotage centralise des evaluations qualite.  
Sur le plan technique, la base est solide et fonctionnelle, mais elle gagnerait a etre refactorisee progressivement pour mieux supporter la croissance des fonctionnalites.

En resume :

- **metierement**, le projet est pertinent et bien aligne avec un usage entreprise,
- **techniquement**, il est efficace aujourd'hui, mais doit evoluer vers une structure plus modulaire pour rester durable.
