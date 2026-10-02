"""Application key semantics and tagged time syntax, not a semantic truth oracle."""

from .models import MemoryError, nonempty, timestamp
from .quote_locator import resolve_quote

VERSION = "project-memory.decision-contract.v1"
DEFAULT_DEFINITIONS = {
    "plan": "Selected future work, next action, sequencing, and approved first deliverable. "
    "Approval or replacement of a named first result is a plan update even without the word plan. "
    "Distinguish a future deliverable decision from a report that work was already completed.",
    "deliverable": "The selected output to produce, including its priority and scope.",
    "budget": "Approved spending limits, currency, funding and prohibitions on exceeding cost.",
    "environment": "Authorized execution or deployment environment, data sources, privacy and "
    "local/cloud constraints, including explicit bans and required operating conditions.",
    "deadline": "A required completion date or time limit on work. Do not confuse it with the "
    "time a decision becomes effective or an authorization expires.",
}
SEMANTIC_INSTRUCTIONS = """
Interpret keys using decision_contract.definitions, shared with the other stages.
Classify the source's speech act before constructing candidates. An owner's definite
instruction or selection of next work is a decision; it need not say 'I approve'. Role
alone does not turn tentative ideas, questions or quoted historical statements into decisions.
Do not downgrade a definite next-work directive to proposal merely because it uses future tense.
Review both content and intent: a decision represented as a proposal is not fully covered.
Match meaning across languages, not literal occurrences of the English key name.
Do not infer cancellation from recency. A replacement can target only adopted/replacement
events, not a proposal. Unclear authority, conflicting choices or missing targets need review.
"""
TIME_INSTRUCTIONS = """
Use timing and expiry, NOT time_basis/effective_at/expires_at, in each candidate.
timing is exactly one of:
{"kind":"message_time"} (no explicit start date: host binds message time),
{"kind":"explicit","at":aware ISO timestamp,"quote":exact source passage with the start date},
{"kind":"uncertain"} (unresolved effective/expiry timing; not admissible).
expiry is null when no explicit end is stated, otherwise exactly
{"at":aware ISO timestamp,"quote":exact source passage with the end restriction}.
Quote enough text to identify one occurrence. Preserve future starts and exclusive end times.
Do not put a completion deadline into expiry unless permission itself expires then.
Do not invent a timezone or time for an ambiguous date: use uncertain if needed.
A parseable timestamp or an exact quote does not prove the date interpretation is correct.
"""


def definition_contract(keys: tuple[str, ...], provided: dict[str, str] | None = None) -> dict:
    if provided is not None and not isinstance(provided, dict):
        raise MemoryError("key definitions must be an object")
    supplied = {} if provided is None else provided
    if set(supplied) - set(keys):
        raise MemoryError("definition supplied for an unlisted key")
    definitions = {}
    for key in keys:
        value = supplied.get(key, DEFAULT_DEFINITIONS.get(key))
        if value is None:
            raise MemoryError("custom decision key requires an explicit definition")
        nonempty(value)
        definitions[key] = value
    return {"version": VERSION, "definitions": definitions}


def _fields(value: object, keys: set[str]) -> dict:
    if not isinstance(value, dict) or set(value) != keys:
        raise MemoryError("invalid tagged time fields")
    return value


def _explicit(value: object, text: str, *, effective: bool = False) -> str:
    item = _fields(value, {"kind", "at", "quote"} if effective else {"at", "quote"})
    resolve_quote(text, item["quote"], None, None)
    return timestamp(item["at"])


def normalize_timing(raw: dict, text: str) -> dict:
    """Translate v3 tagged syntax into internal event fields. No guessed repairs.

    The strict legacy field tuple remains accepted as a migration input, not advertised
    in the v3 prompt. Mixing either representation is rejected by the caller's schema.
    Raw reply (including temporal quotes) stays in the recorded ModelResponse.
    """
    if "timing" not in raw and "expiry" not in raw:
        return raw
    if "timing" not in raw or "expiry" not in raw:
        raise MemoryError("tagged time requires timing and expiry")
    if {"time_basis", "effective_at", "expires_at"} & raw.keys():
        raise MemoryError("mixed time representations")
    timing = raw["timing"]
    if not isinstance(timing, dict):
        raise MemoryError("timing must be a tagged object")
    kind = timing.get("kind")
    if kind == "explicit":
        effective = _explicit(timing, text, effective=True)
    elif kind in ("message_time", "uncertain"):
        _fields(timing, {"kind"})
        effective = None
    else:
        raise MemoryError("unknown timing kind")
    expiry = None if raw["expiry"] is None else _explicit(raw["expiry"], text)
    return {
        **{k: v for k, v in raw.items() if k not in ("timing", "expiry")},
        "time_basis": kind,
        "effective_at": effective,
        "expires_at": expiry,
    }
