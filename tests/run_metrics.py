import json
import time
import hmac
import hashlib
import os
import statistics
import requests
from collections import defaultdict

# Configuration
WEBHOOK_URL    = os.getenv("WEBHOOK_URL", "http://localhost:5678")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "change_me")
DATASET_PATH   = "dataset_80logs.json"
RESULTS_DIR    = "results"
CLASSES        = ["INFO", "WARNING", "ERROR", "CRITICAL"]
DELAY_MS       = 100 

# Signature HMAC
def sign_payload(payload: str) -> str:
    return hmac.new(
        WEBHOOK_SECRET.encode(),
        payload.encode(),
        hashlib.sha256
    ).hexdigest()

# Charger le dataset
with open(DATASET_PATH, "r", encoding="utf-8") as f:
    dataset = json.load(f)

print(f"Dataset chargé : {len(dataset)} logs")
print(f"Webhook : {WEBHOOK_URL}/webhook/logs")
print("─" * 50)

# Envoyer les logs et collecter les résultats
y_true    = []
y_pred    = []
latencies = []
errors    = 0

for i, log in enumerate(dataset):
    payload = json.dumps({
        "raw_log":   log["raw_log"],
        "source_id": log.get("source_id", "test-service")
    })
    headers = {
        "Content-Type":    "application/json",
        "X-Webhook-Secret": sign_payload(payload)
    }

    try:
        t0 = time.time()
        r  = requests.post(
            f"{WEBHOOK_URL}/webhook/logs",
            data=payload,
            headers=headers,
            timeout=10
        )
        latency_ms = (time.time() - t0) * 1000
        latencies.append(latency_ms)

        print(r.json())
        predicted = r.json().get("status", "UNKNOWN")
        y_true.append(log["expected_level"])
        y_pred.append(predicted)

        status = "YES" if predicted == log["expected_level"] else "NO"
        print(f"{status} Log {i+1:02d}/{len(dataset)} | Attendu: {log['expected_level']:8} | Prédit: {predicted:8} | {latency_ms:.0f}ms")

    except Exception as e:
        print(f"! Log {i+1} — Erreur : {e}")
        y_true.append(log["expected_level"])
        y_pred.append("UNKNOWN")
        errors += 1

    time.sleep(DELAY_MS / 1000)

# Matrice de confusion
confusion = defaultdict(lambda: defaultdict(int))
for true_cls, pred_cls in zip(y_true, y_pred):
    confusion[true_cls][pred_cls] += 1

# Métriques par classe
metrics = {}
for cls in CLASSES:
    tp = confusion[cls][cls]
    fp = sum(confusion[other][cls] for other in CLASSES if other != cls)
    fn = sum(confusion[cls][other] for other in CLASSES if other != cls)

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall    = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1        = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0

    metrics[cls] = {"tp": tp, "fp": fp, "fn": fn,
                    "precision": precision, "recall": recall, "f1": f1}

total_correct = sum(1 for t, p in zip(y_true, y_pred) if t == p)
accuracy      = total_correct / len(y_true)
macro_f1      = sum(m["f1"] for m in metrics.values()) / len(CLASSES)

# Latence
lat_mean = statistics.mean(latencies) if latencies else 0
lat_min  = min(latencies) if latencies else 0
lat_max  = max(latencies) if latencies else 0
lat_p95  = sorted(latencies)[int(0.95 * len(latencies))] if latencies else 0

# Affichage console
print("\n" + "=" * 60)
print("RÉSULTATS MÉTRIQUES")
print("=" * 60)
print(f"  Accuracy   : {accuracy:.2%}  ({total_correct}/{len(y_true)} corrects)")
print(f"  Macro F1   : {macro_f1:.4f}")
print(f"  Erreurs    : {errors} requêtes échouées")
print()
print(f"  {'Classe':10} {'Precision':10} {'Recall':10} {'F1':10}")
print(f"  {'-'*10} {'-'*10} {'-'*10} {'-'*10}")
for cls in CLASSES:
    m = metrics[cls]
    print(f"  {cls:10} {m['precision']:.4f}     {m['recall']:.4f}     {m['f1']:.4f}")

print()
print("MATRICE DE CONFUSION")
print(f"  {'':12}", "  ".join(f"{c:10}" for c in CLASSES))
for true_cls in CLASSES:
    row = "  ".join(f"{confusion[true_cls][pred]:10}" for pred in CLASSES)
    print(f"  {true_cls:12} {row}")

print()
print("LATENCE")
print(f"  Moyenne : {lat_mean:.1f}ms | Min : {lat_min:.1f}ms | Max : {lat_max:.1f}ms | p95 : {lat_p95:.1f}ms")
print("=" * 60)

# Export JSON
os.makedirs(RESULTS_DIR, exist_ok=True)

report = {
    "accuracy":  round(accuracy, 4),
    "macro_f1":  round(macro_f1, 4),
    "per_class": {
        cls: {k: round(v, 4) if isinstance(v, float) else v for k, v in m.items()}
        for cls, m in metrics.items()
    },
    "confusion_matrix": {t: dict(confusion[t]) for t in CLASSES},
    "latency_ms": {
        "mean": round(lat_mean, 1),
        "min":  round(lat_min, 1),
        "max":  round(lat_max, 1),
        "p95":  round(lat_p95, 1)
    },
    "errors": errors
}

json_path = f"{RESULTS_DIR}/metrics_report.json"
txt_path  = f"{RESULTS_DIR}/metrics_report.txt"

with open(json_path, "w") as f:
    json.dump(report, f, indent=2)

with open(txt_path, "w") as f:
    f.write(f"Accuracy  : {accuracy:.2%}\n")
    f.write(f"Macro F1  : {macro_f1:.4f}\n\n")
    for cls in CLASSES:
        m = metrics[cls]
        f.write(f"{cls}: Precision={m['precision']:.4f} Recall={m['recall']:.4f} F1={m['f1']:.4f}\n")

print(f"\nRapport sauvegardé dans {RESULTS_DIR}/")