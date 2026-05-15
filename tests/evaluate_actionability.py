#!/usr/bin/env python3
"""
Issue #19 — LLM Actionability Evaluation

Goal:
Evaluate whether Groq remediation responses are more actionable than static fallback responses.

Inputs:
- tests/dataset_80logs.json

Outputs:
- tests/results/actionability_report.json
- tests/results/actionability_report.txt
"""

import json
import os
import time
import urllib.request
import urllib.error
from pathlib import Path
from statistics import mean


DATASET_PATH = Path("tests/dataset_80logs.json")
RESULTS_DIR = Path("tests/results")
REPORT_JSON = RESULTS_DIR / "actionability_report.json"
REPORT_TXT = RESULTS_DIR / "actionability_report.txt"


STATIC_FALLBACKS = {
    "SECURITY": {
        "cause_probable": "Incident de sécurité potentiel détecté.",
        "actions_immediates": [
            "Vérifier les logs d'accès du service concerné.",
            "Bloquer l'adresse IP source si elle est suspecte.",
            "Notifier l'équipe sécurité pour analyse."
        ],
        "escalade_si": "Escalader si plusieurs tentatives similaires apparaissent dans les 10 minutes.",
        "severite_estimee": "CRITICAL"
    },
    "PERFORMANCE": {
        "cause_probable": "Saturation ou dégradation des ressources.",
        "actions_immediates": [
            "Vérifier l'utilisation CPU, RAM et disque.",
            "Identifier le processus ou service le plus consommateur.",
            "Redémarrer ou isoler le composant fautif si nécessaire."
        ],
        "escalade_si": "Escalader si la latence ou la saturation persiste plus de 10 minutes.",
        "severite_estimee": "HIGH"
    },
    "AVAILABILITY": {
        "cause_probable": "Indisponibilité du service ou d'une dépendance.",
        "actions_immediates": [
            "Vérifier l'état du service principal.",
            "Tester la connectivité vers les dépendances critiques.",
            "Redémarrer le service si aucune réponse n'est observée."
        ],
        "escalade_si": "Escalader si le service reste indisponible après redémarrage.",
        "severite_estimee": "CRITICAL"
    },
    "DATA": {
        "cause_probable": "Problème d'intégrité, de sauvegarde ou de stockage des données.",
        "actions_immediates": [
            "Stopper les écritures si une corruption est suspectée.",
            "Vérifier les sauvegardes récentes.",
            "Alerter l'équipe DBA pour diagnostic."
        ],
        "escalade_si": "Escalader si une perte ou corruption de données est confirmée.",
        "severite_estimee": "CRITICAL"
    },
    "NETWORK": {
        "cause_probable": "Problème de connectivité réseau ou de résolution DNS.",
        "actions_immediates": [
            "Tester la connectivité réseau vers le service.",
            "Vérifier les règles firewall et les routes.",
            "Contrôler la résolution DNS."
        ],
        "escalade_si": "Escalader si plusieurs services deviennent injoignables.",
        "severite_estimee": "HIGH"
    },
    "SYSTEM": {
        "cause_probable": "Défaillance système ou saturation de ressources.",
        "actions_immediates": [
            "Vérifier les logs système et kernel.",
            "Contrôler l'espace disque et la mémoire.",
            "Redémarrer le composant fautif si le diagnostic le confirme."
        ],
        "escalade_si": "Escalader si l'incident affecte plusieurs services.",
        "severite_estimee": "HIGH"
    }
}


def load_env_file(path=".env"):
    """
    Lightweight .env loader without external dependencies.
    Does not override already existing environment variables.
    """
    env_path = Path(path)

    if not env_path.exists():
        return

    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()

        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")

        os.environ.setdefault(key, value)


def load_dataset():
    if not DATASET_PATH.exists():
        raise FileNotFoundError(f"Dataset not found: {DATASET_PATH}")

    with DATASET_PATH.open("r", encoding="utf-8") as f:
        data = json.load(f)

    critical_logs = [
        item for item in data
        if item.get("expected_level") == "CRITICAL"
    ]

    if not critical_logs:
        raise ValueError("No CRITICAL logs found in dataset.")

    return critical_logs


