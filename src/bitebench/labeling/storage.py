"""Transactional synthetic SQLite storage with immutable answers and withdrawal."""

import csv
import hashlib
import json
import secrets
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

from bitebench.core.schemas import TastePair
from bitebench.labeling.protocol import audit


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


class Store:
    def __init__(self, path: Path, protocol: dict, mode: str = "synthetic_only"):
        audit(protocol)
        if mode != "synthetic_only":
            raise ValueError("human collection disabled")
        # Synthetic databases must live in an explicitly synthetic directory.
        if "synthetic" not in path.parts:
            raise ValueError("synthetic database requires synthetic directory")
        path.parent.mkdir(parents=True, exist_ok=True)
        self.protocol = json.loads(json.dumps(protocol))
        self.db = sqlite3.connect(path)
        self.db.execute("PRAGMA foreign_keys=ON")
        self.db.executescript("""
        CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS users (
            user_id TEXT PRIMARY KEY, token_hash TEXT UNIQUE NOT NULL,
            assignment_group TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS displays (
            user_id TEXT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
            pair_id TEXT NOT NULL, payload TEXT NOT NULL,
            PRIMARY KEY(user_id, pair_id));
        CREATE TABLE IF NOT EXISTS answers (
            user_id TEXT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
            pair_id TEXT NOT NULL, stage TEXT NOT NULL, payload TEXT NOT NULL,
            PRIMARY KEY(user_id, pair_id, stage));
        """)
        with self.db:
            self.db.execute(
                "INSERT OR IGNORE INTO metadata VALUES ('split_sha256', ?)",
                (protocol["sha256"],),
            )
        digest = self.db.execute(
            "SELECT value FROM metadata WHERE key='split_sha256'"
        ).fetchone()[0]
        if digest != protocol["sha256"]:
            self.db.close()
            raise ValueError("database bound to a different frozen split")

    def close(self):
        self.db.close()

    def register(self, assignment_group: str = "random") -> tuple[str, str]:
        if assignment_group not in {"random", "active"}:
            raise ValueError("invalid assignment group")
        user_id, token = str(uuid.uuid4()), secrets.token_urlsafe(32)
        with self.db:
            self.db.execute(
                "INSERT INTO users VALUES (?, ?, ?)",
                (user_id, token_hash(token), assignment_group),
            )
        return user_id, token

    def display(self, user_id: str, pair_id: str, reverse: bool, seed: int) -> dict:
        pair = next(
            (p for p in self.protocol["pairs"] if p["pair_id"] == pair_id), None
        )
        if pair is None:
            raise ValueError("pair not in frozen split")
        left, right = pair["left_food_id"], pair["right_food_id"]
        if reverse:
            left, right = right, left
        payload = dict(left_food_id=left, right_food_id=right, display_order_seed=seed)
        encoded = json.dumps(payload, sort_keys=True)
        with self.db:
            existing = self.db.execute(
                "SELECT payload FROM displays WHERE user_id=? AND pair_id=?",
                (user_id, pair_id),
            ).fetchone()
            if existing and existing[0] != encoded:
                raise ValueError("display order already locked")
            self.db.execute(
                "INSERT OR IGNORE INTO displays VALUES (?, ?, ?)",
                (user_id, pair_id, encoded),
            )
        return payload

    def record(self, answer: TastePair) -> bool:
        answer = TastePair.model_validate(answer.model_dump())
        if not answer.is_synthetic:
            raise ValueError("human answers forbidden in synthetic storage")
        timestamp = datetime.fromisoformat(answer.timestamp)
        if timestamp.tzinfo is None or timestamp.utcoffset() is None:
            raise ValueError("timestamp must include timezone")
        pair = next(
            (p for p in self.protocol["pairs"] if p["pair_id"] == answer.pair_id), None
        )
        if pair is None or answer.split != pair["split"]:
            raise ValueError("answer does not match frozen split")
        user = self.db.execute(
            "SELECT assignment_group FROM users WHERE user_id=?", (answer.user_id,)
        ).fetchone()
        display = self.db.execute(
            "SELECT payload FROM displays WHERE user_id=? AND pair_id=?",
            (answer.user_id, answer.pair_id),
        ).fetchone()
        if not user or not display:
            raise ValueError("registered user and display required")
        expected = json.loads(display[0])
        if any(getattr(answer, key) != value for key, value in expected.items()):
            raise ValueError("answer display order mismatch")
        if answer.assignment_group != user[0]:
            raise ValueError("assignment group mismatch")
        expected_policy = (
            "frozen_test"
            if pair["split"] == "test"
            else "coverage_fixed"
            if pair.get("query_phase") == "coverage"
            else user[0]
        )
        if answer.query_policy != expected_policy:
            raise ValueError("query policy mismatch")
        payload = answer.model_dump()
        with self.db:
            self.db.execute("BEGIN IMMEDIATE")
            existing = self.db.execute(
                "SELECT payload FROM answers WHERE user_id=? AND pair_id=? AND stage=?",
                (answer.user_id, answer.pair_id, answer.split),
            ).fetchone()
            if existing:
                previous = json.loads(existing[0])
                if {k: v for k, v in previous.items() if k != "timestamp"} != {
                    k: v for k, v in payload.items() if k != "timestamp"
                }:
                    raise ValueError("answer conflict; original response preserved")
                return False
            self.db.execute(
                "INSERT INTO answers VALUES (?, ?, ?, ?)",
                (
                    answer.user_id,
                    answer.pair_id,
                    answer.split,
                    json.dumps(payload, sort_keys=True),
                ),
            )
        return True

    def export(self, out: Path, split: str = "train") -> int:
        if split not in {"train", "test"}:
            raise ValueError("invalid export split")
        rows = [
            json.loads(r[0])
            for r in self.db.execute(
                "SELECT payload FROM answers WHERE stage=? ORDER BY user_id,pair_id",
                (split,),
            )
        ]
        out.parent.mkdir(parents=True, exist_ok=True)
        with out.open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(TastePair.model_fields))
            writer.writeheader()
            writer.writerows(rows)
        return len(rows)

    def withdraw(self, token: str) -> bool:
        with self.db:
            cursor = self.db.execute(
                "DELETE FROM users WHERE token_hash=?", (token_hash(token),)
            )
        return cursor.rowcount == 1


def now() -> str:
    return datetime.now(timezone.utc).isoformat()
