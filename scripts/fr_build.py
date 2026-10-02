"""Real-text cases from fiscal-fr-bench (ICML 2026, rosecymbler/fiscal-fr-bench@6ca3807): R3 temporal questions
from the 209-question killer set, with (a) the gold version text (as-of), (b) the CURRENT version text (what a
static RAG returns), (c) a bounded version history (the multi-stage input we compress). Gold and nuggets are theirs.
"""
import json
import re
from pathlib import Path

import pyarrow.parquet as pq

from common import pick_by_hash

import os

# A local clone of rosecymbler/fiscal-fr-bench at commit 6ca3807 (CC-BY-4.0 data, MIT code).
FR = Path(os.environ.get("FISCAL_FR_BENCH_DIR", "fiscal-fr-bench"))
OUT = Path(__file__).parent / "fr-cases.json"
SEED = "fr-real-20260921-v1"
MAX_HISTORY_CHARS = 55000


def main(n: int = 40, per_article: int = 2, keep_from: str | None = None, out: Path = OUT) -> None:
    q = json.load(open(FR / "data/benchmark/questions.json", encoding="utf-8"))
    nug = json.load(open(FR / "data/benchmark/nuggets.json", encoding="utf-8"))
    killer = set((FR / "data/benchmark/killer_qids_v2.txt").read_text().split())
    excluded = set((FR / "data/benchmark/excluded_qids_scope.txt").read_text().split())
    r3 = [x for x in q if x["regime"] == "R3" and x["qid"] in killer and x["qid"] not in excluded and x.get("scope", "in") == "in"]
    by_qid_nug = {}
    for x in nug:
        by_qid_nug.setdefault(x["qid"], []).append(x)
    t = pq.read_table(FR / "data/articles_cgi_versioned.parquet", columns=["id", "cid", "num", "texte_clean", "date_debut", "date_fin"]).to_pylist()
    versions = {}
    for r in t:
        versions.setdefault(r["cid"], []).append(r)
    for cid in versions:
        versions[cid].sort(key=lambda r: r["date_debut"])
    # at most 2 questions per article, then hash-pick n
    groups = {}
    for x in sorted(r3, key=lambda x: x["qid"]):
        groups.setdefault(x["gold"]["article_cid"], []).append(x)
    pool = []
    for cid, xs in groups.items():
        pool.extend(pick_by_hash([x["qid"] for x in xs], SEED + cid, per_article))
    keep = set()
    if keep_from:
        keep = {c["qid"] for c in json.loads(Path(keep_from).read_text(encoding="utf-8"))}
    rest = [q for q in pool if q not in keep]
    chosen = keep | set(pick_by_hash(rest, SEED + ":extra", max(0, n - len(keep))))
    cases = []
    for x in r3:
        if x["qid"] not in chosen:
            continue
        cid = x["gold"]["article_cid"]; vs = versions.get(cid, [])
        gold = next((v for v in vs if v["id"] == x["gold"]["version_id"]), None)
        if not vs or gold is None:
            continue
        current = vs[-1]
        anchor = x["date_anchor"]
        # bounded history: versions nearest to the anchor plus the current one, chronological
        def fmt(v):
            d0 = v["date_debut"].date().isoformat() if v["date_debut"] else "?"
            d1 = v["date_fin"].date().isoformat() if v["date_fin"] and v["date_fin"].year < 2999 else "en cours"
            return f"[Article {v['num']} — version en vigueur du {d0} au {d1}]\n{v['texte_clean']}"
        idx = vs.index(gold)
        window = vs[max(0, idx - 3): idx + 3]
        if current not in window:
            window = window + [current]
        # never lose the gold or current version, and never cut a version's text (the asked figure may sit at
        # the end of a long article): drop the neighbours farthest from the gold version until the FULL texts fit
        keep = list(window)
        while True:
            history = "\n\n".join(fmt(v) for v in keep)
            if len(history) <= MAX_HISTORY_CHARS or len(keep) <= 2:
                break
            far = max((v for v in keep if v is not gold and v is not current), key=lambda v: abs(vs.index(v) - idx), default=None)
            if far is None:
                break
            keep.remove(far)
        if len(history) > MAX_HISTORY_CHARS and current is not gold and len(keep) == 2:
            keep = [gold]; history = fmt(gold)  # extreme case: the two versions alone exceed the cap
        window = keep
        assert fmt(gold).split("\n", 1)[0] in history
        cases.append({
            "qid": x["qid"], "prompt": x["prompt"], "date_anchor": anchor, "article_num": gold["num"],
            "gold_version_id": gold["id"], "current_version_id": current["id"], "gold_is_current": gold["id"] == current["id"],
            "gold_text": fmt(gold), "current_text": fmt(current), "history_text": history, "n_versions_total": len(vs), "n_in_history": len(window),
            "canonical_answer": x["gold"]["canonical_answer"], "nuggets": [n for n in by_qid_nug.get(x["qid"], []) if n["kind"] != "provenance"],
        })
    out.write_text(json.dumps(cases, indent=1, ensure_ascii=False))
    print(len(cases), "cases;", sum(c["gold_is_current"] for c in cases), "with gold == current;",
          "median history chars", sorted(len(c["history_text"]) for c in cases)[len(cases) // 2],
          "median gold chars", sorted(len(c["gold_text"]) for c in cases)[len(cases) // 2])
    c = cases[0]; print(c["qid"], c["prompt"][:120], "| gold:", c["canonical_answer"], "| nuggets:", [(n["kind"], n.get("pattern") or n.get("value") or n.get("target"), n.get("required")) for n in c["nuggets"]])


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(); ap.add_argument("n", type=int, nargs="?", default=40); ap.add_argument("--per-article", type=int, default=2)
    ap.add_argument("--keep-from", default=None); ap.add_argument("--out", default=str(OUT))
    a = ap.parse_args(); main(a.n, a.per_article, a.keep_from, Path(a.out))
