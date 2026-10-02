"""Two helpers the event scripts (fr_events_rescore.py, t4_events.py) import from the core's test module.

Kept under the original module name so the scripts run unchanged. The core's full test-suite is not part of
this release; these are the only two symbols the research harness uses.
"""
from project_memory import Event, Scope, Source

SCOPE = Scope("business", "conference", "architecture")
T1 = "2026-09-01T00:00:00+00:00"


def add(store, id="a", kind="adopt", value="A", targets=(), at=T1, expires=None, scope=SCOPE,
        role="owner", key="storage", conditions=()):
    """Append one source + one event to a Store and return the event (the journal's write path)."""
    source = Source("source-" + id, scope, "operator", role, "Source message: " + str(value))
    store.append_source(source, store.revision(scope))
    event = Event(id, scope, key, kind, value, source.id, source.hash, 0, len(source.text), at,
                  targets, conditions, expires)
    store.append_event(event, store.revision(scope))
    return event
