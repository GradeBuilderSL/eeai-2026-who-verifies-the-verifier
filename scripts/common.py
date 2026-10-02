"""Shared wiring for the 2026-09-21 smoke tests (T1 d_flip, T3 placebo length).

Experiment tooling, not library code. One verifier call = one `evidence_request`
(identical instructions to H1) against gpt-5.4-mini; ~$0.001 per call.
"""
import json
import os
import re
import sqlite3
from pathlib import Path

from project_memory.call_budget import CallBudget, RunLimits
from project_memory.models import digest
from project_memory.openai_adapter import OpenAIModel
from project_memory.verification_experiment import evidence_request, parse_verdict

# External run data (AggreFact-derived H1 materials) lived outside git; point PM_RUNS at a copy if you have one.
RUNS = Path(os.environ.get("PM_RUNS", "runs"))
PREPARED = RUNS / "paired-access-20260919" / "prepared-cases.json"
OBSERVATIONS = RUNS / "paired-access-20260919" / "observations.json"
GOLD160 = RUNS / "external-data" / "aggrefact-paired160-20260919" / "gold.jsonl"
SENS32 = RUNS / "external-data" / "aggrefact-sensitivity32-20260919" / "cases.jsonl"
CAPS = {"max_input_chars": 60000, "max_output_tokens": 512}
MODEL = "gpt-5.4-mini-2026-03-17"


def load_keys() -> None:
    """Keys come from the environment only: PROJECT_MEMORY_OPENAI_API_KEY / PROJECT_MEMORY_DEEPSEEK_API_KEY,
    or the plain OPENAI_API_KEY / DEEPSEEK_API_KEY as a fallback. Values are never printed."""
    for name, plain in (("PROJECT_MEMORY_OPENAI_API_KEY", "OPENAI_API_KEY"),
                        ("PROJECT_MEMORY_DEEPSEEK_API_KEY", "DEEPSEEK_API_KEY")):
        if not os.environ.get(name) and os.environ.get(plain):
            os.environ[name] = os.environ[plain]


def make_model(run_id: str, max_calls: int, db_path: Path | None = None, provider: str = "openai",
               output_per_call: int = CAPS["max_output_tokens"]):
    load_keys()
    db = sqlite3.connect(str(db_path) if db_path else ":memory:", isolation_level=None)
    # RunLimits caps are RUN TOTALS (the primary H1 run reserved 487,680 output tokens for 800 calls).
    limits = RunLimits(MODEL, max_calls, max_calls * CAPS["max_input_chars"], max_calls * output_per_call,
                       provider=provider, reasoning_effort="none")
    budget = CallBudget(db, run_id, limits)
    return OpenAIModel(budget), budget


def verdict(model, question: str, claim: str, evidence: str, frame: str = "neutral") -> dict:
    request = evidence_request(question, claim, evidence, frame, CAPS)
    try:
        response = model.complete(request)
        parsed = parse_verdict(request, response)
        return {"verdict": parsed["verdict"], "reason": parsed["reason"],
                "input_tokens": response.input_tokens, "output_tokens": response.output_tokens,
                "request_hash": request.hash}
    except Exception as exc:  # budget/transport/parse failures are observations, not crashes
        return {"verdict": "error", "reason": type(exc).__name__, "input_tokens": None,
                "output_tokens": None, "request_hash": request.hash}


def load_gold160() -> dict:
    return {
        json.loads(l)["case_id"]: json.loads(l)["semantic_label"]
        for l in GOLD160.read_text(encoding="utf-8").splitlines() if l.strip()
    }


def load_observations(mode: str | None = None) -> dict:
    """case_id -> outcome for one arm of the primary mini run (frame neutral)."""
    rows = json.loads(OBSERVATIONS.read_text(encoding="utf-8"))
    out = {}
    for r in rows:
        if r.get("frame", "neutral") != "neutral":
            continue
        if mode is None or r["mode"] == mode:
            out.setdefault(r["case_id"], {})[r["mode"]] = r["outcome"]
    return out


_SENT = re.compile(r"(?<=[.!?])\s+(?=[A-Z\"'(\[])")


def split_sentences(text: str) -> list[str]:
    parts = [p.strip() for p in _SENT.split(text.strip()) if p.strip()]
    return parts


_WORD = re.compile(r"[A-Za-z0-9]+")
STOP = {"the", "a", "an", "of", "to", "in", "and", "is", "was", "for", "on", "that", "with", "as", "by", "at", "it", "be", "are", "from", "this", "has", "have", "had", "he", "she", "they", "his", "her", "their", "its", "or", "not", "but", "were", "been", "will", "would", "said"}


def overlap_rank(claim: str, sentences: list[str]) -> list[int]:
    """Indices of sentences ordered by descending content-word overlap with the claim (ties: original order)."""
    cw = {w.lower() for w in _WORD.findall(claim)} - STOP
    scored = []
    for i, s in enumerate(sentences):
        sw = {w.lower() for w in _WORD.findall(s)} - STOP
        scored.append((-len(cw & sw), i))
    return [i for _, i in sorted(scored)]


def build_placebo(summary: str, target_len: int, fillers: list[str]) -> str:
    """Compressed text first, then unrelated prose until total length == target_len (or all fillers used)."""
    if target_len <= len(summary):
        return summary
    out = summary
    for f in fillers:
        need = target_len - len(out)
        if need <= 0:
            break
        out = out + "\n\n" + f[: max(0, need - 2)]
    return out[:target_len]


def pick_by_hash(ids: list[str], seed: str, n: int) -> list[str]:
    return sorted(ids, key=lambda i: digest([seed, i]))[:n]
