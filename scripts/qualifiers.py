"""Qualifier-span finder for T1b: temporal / scope / quantity / negation / attribution spans.

Deletion of these spans keeps the sentence's assertion but strips the restriction — the
`interval_dropped` / `widen_scope` / `unretract` family of edits, approximated by regex.
"""
import re

_PATTERNS = [
    ("temporal", re.compile(r"\b(?:until|till|before|after|since|during|between|from|by|as of|on|in)\s+(?:the\s+)?(?:early\s|late\s|mid-?)?(?:\d{1,4}(?:st|nd|rd|th)?|january|february|march|april|may|june|july|august|september|october|november|december|monday|tuesday|wednesday|thursday|friday|saturday|sunday|last|next|this|yesterday|today|tomorrow)(?:\s+(?:\d{1,4}(?:st|nd|rd|th)?|january|february|march|april|may|june|july|august|september|october|november|december|of|week|month|year|weeks|months|years|,))*", re.I)),
    ("scope", re.compile(r"\b(?:only|solely|exclusively|just|merely|mainly|mostly|partly|partially|allegedly|reportedly|apparently|possibly|potentially|temporarily)\b", re.I)),
    ("scope_pp", re.compile(r"\b(?:for|among|to|of|in)\s+(?:[A-Z][\w-]*\s+|\w+ing\s+)?(?:those|people|residents|customers|firms|companies|businesses|employees|women|men|children|adults|patients|users|members|households)\b", re.I)),
    ("quantity", re.compile(r"\b(?:fewer|less|more|greater|at least|at most|up to|nearly|almost|about|around|over|under|some|several|a few)\s+than\s+\w+|\b(?:fewer|less|more|greater|at least|at most|up to|nearly|almost|about|around|over|under)\s+\d[\d,.]*\s*(?:%|percent|per cent|million|billion|thousand|people|years?|months?|days?|hours?)?", re.I)),
    ("negation", re.compile(r"\b(?:not|never|no longer|n't|without|unless|except)\b", re.I)),
    ("attribution", re.compile(r"\b(?:according to [^,.;]{1,40}|(?:he|she|they|it|officials?|police|the \w+) (?:said|says|claimed|claims|reported|reports|alleged|alleges|suggested|suggests|believed|believes))\b", re.I)),
]


def qualifier_spans(sentence: str) -> list[dict]:
    """Non-overlapping spans, ordered by position: {kind, start, end, text}."""
    found = []
    for kind, pat in _PATTERNS:
        for m in pat.finditer(sentence):
            if m.end() - m.start() < 2:
                continue
            found.append({"kind": kind, "start": m.start(), "end": m.end(), "text": m.group(0)})
    found.sort(key=lambda s: (s["start"], -(s["end"] - s["start"])))
    out, last_end = [], -1
    for s in found:
        if s["start"] >= last_end:
            out.append(s)
            last_end = s["end"]
    return out


def delete_spans(sentence: str, spans: list[dict]) -> str:
    text = sentence
    for s in sorted(spans, key=lambda x: -x["start"]):
        text = text[: s["start"]] + text[s["end"]:]
    return re.sub(r"\s{2,}", " ", text).replace(" ,", ",").replace(" .", ".").strip()
