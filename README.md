# TER Sénégal — Backend (Django + DRF)

Projet L3 Génie Logiciel — Groupe Supdeco Dakar (ESITEC), 2025-2026.
Encadrement : Docteur Faye.

## Changement de stack

Ce backend remplace la version Spring Boot/Java initiale (module
`ter-core`). Les entités et leurs relations sont **identiques** au
diagramme de classes validé (19 classes) — seule l'implémentation change.
À reporter dans le chapitre 3 (ADR) du mémoire :

| ADR | Ancienne décision | Nouvelle décision |
|---|---|---|
| Langage/framework | Java 17 + Spring Boot 3.x | Python 3 + Django 6 + Django REST Framework |
| Base de données | PostgreSQL 15 | Inchangé |
| Authentification | JWT via Spring Security | JWT via `djangorestframework-simplejwt` |
| Communication inter-services | OpenFeign + Resilience4j | Sans objet — monolithe Django, pas de microservices |

## Structure

```
ter-senegal-backend/
├── manage.py
├── requirements.txt
├── docker-compose.yml          # PostgreSQL 15
├── ter_senegal/                 # config du projet (settings, urls)
├── comptes/                     # Utilisateur, Passager, Administrateur,
│                                 # Controleur, AgentGare, ChefTrain
├── billetterie/                 # Gare, Train, Wagon, Siege, Voyage,
│                                 # Tarif, Billet, Paiement
├── controle/                    # Controle (scan de billet a bord)
├── premium/                     # ServicePremium, Reclamation
└── notifications/               # Notification
```

## Choix de conception à retenir pour le mémoire

- **`Utilisateur` custom Django** (`AbstractUser`) plutôt qu'héritage
  multi-tables : c'est le pattern Django idiomatique pour
  l'authentification. Les rôles (`Passager`, `Administrateur`,
  `Controleur`, `AgentGare`, `ChefTrain`) sont des profils
  `OneToOneField` — équivalent fonctionnel de l'héritage JOINED du
  diagramme de classes, mais qui s'intègre nativement à
  `django.contrib.auth` (login, permissions, admin Django gratuit).
- **`Billet` fusionne réservation et billet** via un statut
  (`EN_ATTENTE`, `CONFIRME`, `ANNULE`).
- **`Voyage` distinct de `Train`** pour le reporting par tronçon/heure
  de pointe (section 3.5 du cahier des charges).
- **`ServicePremium` rattaché à `Wagon`**, pas à `Train` : suivi du
  wagon 1ère classe dédié.

## Démarrer

```bash
# 1. Base de données
docker compose up -d

# 2. Dépendances Python (idéalement dans un venv)
pip install -r requirements.txt

# 3. Migrations
python manage.py makemigrations
python manage.py migrate

# 4. Compte admin
python manage.py createsuperuser

# 5. Lancer le serveur
python manage.py runserver
```

L'admin Django est disponible sur `/admin/` — utile pour manipuler les
données pendant le développement sans attendre les endpoints DRF.

## Ce qui n'est pas encore fait

- Serializers DRF + ViewSets/endpoints REST pour chaque module
- Authentification JWT branchée sur les endpoints (`urls.py`)
- Frontend React.js (projet séparé, à initialiser avec `create-react-app`
  ou Vite)
- Mode offline contrôleur, génération QR code, intégration Orange
  Money/Wave (mock pour la démo)
