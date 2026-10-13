"""Transactional, append-only responses and immutable per-session assignments."""

import hashlib
import json
import math
import random
import secrets
import sqlite3
import uuid
from contextlib import closing, contextmanager
from datetime import datetime, timezone
from pathlib import Path

from .bank import Bank, CollectError, canonical, digest


def now():
    return datetime.now(timezone.utc).isoformat()


def token_hash(token):
    return hashlib.sha256(token.encode()).hexdigest()


class Store:
    def __init__(self, path, bank):
        self.path = Path(path).resolve()
        self.bank = bank
        # Runtime data must stay in an explicitly synthetic partition.
        if "synthetic" not in self.path.parts:
            raise CollectError("演示数据库必须置于 synthetic/ 目录，禁止使用真人私有库")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.executescript("""
                CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS sessions(
                    user_id TEXT PRIMARY KEY, token_hash TEXT UNIQUE NOT NULL,
                    created_at TEXT NOT NULL, bank_hash TEXT NOT NULL,
                    bank_json TEXT NOT NULL, display_order_seed INTEGER NOT NULL,
                    assignment_hash TEXT NOT NULL, assignment_group TEXT NOT NULL,
                    status TEXT NOT NULL CHECK(status IN ('active','paused','complete')),
                    is_synthetic INTEGER NOT NULL CHECK(is_synthetic=1));
                CREATE TABLE IF NOT EXISTS consents(
                    user_id TEXT PRIMARY KEY REFERENCES sessions ON DELETE CASCADE,
                    version TEXT NOT NULL, text TEXT NOT NULL, text_hash TEXT NOT NULL,
                    accepted_at TEXT NOT NULL, adult INTEGER NOT NULL CHECK(adult=1),
                    voluntary INTEGER NOT NULL CHECK(voluntary=1));
                CREATE TABLE IF NOT EXISTS assignments(
                    user_id TEXT REFERENCES sessions ON DELETE CASCADE,
                    ordinal INTEGER NOT NULL, question_id TEXT NOT NULL,
                    question_json TEXT NOT NULL, presented_at TEXT,
                    PRIMARY KEY(user_id, question_id), UNIQUE(user_id, ordinal));
                CREATE TABLE IF NOT EXISTS responses(
                    user_id TEXT NOT NULL, question_id TEXT NOT NULL,
                    payload_json TEXT NOT NULL, timestamp TEXT NOT NULL,
                    reaction_time_ms REAL NOT NULL CHECK(reaction_time_ms>=0),
                    PRIMARY KEY(user_id, question_id),
                    FOREIGN KEY(user_id,question_id) REFERENCES assignments ON DELETE CASCADE);
            """)
            meta = dict(db.execute("SELECT key,value FROM meta"))
            if meta and meta != {"schema_version": "1", "provenance": "synthetic"}:
                raise CollectError("数据库版本或来源不兼容；禁止混用")
            db.executemany(
                "INSERT OR IGNORE INTO meta VALUES (?,?)",
                [("schema_version", "1"), ("provenance", "synthetic")],
            )
        try:
            self.path.chmod(0o600)
        except OSError:
            pass  # Windows ACLs are configured by the local operator, not POSIX mode.

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("PRAGMA synchronous=FULL")
        db.execute("PRAGMA secure_delete=ON")
        try:
            with db:
                yield db
        finally:
            db.close()

    def create(self, consent):
        required = {"adult", "voluntary", "demo_understood", "consent_hash"}
        if set(consent) != required or any(
            consent.get(k) is not True for k in required - {"consent_hash"}
        ):
            raise CollectError("必须确认 18+、自愿以及合成演示说明")
        if consent["consent_hash"] != digest(self.bank.document["consent"]):
            raise CollectError("说明版本已改变，请重新阅读")
        user_id, token, seed = (
            str(uuid.uuid4()),
            secrets.token_urlsafe(32),
            secrets.randbits(32),
        )
        rng = random.Random(seed)
        assignments = json.loads(canonical(self.bank.questions))
        for q in assignments:
            if q["kind"] == "pair":
                a, b = q.pop("food_a_id"), q.pop("food_b_id")
                q["left_food_id"], q["right_food_id"] = (
                    (a, b) if rng.getrandbits(1) else (b, a)
                )
                q["test_stratum"] = (
                    (
                        "cold_food"
                        if {a, b} & set(self.bank.document["heldout_food_ids"])
                        else "known_food"
                    )
                    if q["split"] == "test"
                    else None
                )
        stamp = now()
        c = self.bank.document["consent"]
        with self.connect() as db:
            db.execute(
                "INSERT INTO sessions VALUES (?,?,?,?,?,?,?,?,?,1)",
                (
                    user_id,
                    token_hash(token),
                    stamp,
                    self.bank.sha256,
                    canonical(self.bank.document),
                    seed,
                    digest(assignments),
                    "synthetic_fixed",
                    "active",
                ),
            )
            db.execute(
                "INSERT INTO consents VALUES (?,?,?,?,?,1,1)",
                (user_id, c["version"], c["text"], digest(c), stamp),
            )
            db.executemany(
                "INSERT INTO assignments VALUES (?,?,?,?,NULL)",
                [
                    (user_id, i, q["question_id"], canonical(q))
                    for i, q in enumerate(assignments)
                ],
            )
        return {
            "user_id": user_id,
            "token": token,
            "is_synthetic": True,
            "research_eligible": False,
        }

    def authenticate(self, db, token):
        if not isinstance(token, str) or not 20 <= len(token) <= 100:
            raise CollectError("恢复/撤回码无效")
        s = db.execute(
            "SELECT * FROM sessions WHERE token_hash=?", (token_hash(token),)
        ).fetchone()
        if s is None:
            raise CollectError("恢复/撤回码无效")
        return s

    def verify(self, db, session):
        bank = Bank(json.loads(session["bank_json"]))
        rows = db.execute(
            "SELECT * FROM assignments WHERE user_id=? ORDER BY ordinal",
            (session["user_id"],),
        ).fetchall()
        if (
            bank.sha256 != session["bank_hash"]
            or digest([json.loads(r["question_json"]) for r in rows])
            != session["assignment_hash"]
        ):
            raise CollectError("冻结题库或展示顺序完整性检查失败")
        return bank, rows

    def state(self, token, resume=False):
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            s = self.authenticate(db, token)
            bank, rows = self.verify(db, s)
            if resume and s["status"] == "paused":
                db.execute(
                    "UPDATE sessions SET status='active' WHERE user_id=?",
                    (s["user_id"],),
                )
            done = {
                r[0]
                for r in db.execute(
                    "SELECT question_id FROM responses WHERE user_id=?", (s["user_id"],)
                )
            }
            current = next((r for r in rows if r["question_id"] not in done), None)
            status = (
                "complete" if current is None else ("active" if resume else s["status"])
            )
            question = None
            if current is not None and status == "active":
                stamp = now()
                db.execute(
                    "UPDATE assignments SET presented_at=COALESCE(presented_at,?) WHERE user_id=? AND question_id=?",
                    (stamp, s["user_id"], current["question_id"]),
                )
                q = json.loads(current["question_json"])
                # No split, heldout IDs, future questions or labels in participant payload.
                question = {
                    "question_id": q["question_id"],
                    "kind": q["kind"],
                    "number": current["ordinal"] + 1,
                }
                if q["kind"] == "pair":
                    question.update(
                        left=bank.display_food(q["left_food_id"]),
                        right=bank.display_food(q["right_food_id"]),
                    )
                else:
                    question["food"] = bank.display_food(q["food_id"])
            return {
                "user_id": s["user_id"],
                "status": status,
                "answered": len(done),
                "total": 58,
                "question": question,
                "is_synthetic": True,
                "research_eligible": False,
            }

    def save(self, token, question_id, payload):
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            s = self.authenticate(db, token)
            _, rows = self.verify(db, s)
            row = next((r for r in rows if r["question_id"] == question_id), None)
            if row is None:
                raise CollectError("题目不属于此会话")
            q = json.loads(row["question_json"])
            self.validate_answer(q, payload)
            encoded = canonical(payload)
            existing = db.execute(
                "SELECT payload_json FROM responses WHERE user_id=? AND question_id=?",
                (s["user_id"], question_id),
            ).fetchone()
            if existing:
                if existing[0] != encoded:
                    raise CollectError("已保存回答不可覆盖；原记录保留")
                return {"saved": True, "duplicate": True}
            if s["status"] != "active":
                raise CollectError("会话已暂停或完成")
            current = db.execute(
                "SELECT a.question_id FROM assignments a LEFT JOIN responses r USING(user_id,question_id) WHERE a.user_id=? AND r.question_id IS NULL ORDER BY ordinal LIMIT 1",
                (s["user_id"],),
            ).fetchone()
            if current[0] != question_id or row["presented_at"] is None:
                raise CollectError("只能提交当前已展示题目")
            stamp = now()
            elapsed = max(
                0,
                (
                    datetime.fromisoformat(stamp)
                    - datetime.fromisoformat(row["presented_at"])
                ).total_seconds()
                * 1000,
            )
            db.execute(
                "INSERT INTO responses VALUES (?,?,?,?,?)",
                (s["user_id"], question_id, encoded, stamp, elapsed),
            )
            count = db.execute(
                "SELECT COUNT(*) FROM responses WHERE user_id=?", (s["user_id"],)
            ).fetchone()[0]
            if count == 58:
                db.execute(
                    "UPDATE sessions SET status='complete' WHERE user_id=?",
                    (s["user_id"],),
                )
        return {"saved": True, "duplicate": False}

    @staticmethod
    def validate_answer(q, payload):
        if not isinstance(payload, dict):
            raise CollectError("回答格式无效")
        if q["kind"] == "pair":
            if set(payload) != {
                "choice",
                "seen_left",
                "seen_right",
                "self_reported_hunger",
            } or payload["choice"] not in ("left", "right", "tie", "skip"):
                raise CollectError("选择必须为 left/right/tie/skip")
            if any(
                payload[k] is not None and type(payload[k]) is not bool
                for k in ("seen_left", "seen_right")
            ):
                raise CollectError("是否吃过应为布尔值或 null")
            h = payload["self_reported_hunger"]
            if h is not None and (type(h) is not int or not 0 <= h <= 10):
                raise CollectError("自愿饥饿水平应为 0–10 整数或 null")
        else:
            if set(payload) != {"rating", "skip"} or type(payload["skip"]) is not bool:
                raise CollectError("评分格式无效")
            r = payload["rating"]
            if payload["skip"]:
                if r is not None:
                    raise CollectError("跳过的评分应为 null")
            elif (
                type(r) not in (int, float) or not math.isfinite(r) or not 0 <= r <= 10
            ):
                raise CollectError("预期美味评分应在 0–10")

    def pause(self, token):
        with self.connect() as db:
            s = self.authenticate(db, token)
            db.execute(
                "UPDATE sessions SET status='paused' WHERE user_id=? AND status='active'",
                (s["user_id"],),
            )
        return {"paused": True}

    def withdraw(self, token):
        with self.connect() as db:
            s = self.authenticate(db, token)
            db.execute("DELETE FROM sessions WHERE user_id=?", (s["user_id"],))
        with self.connect() as db:
            db.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        return {"deleted": True}

    def summary(self):
        with self.connect() as db:
            rows = db.execute(
                "SELECT s.user_id,s.created_at,s.status,s.bank_hash,COUNT(r.question_id) AS answered FROM sessions s LEFT JOIN responses r USING(user_id) GROUP BY s.user_id ORDER BY s.created_at DESC"
            ).fetchall()
        return {
            "sessions": [dict(r) for r in rows],
            "synthetic_sessions": len(rows),
            "real_participants": 0,
            "is_synthetic": True,
            "human_study_status": "BLOCKED",
            "reason_code": "FORMAL_COLLECTION_DISABLED",
        }

    def backup(self, target):
        target = Path(target).resolve()
        if "synthetic" not in target.parts or target == self.path:
            raise CollectError("备份必须写入独立 synthetic/ 路径")
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("xb"):
            pass
        with self.connect() as source, closing(sqlite3.connect(target)) as dest:
            source.backup(dest)
        target.chmod(0o600)
