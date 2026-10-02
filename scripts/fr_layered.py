"""Layered restrictions on REAL articles (fiscal-fr-bench gold versions) for d_flip.

deepseek-chat finds, in the first ~1800 chars of a gold version, one sentence carrying at least two restrictions,
returns the exact restriction substrings and the unqualified false claim; code turns them into the seed schema
(segments / spans / corrupted) so `seed_tests.py` runs the same naive/anchored/d_flip protocol on real text.
"""
import json
import sys
import os
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
# Inputs and outputs live in one working folder (default ../work, built by prepare_work.py); override with WVV_WORK.
HERE = Path(os.environ.get("WVV_WORK", str(SCRIPTS.parent / "work")))
sys.path.insert(0, str(SCRIPTS))
import common  # noqa: E402
from common import make_model  # noqa: E402
from project_memory.language import ModelRequest  # noqa: E402
from project_memory.models import canonical  # noqa: E402

INSTR = """Dans le texte juridique ci-dessous, trouve UNE phrase qui énonce une règle assortie d'AU MOINS DEUX restrictions
indépendantes (condition de date/durée, seuil chiffré, catégorie de personnes/entreprises, champ d'application).
Réponds UNIQUEMENT en JSON :
{"sentence": "la phrase copiée MOT POUR MOT", "spans": ["sous-chaîne exacte de la restriction 1", "sous-chaîne exacte de la restriction 2", ...],
 "false_claim": "la règle énoncée SANS ces restrictions, une phrase au présent, en français",
 "true_claim": "la règle énoncée AVEC ses restrictions, une phrase, en français"}
Chaque span doit être une sous-chaîne exacte de la phrase, supprimable sans casser la grammaire. Si aucune phrase ne
convient, réponds {"sentence": null}."""


def build_segments(paragraph: str, spans: list[str]) -> list[dict] | None:
    positions = []
    for sp in spans:
        i = paragraph.find(sp)
        if i < 0:
            return None
        positions.append((i, i + len(sp), sp))
    positions.sort()
    for (a, b, _), (c, d, _) in zip(positions, positions[1:]):
        if c < b:
            return None
    segs, pos = [], 0
    for a, b, sp in positions:
        if a > pos:
            segs.append({"text": paragraph[pos:a], "kind": None, "critical": False})
        segs.append({"text": sp, "kind": "critical", "critical": True}); pos = b
    if pos < len(paragraph):
        segs.append({"text": paragraph[pos:], "kind": None, "critical": False})
    return segs


def main(n: int = 30) -> None:
    cases = json.loads((HERE / "fr-cases.json").read_text(encoding="utf-8"))[:n]
    common.MODEL = "deepseek-chat"
    model, _ = make_model("fr-layered-author-20260921", max_calls=n + 2, db_path=HERE / "fr-layered-author.sqlite", provider="deepseek", output_per_call=700)
    out = []
    for c in cases:
        para = c["gold_text"].split("\n", 1)[-1][:1800]
        req = ModelRequest("fr_layered", INSTR, canonical({"texte": para}), 20000, 700, version="smoke-fr-layered.v1")
        try:
            resp = model.complete(req); d = json.loads(resp.output)
        except Exception as exc:
            print(c["qid"], "author error", type(exc).__name__); continue
        if not d.get("sentence") or not d.get("spans") or len(d["spans"]) < 2 or d["sentence"] not in para:
            print(c["qid"], "no usable sentence"); continue
        segs = build_segments(para, d["spans"])
        if segs is None:
            print(c["qid"], "spans not exact/overlapping"); continue
        spans = [dict(index=k, kind=s["kind"], text=s["text"], critical=True) for k, s in enumerate(segs) if s["kind"]]
        corrupted = "".join(s["text"] for s in segs if not s["critical"])
        out.append({"id": "real-" + c["qid"], "family": "layered_real", "as_of": c["date_anchor"], "original": para, "corrupted": corrupted,
                    "spans": spans, "segments": segs, "false_claim": d["false_claim"], "true_claim": d.get("true_claim", ""), "author": "deepseek-chat",
                    "source_sentence": d["sentence"]})
        print(c["qid"], "OK spans", len(spans), "| FALSE:", d["false_claim"][:100], flush=True)
    (HERE / "fr-layered.json").write_text(json.dumps(out, indent=1, ensure_ascii=False))
    print(len(out), "real layered cases")


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 30)
