"""Synthetic questionnaire persistence and resume without exposing test answers."""

import csv
import json
import random
import secrets
import uuid
from pathlib import Path

from bitebench.core.hashing import content_hash
from bitebench.labeling.pair_selector import select_uncertain
from bitebench.labeling.query_model import QueryModel
from bitebench.labeling.questionnaire import (
    AnchorRating,
    MenuChoice,
    audit_questionnaire,
)
from bitebench.labeling.storage import Store, now, token_hash

HIDDEN = "taste_hidden_nutrition"
VISIBLE = "overall_visible_nutrition"


class SurveyStore(Store):
    def __init__(
        self, path: Path, protocol: dict, manifest: dict, mode="synthetic_only"
    ):
        audit_questionnaire(manifest, protocol)
        super().__init__(path, protocol, mode)
        self.manifest = json.loads(json.dumps(manifest))
        with self.db:
            self.db.execute(
                "INSERT OR IGNORE INTO metadata VALUES ('questionnaire_sha256', ?)",
                (manifest["sha256"],),
            )
        digest = self.db.execute(
            "SELECT value FROM metadata WHERE key='questionnaire_sha256'"
        ).fetchone()[0]
        if digest != manifest["sha256"]:
            self.close()
            raise ValueError("database bound to different questionnaire")
        self.db.executescript("""
        CREATE TABLE IF NOT EXISTS assignments (
            user_id TEXT PRIMARY KEY REFERENCES users(user_id) ON DELETE CASCADE,
            slot INTEGER UNIQUE NOT NULL, group_name TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS notices (
            user_id TEXT PRIMARY KEY REFERENCES users(user_id) ON DELETE CASCADE,
            version TEXT NOT NULL, acknowledged_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS queries (
            user_id TEXT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
            pair_id TEXT NOT NULL, payload TEXT NOT NULL, PRIMARY KEY(user_id,pair_id));
        CREATE TABLE IF NOT EXISTS anchors (
            user_id TEXT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
            food_id TEXT NOT NULL, payload TEXT NOT NULL, PRIMARY KEY(user_id,food_id));
        CREATE TABLE IF NOT EXISTS menu_displays (
            user_id TEXT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
            menu_pair_id TEXT NOT NULL, payload TEXT NOT NULL, PRIMARY KEY(user_id,menu_pair_id));
        CREATE TABLE IF NOT EXISTS menu_answers (
            user_id TEXT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
            menu_pair_id TEXT NOT NULL, stage TEXT NOT NULL, payload TEXT NOT NULL,
            PRIMARY KEY(user_id,menu_pair_id,stage));
        """)

    def assignment_group(self, user_id: str) -> str:
        self.require_user(user_id)
        return self.db.execute(
            "SELECT assignment_group FROM users WHERE user_id=?", (user_id,)
        ).fetchone()[0]

    def register_planned(self) -> tuple[str, str]:
        groups = self.protocol.get("assignment_order")
        if groups is None:
            return self.register("random")
        with self.db:
            self.db.execute("BEGIN IMMEDIATE")
            row = self.db.execute(
                "SELECT value FROM metadata WHERE key='assignment_cursor'"
            ).fetchone()
            slot = int(row[0]) if row else 0
            if slot >= len(groups):
                raise ValueError(
                    "synthetic assignment plan exhausted; create a separate run database"
                )
            user, token = str(uuid.uuid4()), secrets.token_urlsafe(32)
            self.db.execute(
                "INSERT INTO users VALUES (?, ?, ?)",
                (user, token_hash(token), groups[slot]),
            )
            self.db.execute(
                "INSERT INTO assignments VALUES (?, ?, ?)", (user, slot, groups[slot])
            )
            self.db.execute(
                "INSERT OR REPLACE INTO metadata VALUES ('assignment_cursor', ?)",
                (str(slot + 1),),
            )
        return user, token

    def training_answers(self, user_id: str) -> list[dict]:
        self.require_user(user_id)
        return [
            json.loads(r[0])
            for r in self.db.execute(
                "SELECT payload FROM answers WHERE user_id=? AND stage='train' ORDER BY pair_id",
                (user_id,),
            )
        ]

    def record(self, answer) -> bool:
        if self.protocol.get("version") == "synthetic_sized_split_v1":
            if answer.split == "train":
                if not self.db.execute(
                    "SELECT 1 FROM queries WHERE user_id=? AND pair_id=?",
                    (answer.user_id, answer.pair_id),
                ).fetchone():
                    raise ValueError("training answer must match an issued query")
            elif (
                answer.split == "test"
                and len(self.training_answers(answer.user_id)) != 40
            ):
                raise ValueError("40 training responses required before test")
        return super().record(answer)

    def acknowledge_demo(self, user_id: str) -> None:
        self.require_user(user_id)
        with self.db:
            self.db.execute(
                "INSERT OR IGNORE INTO notices VALUES (?, ?, ?)",
                (user_id, "synthetic_notice_v1", now()),
            )

    def resume(self, token: str) -> str:
        row = self.db.execute(
            "SELECT user_id FROM users WHERE token_hash=?", (token_hash(token),)
        ).fetchone()
        if not row:
            raise ValueError("invalid or withdrawn token")
        return row[0]

    def require_user(self, user_id: str):
        if not self.db.execute(
            "SELECT 1 FROM users WHERE user_id=?", (user_id,)
        ).fetchone():
            raise ValueError("registered user required")

    def stable_order(self, user_id: str, object_id: str) -> tuple[bool, int]:
        self.require_user(user_id)
        seed = int(content_hash([self.protocol["seed"], user_id, object_id])[:12], 16)
        return bool(random.Random(seed).getrandbits(1)), seed

    def taste_display(self, user_id: str, pair_id: str) -> dict:
        reverse, seed = self.stable_order(user_id, pair_id)
        return self.display(user_id, pair_id, reverse, seed)

    def next_task(self, user_id: str) -> dict:
        self.require_user(user_id)
        # Only IDs are read here; test choices are never passed to query selection.
        answered = {
            r[0]
            for r in self.db.execute(
                "SELECT pair_id FROM answers WHERE user_id=?", (user_id,)
            )
        }
        train_answered = {
            r[0]
            for r in self.db.execute(
                "SELECT pair_id FROM answers WHERE user_id=? AND stage='train'",
                (user_id,),
            )
        }
        full = self.protocol.get("version") == "synthetic_sized_split_v1"
        budget = self.protocol.get(
            "training_budget",
            sum(p["split"] == "train" for p in self.protocol["pairs"]),
        )
        if len(train_answered) < budget:
            pending = self.db.execute(
                "SELECT q.pair_id,q.payload FROM queries q WHERE q.user_id=? AND NOT EXISTS (SELECT 1 FROM answers a WHERE a.user_id=q.user_id AND a.pair_id=q.pair_id) ORDER BY q.rowid LIMIT 1",
                (user_id,),
            ).fetchone()
            if pending:
                pair = next(
                    p for p in self.protocol["pairs"] if p["pair_id"] == pending[0]
                )
                return dict(
                    kind="taste",
                    pair=pair,
                    query_policy=json.loads(pending[1])["query_policy"],
                )
            pool = [
                p
                for p in self.protocol["pairs"]
                if p["split"] == "train" and p["pair_id"] not in train_answered
            ]
            group = self.assignment_group(user_id)
            fixed = (
                [p for p in pool if p.get("query_phase") == "coverage"] if full else []
            )
            state, probabilities = None, {}
            if fixed:
                pair, candidates, policy = fixed[0], fixed, "coverage_fixed"
                version = "synthetic_fixed_coverage_v1"
            else:
                candidates = (
                    [p for p in pool if p.get("query_phase") == "query"]
                    if full
                    else pool
                )
                policy = group
                if group == "active":
                    model = QueryModel()
                    state = model.fit(self.protocol, self.training_answers(user_id))
                    probabilities = {
                        p["pair_id"]: model.probability(
                            p["left_food_id"], p["right_food_id"]
                        )
                        for p in candidates
                    }
                    pair = select_uncertain(
                        self.protocol, probabilities, train_answered
                    )
                    version = "synthetic_uncertainty_bt_v1"
                else:
                    pair = min(
                        candidates,
                        key=lambda p: content_hash(
                            [self.protocol["seed"], user_id, p["pair_id"]]
                        ),
                    )
                    version = "synthetic_random_order_v1"
            trace = dict(
                query_policy=policy,
                policy_version=version,
                candidate_pool_sha256=content_hash(
                    sorted(candidates, key=lambda p: p["pair_id"])
                ),
                candidate_pair_ids=sorted(p["pair_id"] for p in candidates),
                selected_pair_id=pair["pair_id"],
                sequence=len(train_answered) + 1,
                selected_probability=probabilities.get(pair["pair_id"]),
                model_state_sha256=state["sha256"] if state else None,
                model_state=state,
                is_synthetic=True,
            )
            with self.db:
                self.db.execute(
                    "INSERT OR IGNORE INTO queries VALUES (?, ?, ?)",
                    (user_id, pair["pair_id"], json.dumps(trace, sort_keys=True)),
                )
            return dict(kind="taste", pair=pair, query_policy=policy)
        for pair in self.protocol["pairs"]:
            if pair["split"] == "test" and pair["pair_id"] not in answered:
                return dict(kind="taste", pair=pair, query_policy="frozen_test")
        anchors = {
            r[0]
            for r in self.db.execute(
                "SELECT food_id FROM anchors WHERE user_id=?", (user_id,)
            )
        }
        for food_id in self.protocol["anchor_food_ids"]:
            if food_id not in anchors:
                return dict(kind="anchor", food_id=food_id)
        completed = {
            (r[0], r[1])
            for r in self.db.execute(
                "SELECT menu_pair_id,stage FROM menu_answers WHERE user_id=?",
                (user_id,),
            )
        }
        # All hidden tasks precede all visible tasks to avoid nutrition carry-over.
        for stage in [HIDDEN, VISIBLE]:
            for pair in self.manifest["menu_pairs"]:
                if (pair["menu_pair_id"], stage) not in completed:
                    return dict(kind="menu", pair=pair, stage=stage)
        return dict(kind="complete")

    def insert_immutable(self, table: str, keys: dict, payload: dict) -> bool:
        # Table/column names are fixed by internal call sites, never user-provided SQL.
        if table not in {"anchors", "menu_answers"}:
            raise ValueError("invalid answer table")
        columns = list(keys)
        condition = " AND ".join(c + "=?" for c in columns)
        with self.db:
            self.db.execute("BEGIN IMMEDIATE")
            previous = self.db.execute(
                f"SELECT payload FROM {table} WHERE {condition}", tuple(keys.values())
            ).fetchone()
            if previous:
                old = json.loads(previous[0])
                if {k: v for k, v in old.items() if k != "timestamp"} != {
                    k: v for k, v in payload.items() if k != "timestamp"
                }:
                    raise ValueError("answer conflict; original response preserved")
                return False
            values = (*keys.values(), json.dumps(payload, sort_keys=True))
            self.db.execute(
                f"INSERT INTO {table} ({','.join(columns)},payload) VALUES ({','.join('?' for _ in values)})",
                values,
            )
        return True

    def record_anchor(self, answer: AnchorRating) -> bool:
        answer = AnchorRating.model_validate(answer.model_dump())
        self.require_user(answer.user_id)
        if answer.food_id not in self.protocol["anchor_food_ids"]:
            raise ValueError("rating must use frozen training anchors")
        return self.insert_immutable(
            "anchors",
            dict(user_id=answer.user_id, food_id=answer.food_id),
            answer.model_dump(mode="json"),
        )

    def menu_display(self, user_id: str, pair_id: str, stage: str) -> dict:
        self.require_user(user_id)
        if stage not in {HIDDEN, VISIBLE}:
            raise ValueError("invalid stage")
        if stage == VISIBLE and not self.hidden_complete(user_id):
            raise ValueError("all hidden choices required before nutrition is shown")
        pair = next(
            (p for p in self.manifest["menu_pairs"] if p["menu_pair_id"] == pair_id),
            None,
        )
        if pair is None:
            raise ValueError("menu pair not frozen")
        reverse, seed = self.stable_order(user_id, pair_id)
        a, b = pair["menu_a_id"], pair["menu_b_id"]
        if reverse:
            a, b = b, a
        payload = dict(menu_a_id=a, menu_b_id=b, order_randomization=seed)
        encoded = json.dumps(payload, sort_keys=True)
        with self.db:
            row = self.db.execute(
                "SELECT payload FROM menu_displays WHERE user_id=? AND menu_pair_id=?",
                (user_id, pair_id),
            ).fetchone()
            if row and row[0] != encoded:
                raise ValueError("menu display order already locked")
            self.db.execute(
                "INSERT OR IGNORE INTO menu_displays VALUES (?, ?, ?)",
                (user_id, pair_id, encoded),
            )
        return payload

    def hidden_complete(self, user_id: str) -> bool:
        answered = {
            r[0]
            for r in self.db.execute(
                "SELECT menu_pair_id FROM menu_answers WHERE user_id=? AND stage=?",
                (user_id, HIDDEN),
            )
        }
        return answered == {p["menu_pair_id"] for p in self.manifest["menu_pairs"]}

    def record_menu(self, answer: MenuChoice) -> bool:
        answer = MenuChoice.model_validate(answer.model_dump())
        self.require_user(answer.user_id)
        if answer.stage == VISIBLE and not self.hidden_complete(answer.user_id):
            raise ValueError("hidden choices required before visible answers")
        row = self.db.execute(
            "SELECT payload FROM menu_displays WHERE user_id=? AND menu_pair_id=?",
            (answer.user_id, answer.menu_pair_id),
        ).fetchone()
        if not row or any(
            getattr(answer, k) != v for k, v in json.loads(row[0]).items()
        ):
            raise ValueError("menu display mismatch")
        return self.insert_immutable(
            "menu_answers",
            dict(
                user_id=answer.user_id,
                menu_pair_id=answer.menu_pair_id,
                stage=answer.stage,
            ),
            answer.model_dump(mode="json"),
        )

    def summary(self, user_id: str) -> dict:
        self.require_user(user_id)
        taste = self.db.execute(
            "SELECT count(*) FROM answers WHERE user_id=?", (user_id,)
        ).fetchone()[0]
        anchors = self.db.execute(
            "SELECT count(*) FROM anchors WHERE user_id=?", (user_id,)
        ).fetchone()[0]
        records, pairs = self.db.execute(
            "SELECT count(*),count(DISTINCT menu_pair_id) FROM menu_answers WHERE user_id=?",
            (user_id,),
        ).fetchone()
        return dict(
            is_synthetic=True,
            taste_records=taste,
            anchor_records=anchors,
            menu_choice_records=records,
            independent_menu_pairs=pairs,
        )

    def export_extra(self, out: Path, kind: str) -> int:
        table, model = {
            "anchors": ("anchors", AnchorRating),
            "menus": ("menu_answers", MenuChoice),
        }[kind]
        rows = [
            json.loads(r[0])
            for r in self.db.execute(f"SELECT payload FROM {table} ORDER BY user_id")
        ]
        out.parent.mkdir(parents=True, exist_ok=True)
        with out.open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(model.model_fields))
            writer.writeheader()
            writer.writerows(rows)
        return len(rows)
