"""Read raw pilot inputs independently of private gold and resolver-generated state."""

import hashlib
import json
from copy import deepcopy
from pathlib import Path

from .language import fields, sequence
from .models import MemoryError, Scope, Source, digest, nonempty, strings, timestamp


def _pairs(items: list) -> dict:
    result = {}
    for key, value in items:
        if key in result:
            raise MemoryError("duplicate JSON field")
        result[key] = value
    return result


def _nonfinite(value: str) -> None:
    raise MemoryError("nonfinite JSON number")


def read_json(text: str) -> dict:
    value = json.loads(text, object_pairs_hook=_pairs, parse_constant=_nonfinite)
    if not isinstance(value, dict):
        raise MemoryError("expected JSON object")
    return value


def parse_jsonl(text: str) -> list[dict]:
    return [read_json(line) for line in text.splitlines() if line.strip()]


def read_jsonl(path: Path) -> list[dict]:
    return parse_jsonl(path.read_text(encoding="utf-8"))


def read_verified_jsonl(path: Path, expected_hash: str) -> list[dict]:
    # Hash and parse one captured read. A replacement after hashing must not change
    # the inputs or labels associated with that hash.
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected_hash:
        raise MemoryError("JSONL file digest mismatch")
    return parse_jsonl(raw.decode("utf-8"))


def _strings(value: object) -> tuple[str, ...]:
    result = sequence(value)
    strings(result)
    return result


def load_inputs(directory: Path) -> tuple[dict, list[dict]]:
    """Never opens gold.jsonl, even to validate its existence."""
    manifest = read_json((directory / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("schema") != "project-memory.pilot-manifest.v1":
        raise MemoryError("unsupported pilot manifest")
    keys = _strings(manifest["decision_keys"])
    if type(manifest["episode_count"]) is not int or manifest["episode_count"] <= 0:
        raise MemoryError("invalid episode count")
    if not keys:
        raise MemoryError("missing application key vocabulary")
    path = directory / "episodes.jsonl"
    episodes = read_verified_jsonl(path, manifest["sha256"]["episodes.jsonl"])
    seen = set()
    for episode in episodes:
        validate_episode(episode, keys)
        if episode["id"] in seen:
            raise MemoryError("duplicate episode ID")
        seen.add(episode["id"])
    if not episodes or len(episodes) != manifest["episode_count"]:
        raise MemoryError("episode count mismatch")
    return manifest, episodes


def validate_episode(episode: dict, keys: tuple[str, ...]) -> None:
    fields(episode, {"schema", "id", "messages", "task"})
    if episode["schema"] != "project-memory.pilot-episode.v1":
        raise MemoryError("unsupported episode schema")
    nonempty(episode["id"])
    seen = set()
    times = {}
    last = ""
    for message in sequence(episode["messages"]):
        fields(message, {"id", "scope", "actor", "role", "text", "observed_at", "authored_at"})
        Source(
            **{
                k: v for k, v in message.items() if k not in ("scope", "observed_at", "authored_at")
            },
            scope=Scope(**message["scope"]),
        )
        observed = timestamp(message["observed_at"])
        if timestamp(message["authored_at"]) > observed or observed < last:
            raise MemoryError("invalid message time order")
        if message["id"] in seen:
            raise MemoryError("duplicate message ID")
        seen.add(message["id"])
        times[message["id"]] = observed
        last = observed
    task = fields(
        episode["task"],
        {"id", "scope", "visible_until_message_id", "query", "query_at", "required_keys"},
    )
    nonempty(task["id"])
    nonempty(task["query"])
    Scope(**task["scope"])
    required = _strings(task["required_keys"])
    if not required or not set(required) <= set(keys):
        raise MemoryError("task keys outside shared application vocabulary")
    cursor = task["visible_until_message_id"]
    if cursor not in times or timestamp(task["query_at"]) < times[cursor]:
        raise MemoryError("invalid task visibility cursor/time")


def agent_input(episode: dict, keys: tuple[str, ...]) -> dict:
    validate_episode(episode, keys)
    task = episode["task"]
    visible = []
    for message in episode["messages"]:
        if message["scope"] == task["scope"]:
            visible.append(message)
        if message["id"] == task["visible_until_message_id"]:
            break
    return deepcopy(
        {
            "schema": "project-memory.pilot-input.v1",
            "episode_id": episode["id"],
            "allowed_keys": list(keys),
            "messages": visible,
            "task": {k: v for k, v in task.items() if k != "visible_until_message_id"},
        }
    )


def load_gold(directory: Path, manifest: dict, episodes: list[dict]) -> dict[str, dict]:
    path = directory / "gold.jsonl"
    rows = read_verified_jsonl(path, manifest["sha256"]["gold.jsonl"])
    indexed = {e["id"]: e for e in episodes}
    result = {}
    for gold in rows:
        fields(
            gold,
            {
                "schema",
                "episode_id",
                "cluster_id",
                "language",
                "answerable",
                "reversion_applicable",
                "rubric",
                "evidence_message_ids",
                "review_status",
            },
        )
        if gold["schema"] != "project-memory.pilot-gold.v1":
            raise MemoryError("unsupported gold schema")
        id = gold["episode_id"]
        if id not in indexed or id in result:
            raise MemoryError("unknown or duplicate gold episode")
        nonempty(gold["cluster_id"])
        if gold["language"] not in ("ru", "en") or gold["review_status"] != "provisional":
            raise MemoryError("unsupported pilot gold metadata")
        if type(gold["answerable"]) is not bool or type(gold["reversion_applicable"]) is not bool:
            raise MemoryError("gold flags must be boolean")
        fields(gold["rubric"], {"must", "must_not"})
        if not _strings(gold["rubric"]["must"]):
            raise MemoryError("gold needs an explicit correctness rubric")
        _strings(gold["rubric"]["must_not"])
        evidence = _strings(gold["evidence_message_ids"])
        view = agent_input(indexed[id], tuple(manifest["decision_keys"]))
        if not evidence or not set(evidence) <= {m["id"] for m in view["messages"]}:
            raise MemoryError("gold references hidden or unauthorized evidence")
        result[id] = gold
    if set(result) != set(indexed):
        raise MemoryError("gold does not cover every episode")
    return result


def validate_bundle(directory: Path) -> dict:
    manifest, episodes = load_inputs(directory)
    gold = load_gold(directory, manifest, episodes)
    return {
        "status": "schema_validated_not_evaluated",
        "episode_count": len(episodes),
        "clusters": len({g["cluster_id"] for g in gold.values()}),
        "languages": sorted({g["language"] for g in gold.values()}),
        "answerable": sum(g["answerable"] for g in gold.values()),
        "manifest_hash": digest(manifest),
        "independent_gold_review": False,
        "model_calls": 0,
    }
