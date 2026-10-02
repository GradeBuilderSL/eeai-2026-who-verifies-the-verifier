"""Durable admission reservations. Unknown provider charges never refund capacity."""

import math
import sqlite3
from dataclasses import asdict, dataclass
from uuid import uuid4

from .language import ModelRequest
from .models import MemoryError, canonical, nonempty


@dataclass(frozen=True)
class RunLimits:
    model: str
    max_calls: int
    max_input_chars: int
    max_output_tokens: int
    timeout_seconds: float = 45.0
    max_response_chars: int = 100000
    provider: str = "openai"
    reasoning_effort: str | None = None

    def __post_init__(self) -> None:
        nonempty(self.model)
        allowed = {
            "openai": (None, "none", "low", "medium", "high", "xhigh", "max"),
            "deepseek": (None, "none", "low", "high", "max"),
        }
        if self.provider not in allowed or self.reasoning_effort not in allowed[self.provider]:
            raise MemoryError("unsupported provider or reasoning effort")
        for value in (
            self.max_calls,
            self.max_input_chars,
            self.max_output_tokens,
            self.max_response_chars,
        ):
            if type(value) is not int or not 0 < value <= 1_000_000_000:
                raise MemoryError("invalid run budget")
        if (
            type(self.timeout_seconds) not in (int, float)
            or not math.isfinite(self.timeout_seconds)
            or not 0 < self.timeout_seconds <= 120
        ):
            raise MemoryError("timeout must be finite and within 120 seconds")


class CallBudget:
    def __init__(self, db: sqlite3.Connection, run_id: str, limits: RunLimits):
        nonempty(run_id)
        self.db, self.run_id, self.limits = db, run_id, limits
        db.executescript("""
            CREATE TABLE IF NOT EXISTS model_runs (
                id TEXT PRIMARY KEY, limits_json TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS model_calls (
                id TEXT PRIMARY KEY, run_id TEXT NOT NULL, request_hash TEXT NOT NULL,
                input_chars INTEGER NOT NULL, output_reservation INTEGER NOT NULL,
                result_json TEXT
            );
            CREATE INDEX IF NOT EXISTS model_calls_run ON model_calls(run_id);
        """)
        db.execute("BEGIN IMMEDIATE")
        try:
            previous = db.execute(
                "SELECT limits_json FROM model_runs WHERE id=?", (run_id,)
            ).fetchone()
            encoded = canonical(asdict(limits))
            if previous is not None and previous[0] != encoded:
                raise MemoryError("run ID already bound to different model or limits")
            if previous is None:
                db.execute("INSERT INTO model_runs VALUES (?,?)", (run_id, encoded))
            db.execute("COMMIT")
        except BaseException:
            if db.in_transaction:
                db.execute("ROLLBACK")
            raise

    def reserve(self, request: ModelRequest, *, extra_input_chars: int = 0) -> str:
        if type(extra_input_chars) is not int or extra_input_chars < 0:
            raise MemoryError("invalid provider schema overhead")
        size = len(request.instructions) + len(request.payload_json) + extra_input_chars
        self.db.execute("BEGIN IMMEDIATE")
        try:
            count, chars, output = self.db.execute(
                "SELECT COUNT(*),COALESCE(SUM(input_chars),0),"
                "COALESCE(SUM(output_reservation),0) FROM model_calls WHERE run_id=?",
                (self.run_id,),
            ).fetchone()
            if (
                count + 1 > self.limits.max_calls
                or chars + size > self.limits.max_input_chars
                or output + request.max_output_tokens > self.limits.max_output_tokens
            ):
                raise MemoryError("run budget exhausted before provider call")
            id = str(uuid4())
            self.db.execute(
                "INSERT INTO model_calls VALUES (?,?,?,?,?,NULL)",
                (id, self.run_id, request.hash, size, request.max_output_tokens),
            )
            self.db.execute("COMMIT")
            return id
        except BaseException:
            if self.db.in_transaction:
                self.db.execute("ROLLBACK")
            raise

    def finish(self, id: str, result: dict) -> None:
        cursor = self.db.execute(
            "UPDATE model_calls SET result_json=? WHERE id=? AND run_id=? AND result_json IS NULL",
            (canonical(result), id, self.run_id),
        )
        if cursor.rowcount != 1:
            raise MemoryError("call result missing or already recorded")

    def report(self) -> dict:
        import json

        rows = self.db.execute(
            "SELECT id,request_hash,input_chars,output_reservation,result_json "
            "FROM model_calls WHERE run_id=? ORDER BY rowid",
            (self.run_id,),
        ).fetchall()
        calls = [
            {
                "call_id": r[0],
                "request_hash": r[1],
                "input_chars": r[2],
                "output_reservation": r[3],
                "result": json.loads(r[4]) if r[4] else None,
            }
            for r in rows
        ]
        return {
            "run_id": self.run_id,
            "limits": asdict(self.limits),
            "calls": calls,
            "calls_reserved": len(calls),
            "input_chars_reserved": sum(c["input_chars"] for c in calls),
            "output_tokens_reserved": sum(c["output_reservation"] for c in calls),
            "unknown_usage_calls": sum(
                c["result"] is None or not c["result"]["usage_known"] for c in calls
            ),
        }
