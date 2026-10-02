"""Exact anchors inside one already selected source; never fuzzy or cross-source search."""

from .models import MemoryError

POLICY = "project-memory.exact-quote.v1"
INSTRUCTIONS = """
Citation locator contract: quote the original exactly, including relevant qualifiers.
For a unique exact quotation use start=null, end=null: the host computes Unicode offsets.
Only for repeated text supply an exact start/end pair to identify the intended occurrence,
or quote a longer unique passage. Never guess an occurrence or paraphrase a quotation.
The host may resolve a unique exact quote when numeric offsets are mistaken. This proves
only its location in the supplied source, never the correctness of an interpretation.
"""


def resolve_quote(text: str, quote: object, start: object, end: object) -> tuple[int, int]:
    if not isinstance(quote, str) or not quote.strip():
        raise MemoryError("quote must be nonempty exact text")
    if not ((start is None and end is None) or (type(start) is int and type(end) is int)):
        raise MemoryError("quote offsets must be an integer pair or null pair")
    if isinstance(start, int) and isinstance(end, int):
        if 0 <= start < end <= len(text) and text[start:end] == quote:
            return start, end
    first = text.find(quote)
    if first < 0:
        raise MemoryError("quote absent from selected original")
    # Advance one code point, not quote length: overlapping matches are ambiguous too.
    if text.find(quote, first + 1) >= 0:
        raise MemoryError("quote ambiguous in selected original")
    return first, first + len(quote)
