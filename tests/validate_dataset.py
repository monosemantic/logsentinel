import json
from collections import Counter

DATASET_PATH = "tests/dataset_80logs.json"

REQUIRED_FIELDS = {
    "id",
    "raw_log",
    "format_type",
    "source_id",
    "expected_level",
    "expected_category",
    "edge_case",
    "note",
}

VALID_LEVELS = {"INFO", "WARNING", "ERROR", "CRITICAL"}
VALID_CATEGORIES = {"SECURITY", "PERFORMANCE", "AVAILABILITY", "DATA", "NETWORK", "SYSTEM"}
VALID_FORMATS = {"plaintext", "json", "syslog", "apache", "unknown"}

with open(DATASET_PATH, "r", encoding="utf-8") as f:
    data = json.load(f)

errors = []

if not isinstance(data, list):
    errors.append("Le fichier doit contenir une liste JSON principale : [ ... ].")

if len(data) != 80:
    errors.append(f"Nombre de logs incorrect : {len(data)} au lieu de 80.")

ids = [item.get("id") for item in data]
if sorted(ids) != list(range(1, 81)):
    errors.append("Les ids doivent aller exactement de 1 à 80, sans doublon ni trou.")

level_counts = Counter(item.get("expected_level") for item in data)
category_counts = Counter(item.get("expected_category") for item in data)
format_counts = Counter(item.get("format_type") for item in data)
edge_count = sum(1 for item in data if item.get("edge_case") is True)

for i, item in enumerate(data, start=1):
    missing = REQUIRED_FIELDS - set(item.keys())
    extra = set(item.keys()) - REQUIRED_FIELDS

    if missing:
        errors.append(f"Log #{i} : champs manquants : {missing}")

    if extra:
        errors.append(f"Log #{i} : champs en trop : {extra}")

    if item.get("expected_level") not in VALID_LEVELS:
        errors.append(f"Log #{i} : expected_level invalide : {item.get('expected_level')}")

    if item.get("expected_category") not in VALID_CATEGORIES:
        errors.append(f"Log #{i} : expected_category invalide : {item.get('expected_category')}")

    if item.get("format_type") not in VALID_FORMATS:
        errors.append(f"Log #{i} : format_type invalide : {item.get('format_type')}")

    if not isinstance(item.get("edge_case"), bool):
        errors.append(f"Log #{i} : edge_case doit être true ou false.")

    if item.get("edge_case") is True and not item.get("note"):
        errors.append(f"Log #{i} : edge_case=true mais note vide.")

expected_level_distribution = {
    "INFO": 20,
    "WARNING": 20,
    "ERROR": 20,
    "CRITICAL": 20,
}

for level, expected_count in expected_level_distribution.items():
    if level_counts[level] != expected_count:
        errors.append(
            f"Niveau {level} : {level_counts[level]} logs au lieu de {expected_count}."
        )

for category in VALID_CATEGORIES:
    if category_counts[category] < 5:
        errors.append(
            f"Catégorie {category} : seulement {category_counts[category]} logs, minimum demandé = 5."
        )

if edge_count != 15:
    errors.append(f"Edge cases : {edge_count} au lieu de 15.")

print("=== Résumé dataset ===")
print("Nombre total de logs :", len(data))
print("Répartition niveaux :", dict(level_counts))
print("Répartition catégories :", dict(category_counts))
print("Répartition formats :", dict(format_counts))
print("Nombre edge cases :", edge_count)

if errors:
    print("\n=== ERREURS À CORRIGER ===")
    for error in errors:
        print("-", error)
    raise SystemExit(1)

print("\nDataset valide selon la Definition of Done de l'Issue #9.")