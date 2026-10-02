"""Snapshot-bound structural receipts and explicit dependency invalidation."""

from dataclasses import asdict, dataclass

from .models import MemoryError, Scope, Snapshot, digest, nonempty, strings
from .resolve import resolve
from .store import Store


@dataclass(frozen=True)
class Claim:
    key: str
    value: str
    supports: tuple[str, ...]
    conditions: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        nonempty(self.key)
        nonempty(self.value)
        strings(self.supports)
        strings(self.conditions)


def verify(
    snapshot: Snapshot,
    claimed_snapshot_hash: str,
    claims: tuple[Claim, ...],
    required_keys: tuple[str, ...],
    prose: str | None = None,
) -> dict:
    strings(required_keys)
    if not required_keys:
        raise MemoryError("verification requires a nonempty task contract")
    if prose is not None and not isinstance(prose, str):
        raise MemoryError("prose must be a string")
    errors = []
    if claimed_snapshot_hash != snapshot.hash:
        errors.append({"code": "snapshot_mismatch"})
    keys = [c.key for c in claims]
    if len(set(keys)) != len(keys):
        errors.append({"code": "duplicate_claim_keys"})
    for key in sorted(set(required_keys) - set(keys)):
        errors.append({"code": "missing_required_claim", "key": key})
    sources = {s.id: s for s in snapshot.sources}
    events = {r.event.id: r.event for r in snapshot.events}
    for claim in claims:
        state = resolve(snapshot, claim.key)
        if state.status != "active":
            errors.append({"code": "decision_not_active", "key": claim.key, "status": state.status})
            continue
        if claim.value != state.value or tuple(sorted(claim.conditions)) != state.conditions:
            errors.append({"code": "value_or_conditions_mismatch", "key": claim.key})
        if not claim.supports or not set(claim.supports) <= set(state.supports):
            errors.append({"code": "invalid_support", "key": claim.key})
            continue
        for id in claim.supports:
            event = events[id]
            source = sources.get(event.source_id)
            if (
                source is None
                or source.scope != snapshot.scope
                or source.role != "owner"
                or source.hash != event.source_hash
                or event.end > len(source.text)
            ):
                errors.append({"code": "invalid_source_binding", "key": claim.key})
    return {
        "schema": "project-memory.receipt.v1",
        "scope": asdict(snapshot.scope),
        "snapshot_hash": snapshot.hash,
        "revision": snapshot.revision,
        "valid_at": snapshot.valid_at,
        "known_at": snapshot.known_at,
        "proposal_hash": digest(
            {
                "claims": [asdict(c) for c in claims],
                "prose": prose,
                "required_keys": required_keys,
                "claimed_snapshot_hash": claimed_snapshot_hash,
            }
        ),
        "structural_status": "fail" if errors else "pass",
        "errors": errors,
        "semantic_status": "not_checked",
        "prose_certified": False,
        "dependency_completeness": "not_checked",
    }


class Memory:
    def __init__(self, store: Store):
        self.store = store

    def save_artifact(
        self, snapshot: Snapshot, id: str, content: str, dependency_keys: tuple[str, ...]
    ) -> int:
        nonempty(id)
        nonempty(content)
        strings(dependency_keys)
        if not dependency_keys:
            raise MemoryError("artifact must declare dependencies")
        dependencies = {}
        dependency_states = {}
        for key in dependency_keys:
            state = resolve(snapshot, key)
            if state.status != "active":
                raise MemoryError(f"artifact dependency is not active: {key}")
            dependencies[key] = state.fingerprint
            dependency_states[key] = asdict(state)
        payload = {
            "id": id,
            "content": content,
            "content_hash": digest(content),
            "snapshot_hash": snapshot.hash,
            "dependencies": dependencies,
            "dependency_states": dependency_states,
            "basis_snapshot": {
                "scope": asdict(snapshot.scope),
                "revision": snapshot.revision,
                "valid_at": snapshot.valid_at,
                "known_at": snapshot.known_at,
            },
            "dependency_completeness": "not_checked",
        }
        return self.store.save_artifact(snapshot.scope, id, payload, snapshot.revision)

    def impact_report(
        self, snapshot: Snapshot, *, limit: int = 100, after_revision: int = 0
    ) -> dict:
        """One revision-bound page of affected work. Caller owns scope authorization.

        Resume with the same snapshot and next_after_revision. No artifact, receipt,
        or publishing permission is changed by this diagnostic.
        """
        from .impact import artifact_impact

        page, cursor = self.store.artifact_page(
            snapshot, limit=limit, after_revision=after_revision
        )
        return {
            "schema": "project-memory.impact-report.v1",
            "scope": asdict(snapshot.scope),
            "snapshot_hash": snapshot.hash,
            "revision": snapshot.revision,
            "valid_at": snapshot.valid_at,
            "known_at": snapshot.known_at,
            "artifacts": [artifact_impact(snapshot, payload) for payload in page],
            "next_after_revision": cursor,
            "coverage": "declared_dependencies_only",
            "authorizes_action": False,
        }

    def check_artifact(self, scope: Scope, id: str, snapshot: Snapshot) -> dict:
        if scope != snapshot.scope:
            raise MemoryError("artifact snapshot scope mismatch")
        artifact = self.store.artifact(scope, id, snapshot.known_at)
        changed = [
            key
            for key, previous in artifact["dependencies"].items()
            if resolve(snapshot, key).fingerprint != previous
        ]
        return {
            "id": id,
            "status": "stale" if changed else "unchanged_dependencies",
            "changed_keys": sorted(changed),
            "snapshot_hash": snapshot.hash,
            "content_hash": artifact["content_hash"],
            "semantic_status": "not_checked",
        }
