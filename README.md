# LogSentinel

LogSentinel est un projet de classification et de traitement intelligent de logs. Il s'appuie sur une architecture conteneurisée via Docker, pilotée par **n8n** et **PostgreSQL**, combinant une analyse par automate fini déterministe (AFD) et des grands modèles de langage (LLM) pour la remédiation. 

Le système est conçu pour recevoir des logs en temps réel, évaluer l'état du système, mettre en cache les requêtes LLM, et générer des alertes actionnables via **WhatsApp (Twilio)** et **email (SMTP)**, complété par une boucle de feedback humain.

## Fonctionnalités Principales

D'après les composants actuellement implémentés dans le dépôt :
- **Ingestion via Webhook** : Réception des logs au format JSON, avec vérification de sécurité (HMAC/Secret).
- **Classification Hybride (AFD + LLM)** : Suivi de l'état système (NOMINAL, WARNING, ERROR, CRITICAL) par service, avec appel au LLM (Groq) pour l'analyse de la cause racine et la suggestion d'actions.
- **Cache LLM** : Système de mise en cache via PostgreSQL (hash du message) pour réduire les coûts et la latence liés aux requêtes LLM répétitives.
- **Alerting & Notification** : Envoi de messages structurés avec les actions immédiates recommandées via Twilio (WhatsApp) et par e-mail.
- **Boucle de Feedback (WhatsApp)** : Possibilité pour les administrateurs de répondre directement sur WhatsApp (ex: `ACK`, `RESOLVED`, `FALSE-POSITIVE`) pour corriger l'état dans la base de données et affiner les métriques.
- **Rapports Quotidiens** : Un workflow génère chaque jour un résumé statistique (MTTR, volume par criticité, taux de faux positifs) envoyé par e-mail et WhatsApp.

## Structure du Dépôt

```text
.
├── database/
│   └── schema.sql                  # Schéma PostgreSQL (logs, afd_states, feedback_corrections, llm_cache)
├── docs/                           # Documentation technique et discussions sur l'architecture
├── scripts/
│   └── demo-start.sh               # Script bash pour lancer le stack complet en mode démo avec Ngrok
├── tests/
│   ├── dataset_80logs.json         # Jeu de données contenant 80 logs de test
│   ├── run_metrics.py              # Script d'évaluation des performances (Matrice de confusion, F1-score)
│   ├── ablation_study.py           # Étude d'ablation pour comparer l'impact du LLM
│   ├── evaluate_actionability.py   # Script d'évaluation de la pertinence des actions proposées par le LLM
│   └── results/                    # Dossier généré contenant les rapports de tests (.json/.txt)
├── workflows/
│   ├── log-ingestion.json          # Workflow n8n principal (réception, AFD, LLM, alerte)
│   ├── feedback.json               # Workflow n8n de réponse (Webhook depuis Twilio)
│   └── daily-report.json           # Workflow n8n CRON (Rapport quotidien)
├── docker-compose.yml              # Architecture de base (n8n + PostgreSQL)
├── docker-compose.override.demo.yml# Extension de l'architecture avec Ngrok pour l'accès public
└── .env.example                    # Modèle des variables d'environnement
```

## Prérequis

- **Docker** et **Docker Compose v2**
- **Python 3** (pour exécuter les tests localement)
- Compte **Twilio Sandbox** (pour les envois / réceptions WhatsApp)
- Clé API **Groq** (pour le moteur LLM Llama-3)
- Accès **SMTP** (pour l'envoi de mails)
- **Ngrok** (obligatoire si vous souhaitez tester la réception du feedback Twilio et le webhook d'ingestion public en local)

## Installation et Lancement Rapide

1. **Préparer l'environnement :**
   ```bash
   cp .env.example .env
   ```
   Remplissez les champs obligatoires dans le fichier `.env` (`POSTGRES_PASSWORD`, `N8N_ENCRYPTION_KEY`, clés d'API Groq et Twilio, paramètres SMTP).

2. **Démarrer la base de données et n8n :**
   ```bash
   docker compose up -d
   ```
   *n8n sera disponible sur `http://localhost:5678`.*

3. **Importer les workflows :**
   Accédez à l'interface de n8n et importez manuellement les 3 fichiers JSON situés dans le dossier `workflows/`. N'oubliez pas d'activer les nœuds Webhook et CRON.

4. **Connecter la base de données :**
   Lors du démarrage, PostgreSQL s'initialise automatiquement avec le fichier `database/schema.sql`. Les credentials dans les nœuds n8n devront correspondre à votre fichier `.env`.

## Mode Démo (Ngrok)

Un script est fourni pour lancer directement la stack complète tout en exposant publiquement le système via Ngrok. Ceci est particulièrement utile pour connecter Twilio au webhook de feedback de votre machine locale.

1. Renseignez `NGROK_AUTHTOKEN` dans votre `.env`.
2. Lancez le script de démarrage interactif :
   ```bash
   bash scripts/demo-start.sh
   ```
   Le script s'assurera de monter la base, de rattacher ngrok et de reconfigurer n8n avec la bonne URL publique.

## Tests et Évaluations

Ce dépôt propose plusieurs utilitaires en Python permettant de tester rigoureusement l'AFD et la qualité du LLM.

```bash
# Vérifier la validité du dataset
python3 tests/validate_dataset.py

# Mesurer la précision du classifieur AFD
python3 tests/run_metrics.py

# Tester différentes configurations de la stack (Ablation Study)
python3 tests/ablation_study.py

# Générer un rapport sur l'actionabilité du LLM
python3 tests/evaluate_actionability.py
```

Les rapports finaux sont générés dans `tests/results/`.
