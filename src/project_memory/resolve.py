"""Pure projection. Expired/retracted replacements never resurrect their targets."""

from dataclasses import asdict, dataclass

from .models import Snapshot, digest


@dataclass(frozen=True)
class Resolution:
    key: str
    status: str
    value: str | None
    conditions: tuple[str, ...]
    supports: tuple[str, ...]
    history: tuple[tuple[str, str], ...]

    @property
    def fingerprint(self) -> str:
        # Notes/history alone must not invalidate a current dependency.
        return digest({k: v for k, v in asdict(self).items() if k != "history"})


def resolve(snapshot: Snapshot, key: str) -> Resolution:
    events = [
        r.event
        for r in snapshot.events
        if r.event.scope == snapshot.scope
        and r.event.key == key
        and r.recorded_at <= snapshot.known_at
        and r.event.effective_at <= snapshot.valid_at
    ]
    retirements: dict[str, list[str]] = {}
    for event in events:
        if event.kind in ("replace", "retract"):
            for target in event.targets:
                retirements.setdefault(target, []).append(event.kind)
    active = []
    history = []
    for event in events:
        if event.kind not in ("adopt", "replace"):
            continue
        if event.id in retirements:
            status = "retracted" if "retract" in retirements[event.id] else "superseded"
        elif event.expires_at is not None and event.expires_at <= snapshot.valid_at:
            status = "expired"
        else:
            status = "active"
            active.append(event)
        history.append((event.id, status))
    variants = {(e.value, tuple(sorted(e.conditions))) for e in active}
    conditions: tuple[str, ...]
    value: str | None
    if len(variants) > 1:
        status, value, conditions = "conflict", None, ()
    elif active:
        status, value, conditions = "active", active[0].value, tuple(sorted(active[0].conditions))
    else:
        statuses = {s for _, s in history}
        status = next(
            (s for s in ("retracted", "expired", "superseded") if s in statuses), "unknown"
        )
        value, conditions = None, ()
    return Resolution(
        key, status, value, conditions, tuple(sorted(e.id for e in active)), tuple(sorted(history))
    )
