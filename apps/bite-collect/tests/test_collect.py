import copy
import csv
import io
import json
import sqlite3
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
import zipfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from bite_collect.bank import Bank, CollectError, digest  # noqa: E402
from bite_collect.exporter import export_bundle, write_export  # noqa: E402
from bite_collect.server import LocalServer  # noqa: E402
from bite_collect.store import Store  # noqa: E402


class StoreFixture(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.bank = Bank.load(ROOT / "fixtures/synthetic/questionnaire.json")
        self.path = Path(self.temp.name) / "synthetic/collect.sqlite3"
        self.store = Store(self.path, self.bank)

    def tearDown(self):
        self.temp.cleanup()

    def create(self):
        return self.store.create(
            {
                "adult": True,
                "voluntary": True,
                "demo_understood": True,
                "consent_hash": digest(self.bank.document["consent"]),
            }
        )

    def answer(self, token, choice="left"):
        state = self.store.state(token)
        q = state["question"]
        payload = (
            {
                "choice": choice,
                "seen_left": None,
                "seen_right": True,
                "self_reported_hunger": None,
            }
            if q["kind"] == "pair"
            else {"rating": 7.5, "skip": False}
        )
        return self.store.save(token, q["question_id"], payload)


class CollectTests(StoreFixture):
    def test_fixture_contract(self):
        self.assertEqual(len(self.bank.questions), 58)
        self.assertTrue(
            all(f["energy_kcal_per_100g"] is None for f in self.bank.foods.values())
        )
        self.assertEqual(len(self.bank.training_candidates()), 40)
        self.assertFalse(
            set(self.bank.document["heldout_food_ids"])
            & {
                q[k]
                for q in self.bank.training_candidates()
                for k in ["food_a_id", "food_b_id"]
            }
        )

    def test_rejects_real_or_mixed_bank(self):
        for field, value in [("is_synthetic", False), ("research_eligible", True)]:
            d = copy.deepcopy(self.bank.document)
            d[field] = value
            with self.assertRaises(CollectError):
                Bank(d)
        d = copy.deepcopy(self.bank.document)
        d["foods"][0]["is_synthetic"] = False
        with self.assertRaises(CollectError):
            Bank(d)

    def test_leakage_and_duplicate_pairs_rejected(self):
        for change in [
            "cold_train",
            "duplicate",
            "cold_rating",
            "known_unseen",
            "wrong_order",
        ]:
            d = copy.deepcopy(self.bank.document)
            if change == "cold_train":
                d["questions"][0]["food_a_id"] = d["heldout_food_ids"][0]
            elif change == "duplicate":
                d["questions"][40].update(
                    food_a_id=d["questions"][0]["food_b_id"],
                    food_b_id=d["questions"][0]["food_a_id"],
                )
            elif change == "cold_rating":
                d["questions"][50]["food_id"] = d["heldout_food_ids"][0]
            elif change == "known_unseen":
                d["heldout_food_ids"] = [d["heldout_food_ids"][0]]
            else:
                d["questions"][0]["split"] = "test"
            with self.subTest(change=change), self.assertRaises(CollectError):
                Bank(d)

    def test_consent_is_required_and_version_checked(self):
        for consent in [
            {},
            {
                "adult": False,
                "voluntary": True,
                "demo_understood": True,
                "consent_hash": digest(self.bank.document["consent"]),
            },
            {
                "adult": True,
                "voluntary": True,
                "demo_understood": True,
                "consent_hash": "old",
            },
        ]:
            with self.assertRaises(CollectError):
                self.store.create(consent)
        self.assertEqual(self.store.summary()["synthetic_sessions"], 0)

    def test_anonymous_uuid_and_hashed_secret(self):
        s = self.create()
        with self.store.connect() as db:
            row = db.execute("SELECT * FROM sessions").fetchone()
            self.assertNotEqual(row["token_hash"], s["token"])
            self.assertEqual(len(row["user_id"]), 36)
            self.assertEqual(
                db.execute("SELECT COUNT(*) FROM consents").fetchone()[0], 1
            )
        with self.assertRaises(CollectError):
            self.store.state(s["user_id"])

    def test_no_save_before_presentation_or_out_of_order(self):
        s = self.create()
        payload = {
            "choice": "tie",
            "seen_left": None,
            "seen_right": None,
            "self_reported_hunger": None,
        }
        with self.assertRaises(CollectError):
            self.store.save(s["token"], "syn_p00", payload)
        self.store.state(s["token"])
        with self.assertRaises(CollectError):
            self.store.save(s["token"], "syn_p01", payload)

    def test_all_58_and_complete_cannot_append(self):
        s = self.create()
        for _ in range(58):
            self.answer(s["token"])
        state = self.store.state(s["token"])
        self.assertEqual(state["status"], "complete")
        self.assertEqual(state["answered"], 58)
        self.assertIsNone(state["question"])
        self.assertEqual(self.store.summary()["real_participants"], 0)

    def test_retry_idempotent_conflict_preserves_original(self):
        s = self.create()
        q = self.store.state(s["token"])["question"]
        p = {
            "choice": "tie",
            "seen_left": None,
            "seen_right": None,
            "self_reported_hunger": None,
        }
        self.store.save(s["token"], q["question_id"], p)
        self.assertTrue(self.store.save(s["token"], q["question_id"], p)["duplicate"])
        with self.assertRaises(CollectError):
            self.store.save(s["token"], q["question_id"], dict(p, choice="right"))
        self.assertEqual(self.store.state(s["token"])["answered"], 1)

    def test_concurrent_identical_retry_counts_once(self):
        s = self.create()
        q = self.store.state(s["token"])["question"]
        p = {
            "choice": "skip",
            "seen_left": None,
            "seen_right": None,
            "self_reported_hunger": None,
        }
        with ThreadPoolExecutor(max_workers=5) as pool:
            results = list(
                pool.map(
                    lambda _: self.store.save(s["token"], q["question_id"], p), range(5)
                )
            )
        self.assertEqual(sum(not r["duplicate"] for r in results), 1)
        self.assertEqual(self.store.state(s["token"])["answered"], 1)

    def test_restart_resume_and_freeze_after_bank_change(self):
        s = self.create()
        self.answer(s["token"])
        before = self.store.state(s["token"])["question"]
        d = copy.deepcopy(self.bank.document)
        d["bank_version"] = "synthetic_text_v2"
        d["foods"][0]["name_zh"] = "更改后的合成文字"
        restarted = Store(self.path, Bank(d))
        self.assertEqual(before, restarted.state(s["token"])["question"])
        newer = restarted.create(
            {
                "adult": True,
                "voluntary": True,
                "demo_understood": True,
                "consent_hash": digest(d["consent"]),
            }
        )
        with restarted.connect() as db:
            self.assertNotEqual(
                db.execute(
                    "SELECT bank_hash FROM sessions WHERE user_id=?",
                    (newer["user_id"],),
                ).fetchone()[0],
                self.bank.sha256,
            )

    def test_pause_resume_sequential_participants(self):
        a = self.create()
        self.answer(a["token"])
        self.store.pause(a["token"])
        self.assertEqual(self.store.state(a["token"])["status"], "paused")
        with self.assertRaises(CollectError):
            self.store.save(
                a["token"],
                "syn_p01",
                {
                    "choice": "left",
                    "seen_left": None,
                    "seen_right": None,
                    "self_reported_hunger": None,
                },
            )
        b = self.create()
        self.assertEqual(self.store.state(b["token"])["answered"], 0)
        self.assertEqual(self.store.state(a["token"], resume=True)["answered"], 1)
        self.assertEqual(self.store.summary()["synthetic_sessions"], 2)

    def test_invalid_answer_and_null_semantics(self):
        s = self.create()
        q = self.store.state(s["token"])["question"]
        p = {
            "choice": "left",
            "seen_left": None,
            "seen_right": None,
            "self_reported_hunger": None,
        }
        for modified in [
            dict(p, choice="both"),
            dict(p, seen_left=1),
            dict(p, self_reported_hunger=11),
            dict(p, self_reported_hunger=True),
        ]:
            with self.assertRaises(CollectError):
                self.store.save(s["token"], q["question_id"], modified)
        for rating in [True, float("nan"), float("inf"), -1, 11, None]:
            with self.assertRaises(CollectError):
                Store.validate_answer(
                    {"kind": "rating"}, {"rating": rating, "skip": False}
                )
        Store.validate_answer({"kind": "rating"}, {"rating": 0, "skip": False})
        Store.validate_answer({"kind": "rating"}, {"rating": None, "skip": True})

    def test_participant_payload_never_exposes_splits_or_nutrition(self):
        s = self.create()
        payload = json.dumps(self.store.state(s["token"]))
        for forbidden in [
            "split",
            "heldout",
            "energy_kcal",
            "query_policy",
            "bank_json",
            "token_hash",
            "responses",
        ]:
            self.assertNotIn(forbidden, payload)

    def test_position_and_choices_export_without_relabeling(self):
        s = self.create()
        states = []
        for choice in ["left", "right", "tie", "skip"]:
            states.append(self.store.state(s["token"])["question"])
            self.answer(s["token"], choice)
        data, _ = export_bundle(self.store)
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            rows = list(
                csv.DictReader(
                    io.StringIO(z.read("synthetic/train_pairs.csv").decode("utf-8-sig"))
                )
            )
            self.assertEqual(
                [r["choice"] for r in rows], ["left", "right", "tie", "skip"]
            )
            self.assertEqual(
                [r["left_food_id"] for r in rows],
                [q["left"]["food_id"] for q in states],
            )
            self.assertTrue(all(r["self_reported_hunger"] == "" for r in rows))
            self.assertTrue(all(float(r["reaction_time_ms"]) >= 0 for r in rows))

    def test_partitioned_export_and_no_private_consent_or_secret(self):
        s = self.create()
        for _ in range(58):
            self.answer(s["token"])
        data, manifest = export_bundle(self.store)
        self.assertEqual(
            manifest["counts"],
            {"train_pairs": 40, "test_pairs": 10, "train_ratings": 8},
        )
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            everything = "\n".join(z.read(n).decode("utf-8-sig") for n in z.namelist())
            self.assertNotIn(s["token"], everything)
            self.assertNotIn("accepted_at", everything)
            train = list(
                csv.DictReader(
                    io.StringIO(z.read("synthetic/train_pairs.csv").decode("utf-8-sig"))
                )
            )
            test = list(
                csv.DictReader(
                    io.StringIO(z.read("synthetic/test_pairs.csv").decode("utf-8-sig"))
                )
            )
            self.assertFalse(
                {r["pair_id"] for r in train} & {r["pair_id"] for r in test}
            )
            self.assertEqual(sum(r["test_stratum"] == "cold_food" for r in test), 5)
            self.assertTrue(
                all(
                    r["is_synthetic"] == "True" and r["research_eligible"] == "False"
                    for r in train + test
                )
            )
        with self.assertRaises(CollectError):
            export_bundle(self.store, purpose="human")

    def test_export_path_and_no_overwrite(self):
        with self.assertRaises(CollectError):
            write_export(self.store, Path(self.temp.name) / "human/results.zip")
        target = Path(self.temp.name) / "synthetic/export.zip"
        write_export(self.store, target)
        with self.assertRaises(FileExistsError):
            write_export(self.store, target)

    def test_withdraw_deletes_all_session_rows_keeps_other_participant(self):
        a, b = self.create(), self.create()
        self.answer(a["token"])
        self.answer(b["token"])
        self.store.withdraw(a["token"])
        with self.store.connect() as db:
            for table in ["sessions", "consents", "assignments", "responses"]:
                self.assertEqual(
                    db.execute(
                        f"SELECT COUNT(*) FROM {table} WHERE user_id=?", (a["user_id"],)
                    ).fetchone()[0],
                    0,
                )
        with self.assertRaises(CollectError):
            self.store.state(a["token"])
        self.assertEqual(self.store.state(b["token"])["answered"], 1)

    def test_tampering_aborts_state_export_and_save(self):
        s = self.create()
        with self.store.connect() as db:
            db.execute("UPDATE assignments SET question_json='{}' WHERE ordinal=0")
        with self.assertRaises(CollectError):
            self.store.state(s["token"])
        with self.assertRaises(CollectError):
            export_bundle(self.store)
        with self.assertRaises(CollectError):
            self.store.save(s["token"], "syn_p00", {})

    def test_database_partition_guard(self):
        with self.assertRaises(CollectError):
            Store(Path(self.temp.name) / "human/collect.sqlite3", self.bank)
        with self.store.connect() as db:
            db.execute("UPDATE meta SET value='human' WHERE key='provenance'")
        with self.assertRaises(CollectError):
            Store(self.path, self.bank)

    def test_sqlite_backup_restorable_and_no_overwrite(self):
        s = self.create()
        self.answer(s["token"])
        target = Path(self.temp.name) / "synthetic/backup.sqlite3"
        self.store.backup(target)
        self.assertEqual(Store(target, self.bank).state(s["token"])["answered"], 1)
        with self.assertRaises(FileExistsError):
            self.store.backup(target)
        with self.assertRaises(CollectError):
            self.store.backup(Path(self.temp.name) / "human/backup.sqlite3")

    def test_foreign_key_and_sqlite_integrity(self):
        self.create()
        with self.store.connect() as db:
            self.assertEqual(db.execute("PRAGMA integrity_check").fetchone()[0], "ok")
            self.assertEqual(db.execute("PRAGMA foreign_key_check").fetchall(), [])
            with self.assertRaises(sqlite3.IntegrityError):
                db.execute("INSERT INTO responses VALUES ('bad','bad','{}','now',0)")


class HTTPTests(StoreFixture):
    def setUp(self):
        super().setUp()
        self.http_responses = []
        self.server = LocalServer(self.store, 0)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        for response in self.http_responses:
            response.close()
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        super().tearDown()

    def request(self, path, data=None, extra=None):
        headers = {
            "Origin": self.server.origin,
            "X-CSRF-Token": self.server.csrf,
            "Content-Type": "application/json",
        }
        headers.update(extra or {})
        req = urllib.request.Request(
            self.server.origin + path,
            data=None if data is None else json.dumps(data).encode(),
            headers=headers,
        )
        try:
            response = urllib.request.urlopen(req, timeout=3)
        except urllib.error.HTTPError as e:
            response = e
        self.http_responses.append(response)
        return response

    def test_http_security_and_console(self):
        r = self.request("/")
        self.assertEqual(r.status, 200)
        self.assertIn("frame-ancestors 'none'", r.headers["Content-Security-Policy"])
        self.assertEqual(self.request("/api/collector").status, 403)
        self.assertEqual(
            self.request(
                "/api/collector", extra={"X-Collector-Key": self.server.collector_key}
            ).status,
            200,
        )
        self.assertEqual(
            self.request("/api/session", {}, {"Origin": "https://example.com"}).status,
            400,
        )
        self.assertEqual(
            self.request("/api/session", {}, {"X-CSRF-Token": "bad"}).status, 400
        )
        self.assertEqual(
            self.request("/api/info", extra={"Host": "attacker.local"}).status, 403
        )
        self.assertEqual(self.request("/../run.py").status, 404)
        self.assertEqual(
            self.request("/api/state", {}, {"X-Session-Token": "invalid"}).status, 400
        )
        self.assertEqual(self.request("/api/export").status, 403)

    def test_http_end_to_end_restart_style_resume_export_withdraw(self):
        consent = {
            "adult": True,
            "voluntary": True,
            "demo_understood": True,
            "consent_hash": digest(self.bank.document["consent"]),
        }
        s = json.load(self.request("/api/session", consent))
        headers = {"X-Session-Token": s["token"]}
        for _ in range(58):
            state = json.load(self.request("/api/state", {}, headers))
            q = state["question"]
            p = (
                {
                    "choice": "tie",
                    "seen_left": None,
                    "seen_right": None,
                    "self_reported_hunger": 0,
                }
                if q["kind"] == "pair"
                else {"rating": 0, "skip": False}
            )
            self.assertEqual(
                self.request(
                    "/api/answer",
                    {"question_id": q["question_id"], "answer": p},
                    headers,
                ).status,
                200,
            )
        self.assertEqual(
            json.load(self.request("/api/state", {}, headers))["status"], "complete"
        )
        exported = self.request(
            "/api/export", extra={"X-Collector-Key": self.server.collector_key}
        )
        self.assertEqual(exported.headers["Content-Type"], "application/zip")
        with zipfile.ZipFile(io.BytesIO(exported.read())) as z:
            self.assertEqual(
                json.loads(z.read("synthetic/manifest.json"))["counts"]["test_pairs"],
                10,
            )
        self.assertEqual(
            self.request("/api/withdraw", {"confirm": False}, headers).status, 400
        )
        self.assertEqual(
            self.request("/api/withdraw", {"confirm": True}, headers).status, 200
        )
        self.assertEqual(self.request("/api/state", {}, headers).status, 400)


if __name__ == "__main__":
    unittest.main()