def build_prompt(log):
    source_id = log.get("source_id", "unknown-service")
    category = log.get("expected_category", "SYSTEM")
    raw_log = log.get("raw_log", "")

    return f"""
Tu es un ingénieur SRE expert en monitoring et remédiation d'incidents.

Un log CRITICAL a été détecté.

Service: {source_id}
Catégorie: {category}
Log brut:
{raw_log}

Réponds uniquement en JSON valide avec cette structure:
{{
  "cause_probable": "...",
  "actions_immediates": ["action 1", "action 2", "action 3"],
  "escalade_si": "...",
  "severite_estimee": "HIGH ou CRITICAL"
}}

Contraintes:
- Les actions doivent être concrètes et directement exécutables.
- Évite les phrases vagues comme "vérifier le système" sans précision.
- Maximum 150 mots.
""".strip()


def call_groq(prompt):
    api_key = os.environ.get("GROQ_API_KEY")
    api_url = os.environ.get(
        "GROQ_API_URL",
        "https://api.groq.com/openai/v1/chat/completions"
    )
    model = os.environ.get("GROQ_MODEL", "llama-3.1-8b-instant")

    if not api_key or api_key == "CHANGE_ME":
        raise RuntimeError("GROQ_API_KEY is missing. Set it in .env before running the script.")

    if api_key.startswith("Bearer "):
        raise RuntimeError("GROQ_API_KEY must contain only the key, without 'Bearer ' prefix.")

    payload = {
        "model": model,
        "messages": [
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.3,
        "max_tokens": 300,
        "response_format": {"type": "json_object"}
    }

    req = urllib.request.Request(
        api_url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) LogSentinel/1.0"
        },
        method="POST"
    )

    start = time.time()

    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            raw = response.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Groq HTTP error {e.code}: {error_body}") from e
    except urllib.error.URLError as e:
        raise RuntimeError(f"Groq URL error: {e}") from e

    latency_ms = round((time.time() - start) * 1000, 2)

    parsed = json.loads(raw)
    content = parsed["choices"][0]["message"]["content"].strip()

    try:
        response_json = json.loads(content)
    except json.JSONDecodeError:
        response_json = {
            "cause_probable": content,
            "actions_immediates": [],
            "escalade_si": "",
            "severite_estimee": ""
        }

    return response_json, latency_ms


def static_response_for(log):
    category = log.get("expected_category", "SYSTEM")
    return STATIC_FALLBACKS.get(category, STATIC_FALLBACKS["SYSTEM"])


def score_actionability(response):
    """
    Score sur 10.
    The goal is not to judge linguistic quality, but operational actionability.
    """
    score = 0
    reasons = []

    cause = str(response.get("cause_probable", "")).strip()
    actions = response.get("actions_immediates", [])
    escalation = str(response.get("escalade_si", "")).strip()
    severity = str(response.get("severite_estimee", "")).strip().upper()

    if len(cause) >= 15:
        score += 2
    else:
        reasons.append("cause_probable too short or missing")

    if isinstance(actions, list) and len(actions) >= 3:
        score += 3
    else:
        reasons.append("less than 3 immediate actions")

    concrete_keywords = [
        "vérifier", "tester", "redémarrer", "bloquer", "isoler",
        "contrôler", "notifier", "alerter", "stopper", "consulter",
        "analyser", "identifier", "inspecter", "désactiver", "restaurer"
    ]

    concrete_actions = 0

    if isinstance(actions, list):
        for action in actions:
            text = str(action).lower()
            if any(keyword in text for keyword in concrete_keywords) and len(text) >= 20:
                concrete_actions += 1

    if concrete_actions >= 2:
        score += 2
    elif concrete_actions == 1:
        score += 1
        reasons.append("only one concrete action")
    else:
        reasons.append("actions are too vague")

    if len(escalation) >= 15:
        score += 2
    else:
        reasons.append("escalation condition missing or too short")

    if severity in {"HIGH", "CRITICAL"}:
        score += 1
    else:
        reasons.append("invalid or missing severity")

    return {
        "score": score,
        "is_actionable": score >= 7,
        "reasons": reasons
    }


