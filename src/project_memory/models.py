"""Immutable contracts. All timestamps are aware UTC; offsets count Unicode code points."""

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any


class MemoryError(ValueError):
    """Invalid request, inconsistent evidence or unsupported operation."""


class RevisionConflict(MemoryError):
    pass


def canonical(value: Any) -> str:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    )


def digest(value: Any) -> str:
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def timestamp(value: str) -> str:
    if not isinstance(value, str):
        raise MemoryError("timestamp must be an ISO string")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise MemoryError("invalid timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise MemoryError("timestamp must include timezone")
    return parsed.astimezone(timezone.utc).isoformat(timespec="microseconds")


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def nonempty(value: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise MemoryError("expected nonempty string")


def strings(value: tuple[str, ...]) -> None:
    if not isinstance(value, tuple):
        raise MemoryError("expected tuple of strings")
    for item in value:
        nonempty(item)
    if len(set(value)) != len(value):
        raise MemoryError("duplicate entries")


@dataclass(frozen=True)
class Scope:
    tenant: str
    project: str
    area: str

    def __post_init__(self) -> None:
        for item in (self.tenant, self.project, self.area):
            nonempty(item)

    @property
    def id(self) -> str:
        return canonical(asdict(self))

    @property
    def project_id(self) -> str:
        return canonical([self.tenant, self.project])


@dataclass(frozen=True)
class Source:
    id: str
    scope: Scope
    actor: str
    role: str
    text: str

    def __post_init__(self) -> None:
        if not isinstance(self.scope, Scope):
            raise MemoryError("invalid scope")
        for value in (self.id, self.actor, self.text):
            nonempty(value)
        if self.role not in ("owner", "assistant", "external"):
            raise MemoryError("invalid source role")

    @property
    def hash(self) -> str:
        return digest(asdict(self))


@dataclass(frozen=True)
class Event:
    id: str
    scope: Scope
    key: str
    kind: str
    value: str | None
    source_id: str
    source_hash: str
    start: int
    end: int
    effective_at: str
    targets: tuple[str, ...] = ()
    conditions: tuple[str, ...] = ()
    expires_at: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.scope, Scope):
            raise MemoryError("invalid scope")
        for item in (self.id, self.key, self.source_id, self.source_hash):
            nonempty(item)
        if self.kind not in ("adopt", "replace", "retract", "propose", "note"):
            raise MemoryError("invalid event kind")
        if self.kind == "retract":
            if self.value is not None or self.expires_at is not None:
                raise MemoryError("retraction has no value or expiry")
        else:
            nonempty(self.value)  # type: ignore[arg-type]
        strings(self.targets)
        strings(self.conditions)
        if bool(self.targets) != (self.kind in ("replace", "retract")):
            raise MemoryError("only replacement/retraction require targets")
        if self.kind == "retract" and self.conditions:
            raise MemoryError("conditional retirement requires a separate policy")
        if type(self.start) is not int or type(self.end) is not int:
            raise MemoryError("span offsets must be integers")
        if not 0 <= self.start < self.end:
            raise MemoryError("invalid source span")
        object.__setattr__(self, "effective_at", timestamp(self.effective_at))
        if self.expires_at is not None:
            object.__setattr__(self, "expires_at", timestamp(self.expires_at))
            if self.expires_at <= self.effective_at:
                raise MemoryError("expiry must follow effective time")


def source_from_dict(data: dict[str, Any]) -> Source:
    return Source(**{**data, "scope": Scope(**data["scope"])})


def event_from_dict(data: dict[str, Any]) -> Event:
    for name in ("targets", "conditions"):
        if name in data and not isinstance(data[name], (list, tuple)):
            raise MemoryError(f"{name} must be an array")
    return Event(
        **{
            **data,
            "scope": Scope(**data["scope"]),
            "targets": tuple(data.get("targets", ())),
            "conditions": tuple(data.get("conditions", ())),
        }
    )


@dataclass(frozen=True)
class RecordedEvent:
    event: Event
    recorded_at: str
    revision: int


@dataclass(frozen=True)
class Snapshot:
    scope: Scope
    valid_at: str
    known_at: str
    revision: int
    sources: tuple[Source, ...]
    events: tuple[RecordedEvent, ...]

    @property
    def hash(self) -> str:
        return digest(asdict(self))
