"""Local trusted-caller storage; direct references enforce the same scope as queries."""

import json
import sqlite3
from collections.abc import Callable
from dataclasses import asdict
from pathlib import Path
from typing import Any

from .models import (
    Event,
    MemoryError,
    RecordedEvent,
    RevisionConflict,
    Scope,
    Snapshot,
    Source,
    canonical,
    event_from_dict,
    now,
    source_from_dict,
    timestamp,
)


class Store:
    def __init__(self, path: str | Path, clock: Callable[[], str] = now):
        self.clock = clock
        self.db = sqlite3.connect(str(path), isolation_level=None, timeout=10)
        self.db.row_factory = sqlite3.Row
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS records (
                project TEXT NOT NULL, scope TEXT NOT NULL, kind TEXT NOT NULL,
                id TEXT NOT NULL, payload TEXT NOT NULL, recorded_at TEXT NOT NULL,
                revision INTEGER NOT NULL,
                PRIMARY KEY(scope, kind, id), UNIQUE(project, revision)
            );
            CREATE INDEX IF NOT EXISTS records_project_time
                ON records(project, recorded_at);
            CREATE TABLE IF NOT EXISTS language_traces (
                scope TEXT NOT NULL, id TEXT NOT NULL, payload TEXT NOT NULL,
                PRIMARY KEY(scope, id)
            );
        """)

    def close(self) -> None:
        self.db.close()

    def current_snapshot(self, scope: Scope) -> Snapshot:
        """Read current valid time with all observations through this local read boundary.

        Monotonic observation timestamps can be slightly ahead of a coarse/regressing
        clock. Include those records without turning their observation time into valid time.
        Admission still checks the project revision if a writer races this read.
        """
        valid_at = timestamp(self.clock())
        last = self.db.execute(
            "SELECT MAX(recorded_at) FROM records WHERE project=?", (scope.project_id,)
        ).fetchone()[0]
        return self.snapshot(scope, valid_at, max(valid_at, last or valid_at))

    def _row(self, scope: Scope, kind: str, id: str) -> sqlite3.Row:
        row = self.db.execute(
            "SELECT * FROM records WHERE scope=? AND kind=? AND id=?",
            (scope.id, kind, id),
        ).fetchone()
        if row is None:
            raise MemoryError("reference not found in requested scope")
        return row

    def revision(self, scope: Scope) -> int:
        return int(
            self.db.execute(
                "SELECT COALESCE(MAX(revision),0) FROM records WHERE project=?",
                (scope.project_id,),
            ).fetchone()[0]
        )

    def append_source(self, source: Source, expected_revision: int) -> int:
        return self._append(source.scope, "source", source.id, asdict(source), expected_revision)

    def append_event(self, event: Event, expected_revision: int) -> int:
        return self._append(
            event.scope,
            "event",
            event.id,
            asdict(event),
            expected_revision,
            lambda: self._validate_event(event),
        )

    def _validate_event(self, event: Event) -> None:
        source = source_from_dict(
            json.loads(self._row(event.scope, "source", event.source_id)["payload"])
        )
        if source.hash != event.source_hash or event.end > len(source.text):
            raise MemoryError("source digest or span mismatch")
        if event.kind in ("adopt", "replace", "retract") and source.role != "owner":
            raise MemoryError("source role cannot authorize decisions")
        for target_id in event.targets:
            target = event_from_dict(
                json.loads(self._row(event.scope, "event", target_id)["payload"])
            )
            if (
                target.key != event.key
                or target.kind not in ("adopt", "replace")
                or target.effective_at > event.effective_at
            ):
                raise MemoryError("invalid retirement target")

    def _observation(self, scope: Scope) -> str:
        from datetime import datetime, timedelta

        observed = timestamp(self.clock())
        last = self.db.execute(
            "SELECT MAX(recorded_at) FROM records WHERE project=?", (scope.project_id,)
        ).fetchone()[0]
        if last is not None and observed <= last:
            observed = timestamp(
                (datetime.fromisoformat(last) + timedelta(microseconds=1)).isoformat()
            )
        return observed

    def append_reviewed_batch(
        self,
        events: tuple[Event, ...],
        admission_id: str,
        proof: dict[str, Any],
        expected_revision: int,
    ) -> int:
        """Trusted application boundary; language.admitted_events checks semantic receipts.

        Batch events share one observation time: as-of reads cannot see half a batch.
        """
        from .models import nonempty

        nonempty(admission_id)
        if not events or type(expected_revision) is not int or expected_revision < 0:
            raise MemoryError("invalid batch or revision")
        scope = events[0].scope
        if any(e.scope != scope for e in events) or len({e.id for e in events}) != len(events):
            raise MemoryError("batch scope mismatch or duplicate events")
        payload = canonical({"events": [asdict(e) for e in events], "proof": proof})
        self.db.execute("BEGIN IMMEDIATE")
        try:
            prior = self.db.execute(
                "SELECT payload,revision FROM records WHERE scope=? AND kind='admission' AND id=?",
                (scope.id, admission_id),
            ).fetchone()
            if prior is not None:
                if prior["payload"] != payload:
                    raise MemoryError("admission ID reused with different content")
                self.db.execute("COMMIT")
                return int(prior["revision"])
            revision = self.revision(scope)
            if revision != expected_revision:
                raise RevisionConflict("project changed before language admission")
            # Validate all targets against pre-batch state. No hidden order dependency.
            for event in events:
                self._validate_event(event)
                if self.db.execute(
                    "SELECT 1 FROM records WHERE scope=? AND kind='event' AND id=?",
                    (scope.id, event.id),
                ).fetchone():
                    raise MemoryError("event already admitted; reuse original admission ID")
            observed = self._observation(scope)
            records = [("event", e.id, canonical(asdict(e))) for e in events]
            records.append(("admission", admission_id, payload))
            for kind, id, encoded in records:
                revision += 1
                self.db.execute(
                    "INSERT INTO records VALUES (?,?,?,?,?,?,?)",
                    (scope.project_id, scope.id, kind, id, encoded, observed, revision),
                )
            self.db.execute("COMMIT")
            return revision
        except BaseException:
            if self.db.in_transaction:
                self.db.execute("ROLLBACK")
            raise

    def save_language_trace(self, scope: Scope, id: str, payload: dict[str, Any]) -> None:
        from .models import nonempty

        nonempty(id)
        encoded = canonical(payload)
        self.db.execute("BEGIN IMMEDIATE")
        try:
            previous = self.db.execute(
                "SELECT payload FROM language_traces WHERE scope=? AND id=?", (scope.id, id)
            ).fetchone()
            if previous is not None and previous["payload"] != encoded:
                raise MemoryError("trace ID reused with different content")
            if previous is None:
                self.db.execute(
                    "INSERT INTO language_traces VALUES (?,?,?)", (scope.id, id, encoded)
                )
            self.db.execute("COMMIT")
        except BaseException:
            if self.db.in_transaction:
                self.db.execute("ROLLBACK")
            raise

    def language_trace(self, scope: Scope, id: str) -> dict[str, Any]:
        row = self.db.execute(
            "SELECT payload FROM language_traces WHERE scope=? AND id=?", (scope.id, id)
        ).fetchone()
        if row is None:
            raise MemoryError("trace not found in requested scope")
        return json.loads(row["payload"])  # type: ignore[no-any-return]

    def _append(
        self,
        scope: Scope,
        kind: str,
        id: str,
        payload: dict[str, Any],
        expected_revision: int,
        validate: Callable[[], None] = lambda: None,
    ) -> int:
        if type(expected_revision) is not int or expected_revision < 0:
            raise MemoryError("expected_revision must be a nonnegative integer")
        encoded = canonical(payload)
        self.db.execute("BEGIN IMMEDIATE")
        try:
            previous = self.db.execute(
                "SELECT payload,revision FROM records WHERE scope=? AND kind=? AND id=?",
                (scope.id, kind, id),
            ).fetchone()
            if previous is not None:
                if previous["payload"] != encoded:
                    raise MemoryError("ID reused with different content")
                self.db.execute("COMMIT")
                return int(previous["revision"])
            revision = self.revision(scope)
            if revision != expected_revision:
                raise RevisionConflict(f"expected revision {expected_revision}; current {revision}")
            validate()
            # Strict observation order makes an already-issued known_at snapshot stable.
            observed = self._observation(scope)
            self.db.execute(
                "INSERT INTO records VALUES (?,?,?,?,?,?,?)",
                (scope.project_id, scope.id, kind, id, encoded, observed, revision + 1),
            )
            self.db.execute("COMMIT")
            return revision + 1
        except BaseException:
            if self.db.in_transaction:
                self.db.execute("ROLLBACK")
            raise

    def snapshot(
        self, scope: Scope, valid_at: str, known_at: str, *, revision_limit: int | None = None
    ) -> Snapshot:
        valid_at, known_at = timestamp(valid_at), timestamp(known_at)
        if revision_limit is not None and (type(revision_limit) is not int or revision_limit < 0):
            raise MemoryError("invalid revision limit")
        limit = revision_limit if revision_limit is not None else 9223372036854775807
        # A guarded local action may own a write transaction around this read.
        # Never commit or roll back the caller's transaction from a snapshot helper.
        owns_transaction = not self.db.in_transaction
        if owns_transaction:
            self.db.execute("BEGIN")
        try:
            revision = int(
                self.db.execute(
                    "SELECT COALESCE(MAX(revision),0) FROM records "
                    "WHERE project=? AND recorded_at<=? AND revision<=?",
                    (scope.project_id, known_at, limit),
                ).fetchone()[0]
            )
            if revision_limit is not None and revision:
                partial = self.db.execute(
                    "SELECT 1 FROM records WHERE project=? AND revision>? AND recorded_at="
                    "(SELECT recorded_at FROM records WHERE project=? AND revision=?) LIMIT 1",
                    (scope.project_id, limit, scope.project_id, revision),
                ).fetchone()
                if partial:
                    raise MemoryError("revision limit splits an atomic admission batch")
            rows = self.db.execute(
                "SELECT * FROM records WHERE scope=? AND recorded_at<=? "
                "AND revision<=? ORDER BY revision",
                (scope.id, known_at, limit),
            ).fetchall()
            if owns_transaction:
                self.db.execute("COMMIT")
        except BaseException:
            if owns_transaction:
                self.db.execute("ROLLBACK")
            raise
        sources = tuple(
            source_from_dict(json.loads(r["payload"])) for r in rows if r["kind"] == "source"
        )
        events = tuple(
            RecordedEvent(
                event_from_dict(json.loads(r["payload"])), r["recorded_at"], r["revision"]
            )
            for r in rows
            if r["kind"] == "event"
        )
        return Snapshot(scope, valid_at, known_at, revision, sources, events)

    def save_artifact(
        self, scope: Scope, id: str, payload: dict[str, Any], expected_revision: int
    ) -> int:
        return self._append(scope, "artifact", id, payload, expected_revision)

    def artifact(self, scope: Scope, id: str, known_at: str) -> dict[str, Any]:
        row = self._row(scope, "artifact", id)
        if row["recorded_at"] > timestamp(known_at):
            raise MemoryError("artifact not observed at requested known_at")
        return json.loads(row["payload"])  # type: ignore[no-any-return]

    def artifact_page(
        self, snapshot: Snapshot, *, limit: int = 100, after_revision: int = 0
    ) -> tuple[list[dict[str, Any]], int | None]:
        """Read immutable artifact records visible at both snapshot boundaries."""
        if type(limit) is not int or not 1 <= limit <= 1000:
            raise MemoryError("artifact page limit must be an integer from 1 to 1000")
        if type(after_revision) is not int or not 0 <= after_revision <= snapshot.revision:
            raise MemoryError("invalid artifact page revision cursor")
        rows = self.db.execute(
            "SELECT payload, revision FROM records WHERE scope=? AND kind='artifact' "
            "AND recorded_at<=? AND revision<=? AND revision>? ORDER BY revision LIMIT ?",
            (
                snapshot.scope.id,
                timestamp(snapshot.known_at),
                snapshot.revision,
                after_revision,
                limit + 1,
            ),
        ).fetchall()
        cursor = int(rows[limit - 1]["revision"]) if len(rows) > limit else None
        return [json.loads(r["payload"]) for r in rows[:limit]], cursor
