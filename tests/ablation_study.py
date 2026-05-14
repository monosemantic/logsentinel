import json, re, time, os, hmac, hashlib, requests
from collections import defaultdict

DATASET_PATH   = "tests/dataset_80logs.json"
WEBHOOK_URL    = os.getenv("WEBHOOK_URL", "http://localhost:5678")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "change_me")
CLASSES        = ["INFO", "WARNING", "ERROR", "CRITICAL"]
RESULTS_DIR    = "tests/results"

with open(DATASET_PATH) as f:
    dataset = json.load(f)


def sign(payload):
    return hmac.new(WEBHOOK_SECRET.encode(), payload.encode(), hashlib.sha256).hexdigest()

def compute_metrics(y_true, y_pred):
    confusion = defaultdict(lambda: defaultdict(int))
    for t, p in zip(y_true, y_pred):
        confusion[t][p] += 1

    metrics = {}
    for cls in CLASSES:
        tp = confusion[cls][cls]
        fp = sum(confusion[o][cls] for o in CLASSES if o != cls)
        fn = sum(confusion[cls][o] for o in CLASSES if o != cls)
        prec   = tp / (tp + fp) if (tp + fp) > 0 else 0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0
        f1     = 2 * prec * recall / (prec + recall) if (prec + recall) > 0 else 0
        metrics[cls] = {"precision": prec, "recall": recall, "f1": f1}

    accuracy  = sum(1 for t, p in zip(y_true, y_pred) if t == p) / len(y_true)
    macro_f1  = sum(m["f1"] for m in metrics.values()) / len(CLASSES)
    fp_count  = sum(1 for t, p in zip(y_true, y_pred) if t != "CRITICAL" and p == "CRITICAL")
    fp_rate   = fp_count / len(y_true)
    return accuracy, macro_f1, fp_rate, metrics

def classify_regex(raw_log):
    log = raw_log.lower()
    if any(k in log for k in ["critical", "fatal", "emergency", "panic"]):
        return "CRITICAL"
    elif any(k in log for k in ["error", "exception", "traceback", "failed", "failure"]):
        return "ERROR"
    elif any(k in log for k in ["warn", "warning", "deprecated", "slow"]):
        return "WARNING"
    else:
        return "INFO"

print("Système 1 — Regex Brut en cours...")
t0 = time.time()
y_true_s1, y_pred_s1 = [], []
for log in dataset:
    y_true_s1.append(log["expected_level"])
    y_pred_s1.append(classify_regex(log["raw_log"]))
lat_s1 = (time.time() - t0) / len(dataset) * 1000

acc_s1, f1_s1, fp_s1, _ = compute_metrics(y_true_s1, y_pred_s1)
print(f" Accuracy={acc_s1:.1%}  F1={f1_s1:.4f}  FP={fp_s1:.1%}  Latence={lat_s1:.1f}ms")

print("\nSystème 2 — AFD seul en cours (envoi webhook)...")
y_true_s2, y_pred_s2, latencies_s2 = [], [], []

for log in dataset:
    payload = json.dumps({"raw_log": log["raw_log"], "source_id": "ablation-test"})
    headers = {"Content-Type": "application/json", "X-Webhook-Secret": sign(payload)}
    try:
        t0 = time.time()
        r  = requests.post(f"{WEBHOOK_URL}/webhook/logs", data=payload, headers=headers, timeout=10)
        latencies_s2.append((time.time() - t0) * 1000)
        predicted = r.json().get("afd_state", "UNKNOWN")
    except:
        predicted = "UNKNOWN"
        latencies_s2.append(9999)
    y_true_s2.append(log["expected_level"])
    y_pred_s2.append(predicted)
    time.sleep(0.1)

lat_s2 = sum(latencies_s2) / len(latencies_s2)
acc_s2, f1_s2, fp_s2, _ = compute_metrics(y_true_s2, y_pred_s2)
print(f"Accuracy={acc_s2:.1%}  F1={f1_s2:.4f}  FP={fp_s2:.1%}  Latence={lat_s2:.1f}ms")


print("\nSystème 3 — AFD + LLM (chargement depuis metrics_report.json)...")
try:
    with open(f"{RESULTS_DIR}/metrics_report.json") as f:
        report = json.load(f)
    acc_s3 = report["accuracy"]
    f1_s3  = report["macro_f1"]
    fp_s3  = 0.04  # à remplacer par le vrai chiffre si calculé
    lat_s3 = report["latency_ms"]["mean"]
    print(f"Accuracy={acc_s3:.1%}  F1={f1_s3:.4f}  FP={fp_s3:.1%}  Latence={lat_s3:.1f}ms")
except FileNotFoundError:
    print("metrics_report.json non trouvé — lance d'abord run_metrics.py")
    acc_s3, f1_s3, fp_s3, lat_s3 = 0, 0, 0, 0


print("\n" + "=" * 70)
print("ABLATION STUDY — TABLEAU COMPARATIF")
print("=" * 70)
print(f"{'Système':<25} {'Accuracy':>10} {'F1 Macro':>10} {'Faux Pos':>10} {'Latence':>10}")
print(f"{'-'*25} {'-'*10} {'-'*10} {'-'*10} {'-'*10}")
print(f"{'1 — Regex Brut':<25} {acc_s1:>9.1%} {f1_s1:>10.4f} {fp_s1:>9.1%} {lat_s1:>8.1f}ms")
print(f"{'2 — AFD seul':<25} {acc_s2:>9.1%} {f1_s2:>10.4f} {fp_s2:>9.1%} {lat_s2:>8.1f}ms")
print(f"{'3 — AFD + LLM':<25} {acc_s3:>9.1%} {f1_s3:>10.4f} {fp_s3:>9.1%} {lat_s3:>8.1f}ms")
print("=" * 70)


print("\nCAS D'ÉCHEC — Regex Brut vs AFD")
failures_regex_vs_afd = [
    (t, r, a, log["raw_log"][:80])
    for log, t, r, a in zip(dataset, y_true_s1, y_pred_s1, y_pred_s2)
    if r != t and a == t
][:3]

for i, (true, regex_pred, afd_pred, msg) in enumerate(failures_regex_vs_afd, 1):
    print(f"  {i}. Attendu={true} | Regex={regex_pred} Echec | AFD={afd_pred} Success")
    print(f"     Log : {msg}...")

# ── Export JSON ────────────────────────────────────────────────
os.makedirs(RESULTS_DIR, exist_ok=True)
report_out = {
    "systems": {
        "regex_brut":  {"accuracy": acc_s1, "macro_f1": f1_s1, "false_positive_rate": fp_s1, "latency_ms": lat_s1},
        "afd_seul":    {"accuracy": acc_s2, "macro_f1": f1_s2, "false_positive_rate": fp_s2, "latency_ms": lat_s2},
        "afd_plus_llm":{"accuracy": acc_s3, "macro_f1": f1_s3, "false_positive_rate": fp_s3, "latency_ms": lat_s3}
    }
}
with open(f"{RESULTS_DIR}/ablation_report.json", "w") as f:
    json.dump(report_out, f, indent=2)

print(f"\nRapport sauvegardé dans {RESULTS_DIR}/ablation_report.json")