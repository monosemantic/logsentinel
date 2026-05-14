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