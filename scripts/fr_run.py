"""Real-text run on fiscal-fr-bench cases (mini by default).

Per question: compress the version history (stage 1, the lossy intermediate) → answer the question under three
evidence conditions — A compressed history, B current version (static RAG), C gold version (as-of) — scored with
the benchmark's deterministic nuggets (strict = all required nuggets) → then the H1 verifier judges each answer
against the SAME evidence it was produced from. Measures: accuracy per condition, and P(verifier accepts | wrong).
"""
import argparse
import json
import re
import sys
from collections import Counter
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import common  # noqa: E402
from common import make_model, verdict  # noqa: E402
from project_memory.language import ModelRequest  # noqa: E402
from project_memory.models import canonical  # noqa: E402

SCRIPTS = Path(__file__).resolve().parent
# Inputs and outputs live in one working folder (default ../work, built by prepare_work.py); override with WVV_WORK.
HERE = Path(os.environ.get("WVV_WORK", str(SCRIPTS.parent / "work")))
COMPRESS = """Résume fidèlement le texte juridique suivant (historique de versions d'un article) en au plus 1500 caractères,
en français, en conservant tous les chiffres, seuils, taux et dates. Réponds UNIQUEMENT en JSON {"context": string}."""
ANSWER = """Réponds à la question en te fondant UNIQUEMENT sur les éléments fournis (aucune connaissance extérieure). Donne la
valeur demandée (chiffre, taux, seuil ou délai) et le numéro d'article, en une ou deux phrases en français.
Réponds UNIQUEMENT en JSON {"answer": string}."""
NUM = re.compile(r"\d+(?:[   ]\d{3})*(?:[.,]\d+)?")


def numbers(text: str) -> list[float]:
    out = []
    for m in NUM.findall(text):
        s = m.replace(" ", "").replace(" ", "").replace(" ", "").replace(",", ".")
        try:
            out.append(float(s))
        except ValueError:
            pass
    # fractions like "33 1/3"
    for m in re.finditer(r"(\d+)\s+(\d)/(\d)", text):
        out.append(int(m.group(1)) + int(m.group(2)) / int(m.group(3)))
    return out


def nugget_ok(n: dict, answer: str) -> bool:
    k = n["kind"]
    if k == "regex":
        return re.search(n["pattern"], answer, re.I | re.U) is not None
    if k == "exact":
        return str(n["value"]).lower() in answer.lower()
    if k == "numeric_tol":
        tgt, tol = float(n["target"]), float(n.get("tol", 0))
        return any(abs(v - tgt) <= max(tol, 1e-9) for v in numbers(answer))
    return True


def strict(nuggets: list[dict], answer: str) -> bool:
    req = [n for n in nuggets if n.get("required")]
    return bool(req) and all(nugget_ok(n, answer) for n in req)


def call_json(model, purpose, instr, payload, max_out):
    req = ModelRequest(purpose, instr, canonical(payload), 60000, max_out, version="smoke-fr.v1")
    resp = model.complete(req)
    if resp.outcome != "completed":
        return None
    try:
        return json.loads(resp.output)
    except Exception:
        return None


def main(model_name: str, provider: str, run_id: str, limit: int | None, cases_file: str = "fr-cases.json") -> None:
    cases = json.loads((HERE / cases_file).read_text(encoding="utf-8"))
    if limit:
        cases = cases[:limit]
    common.MODEL = model_name
    model, _ = make_model(run_id, max_calls=len(cases) * 7 + 2, db_path=HERE / f"{run_id}.sqlite", provider=provider, output_per_call=700)
    rows = []
    for c in cases:
        comp = call_json(model, "fr_compress", COMPRESS, {"texte": c["history_text"]}, 700)
        compressed = (comp or {}).get("context") or ""
        conds = {"A_compressed": compressed, "B_current": c["current_text"], "C_gold": c["gold_text"]}
        r = {"qid": c["qid"], "gold_is_current": c["gold_is_current"], "compressed_chars": len(compressed), "compressed_text": compressed, "conds": {}}
        for name, evidence in conds.items():
            if not evidence:
                r["conds"][name] = {"answer": None, "correct": False, "verifier": "no_evidence"}; continue
            ans = (call_json(model, "fr_answer", ANSWER, {"question": c["prompt"], "date": c["date_anchor"], "elements": evidence}, 400) or {}).get("answer") or ""
            ok = strict(c["nuggets"], ans)
            q = f"Date de référence : {c['date_anchor']}. La réponse est-elle étayée par les éléments fournis pour cette date ? Conserver les dates d'entrée en vigueur, les versions et les seuils."
            v = verdict(model, q, ans, evidence)["verdict"] if ans else "no_answer"
            r["conds"][name] = {"answer": ans[:300], "correct": ok, "verifier": v}
        rows.append(r)
        print(c["qid"], {k: (("OK" if v["correct"] else "wrong"), v["verifier"][:3]) for k, v in r["conds"].items()}, flush=True)
    summ = {"model": model_name, "n": len(rows), "gold_is_current": sum(r["gold_is_current"] for r in rows)}
    for name in ("A_compressed", "B_current", "C_gold"):
        cs = [r["conds"][name] for r in rows]
        wrong = [x for x in cs if not x["correct"]]; right = [x for x in cs if x["correct"]]
        summ[name] = {"accuracy": f"{len(right)}/{len(cs)}",
                      "verifier_accepts_wrong": f"{sum(x['verifier']=='supported' for x in wrong)}/{len(wrong)}",
                      "verifier_accepts_right": f"{sum(x['verifier']=='supported' for x in right)}/{len(right)}",
                      "verifier_verdicts_on_wrong": dict(Counter(x["verifier"] for x in wrong))}
    (HERE / f"{run_id}.json").write_text(json.dumps({"summary": summ, "rows": rows}, indent=1, ensure_ascii=False))
    print(json.dumps(summ, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--model", default="gpt-5.4-mini-2026-03-17"); ap.add_argument("--provider", default="openai")
    ap.add_argument("--run-id", default="fr-mini-20260921"); ap.add_argument("--limit", type=int, default=None); ap.add_argument("--cases", default="fr-cases.json")
    a = ap.parse_args(); main(a.model, a.provider, a.run_id, a.limit, a.cases)