def evaluate():
    load_env_file()
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    critical_logs = load_dataset()

    # Start with 10 CRITICAL logs to limit quota consumption.
    sample = critical_logs[:10]

    results = []

    for index, log in enumerate(sample, start=1):
        print(f"[{index}/{len(sample)}] Evaluating log id={log.get('id')} source={log.get('source_id')}")

        prompt = build_prompt(log)

        static_resp = static_response_for(log)
        static_score = score_actionability(static_resp)

        try:
            groq_resp, latency_ms = call_groq(prompt)
            groq_error = None
        except Exception as e:
            groq_resp = {}
            latency_ms = None
            groq_error = str(e)

        if groq_error:
            groq_score = {
                "score": 0,
                "is_actionable": False,
                "reasons": [groq_error]
            }
        else:
            groq_score = score_actionability(groq_resp)

        results.append({
            "log_id": log.get("id"),
            "source_id": log.get("source_id"),
            "category": log.get("expected_category"),
            "raw_log": log.get("raw_log"),
            "groq_response": groq_resp,
            "groq_latency_ms": latency_ms,
            "groq_score": groq_score,
            "static_response": static_resp,
            "static_score": static_score
        })

        time.sleep(0.3)

    groq_scores = [item["groq_score"]["score"] for item in results]
    static_scores = [item["static_score"]["score"] for item in results]

    groq_latencies = [
        item["groq_latency_ms"]
        for item in results
        if item["groq_latency_ms"] is not None
    ]

    summary = {
        "num_logs_evaluated": len(results),
        "groq_avg_actionability_score": round(mean(groq_scores), 2) if groq_scores else 0,
        "static_avg_actionability_score": round(mean(static_scores), 2) if static_scores else 0,
        "groq_actionability_rate": round(
            sum(1 for item in results if item["groq_score"]["is_actionable"]) / len(results),
            3
        ) if results else 0,
        "static_actionability_rate": round(
            sum(1 for item in results if item["static_score"]["is_actionable"]) / len(results),
            3
        ) if results else 0,
        "groq_avg_latency_ms": round(mean(groq_latencies), 2) if groq_latencies else None
    }

    report = {
        "issue": 19,
        "title": "LLM Actionability Evaluation",
        "summary": summary,
        "rubric": {
            "cause_probable": "2 points",
            "actions_immediates_count": "3 points",
            "actions_concreteness": "2 points",
            "escalade_si": "2 points",
            "severite_estimee": "1 point",
            "actionable_threshold": "score >= 7/10"
        },
        "results": results
    }

    with REPORT_JSON.open("w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    with REPORT_TXT.open("w", encoding="utf-8") as f:
        f.write("Issue #19 — LLM Actionability Evaluation\n")
        f.write("=" * 50 + "\n\n")
        f.write(f"Logs evaluated: {summary['num_logs_evaluated']}\n")
        f.write(f"Groq avg score: {summary['groq_avg_actionability_score']}/10\n")
        f.write(f"Static avg score: {summary['static_avg_actionability_score']}/10\n")
        f.write(f"Groq actionability rate: {summary['groq_actionability_rate'] * 100:.1f}%\n")
        f.write(f"Static actionability rate: {summary['static_actionability_rate'] * 100:.1f}%\n")
        f.write(f"Groq avg latency: {summary['groq_avg_latency_ms']} ms\n\n")

        f.write("Rubric:\n")
        f.write("- cause_probable: 2 points\n")
        f.write("- at least 3 immediate actions: 3 points\n")
        f.write("- concrete actions: 2 points\n")
        f.write("- escalation condition: 2 points\n")
        f.write("- severity: 1 point\n")
        f.write("- actionable if score >= 7/10\n\n")

        f.write("Per-log results:\n")
        for item in results:
            f.write(
                f"- log_id={item['log_id']} source={item['source_id']} "
                f"category={item['category']} "
                f"groq={item['groq_score']['score']}/10 "
                f"static={item['static_score']['score']}/10\n"
            )

        f.write("\nNotes:\n")
        if summary["groq_avg_latency_ms"] is None:
            f.write("- Groq did not return successful responses during this run.\n")
            f.write("- Check GROQ_API_KEY, GROQ_MODEL, GROQ_API_URL, quota, or network restrictions.\n")
        else:
            f.write("- Groq responses were successfully evaluated.\n")

    print("\n=== Summary ===")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"\nSaved: {REPORT_JSON}")
    print(f"Saved: {REPORT_TXT}")


if __name__ == "__main__":
    evaluate()