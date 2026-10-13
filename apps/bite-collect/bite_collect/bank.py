"""Versioned questionnaire adapter. No labels or model dependencies here."""

import hashlib
import json
import math
import re
from pathlib import Path


class CollectError(ValueError):
    pass


def canonical(value):
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


class Bank:
    def __init__(self, document):
        self.document = json.loads(canonical(document))
        self.sha256 = digest(self.document)
        self.validate()
        self.foods = {f["food_id"]: f for f in self.document["foods"]}
        self.questions = self.document["questions"]

    @classmethod
    def load(cls, path):
        return cls(json.loads(Path(path).read_text(encoding="utf-8")))

    def validate(self):
        d = self.document
        if d.get("schema_version") != 1 or not d.get("bank_version"):
            raise CollectError("题库版本不受支持")
        if d.get("is_synthetic") is not True or d.get("research_eligible") is not False:
            raise CollectError(
                "此离线开发版本仅接受 synthetic fixture；真人采集尚未开放"
            )
        consent = d.get("consent", {})
        if not all(
            isinstance(consent.get(k), str) and consent[k].strip()
            for k in ("version", "text")
        ):
            raise CollectError("缺少知情说明版本或正文")
        foods = d.get("foods", [])
        ids = [f.get("food_id") for f in foods]
        if (
            not ids
            or len(set(ids)) != len(ids)
            or not all(
                isinstance(i, str)
                and re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_.:-]{0,100}", i)
                for i in ids
            )
        ):
            raise CollectError("食物 ID 缺失或重复")
        for f in foods:
            if f.get("is_synthetic") is not True:
                raise CollectError("禁止混合 synthetic 与真实食物")
            if not all(
                isinstance(f.get(k), str) and f[k].strip()
                for k in ("name_zh", "description", "serving_description")
            ):
                raise CollectError("缺少食物名称、描述或标准份量")
            g = f.get("serving_g")
            if type(g) not in (int, float) or not math.isfinite(g) or g <= 0:
                raise CollectError("标准份量必须为正数")
            # v1 text-only adapter: never fetch external/unlicensed images.
            if f.get("image_path") is not None:
                raise CollectError("v1 为离线文字题库，请保留 image_path=null")
        heldout = set(d.get("heldout_food_ids", []))
        if not heldout or not heldout <= set(ids):
            raise CollectError("冷食物划分无效")
        qs = d.get("questions", [])
        qids = [q.get("question_id") for q in qs]
        if (
            len(qs) != 58
            or len(set(qids)) != 58
            or not all(
                isinstance(i, str)
                and re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_.:-]{0,100}", i)
                for i in qids
            )
        ):
            raise CollectError("要求 58 个唯一题目 ID")
        counts = {"train": 0, "test": 0, "rating": 0}
        pairs = set()
        train_foods, rating_foods = set(), set()
        known_tests, cold_tests = [], []
        for index, q in enumerate(qs):
            if q.get("kind") == "pair":
                if not isinstance(q.get("query_policy"), str) or not re.fullmatch(
                    r"[A-Za-z0-9_][A-Za-z0-9_.:-]{0,100}", q["query_policy"]
                ):
                    raise CollectError("缺少可审计查询策略标识")
                split = q.get("split")
                expected = "train" if index < 40 else "test"
                if index >= 50 or split != expected:
                    raise CollectError("题序必须为 40 train、10 test、8 rating")
                a, b = q.get("food_a_id"), q.get("food_b_id")
                if a not in ids or b not in ids or a == b:
                    raise CollectError("比较题食物引用无效")
                key = tuple(sorted((a, b)))
                if key in pairs:
                    raise CollectError("比较对重复或训练/测试重叠")
                pairs.add(key)
                counts[split] += 1
                if split == "train":
                    if {a, b} & heldout:
                        raise CollectError("冷食物泄漏到训练题")
                    train_foods.update((a, b))
                elif {a, b} & heldout:
                    cold_tests.append(q)
                else:
                    known_tests.append(q)
            elif q.get("kind") == "rating":
                f = q.get("food_id")
                if (
                    index < 50
                    or q.get("split") != "train"
                    or f not in train_foods
                    or f in heldout
                    or f in rating_foods
                ):
                    raise CollectError("直接评分必须是 8 个不同训练锚点")
                rating_foods.add(f)
                counts["rating"] += 1
            else:
                raise CollectError("未知题型")
        if (
            counts != {"train": 40, "test": 10, "rating": 8}
            or len(cold_tests) != 5
            or len(known_tests) != 5
        ):
            raise CollectError("训练/测试/评分数量或测试层级不符合协议")
        if any({q["food_a_id"], q["food_b_id"]} - train_foods for q in known_tests):
            raise CollectError("known-food 测试必须使用训练可见食物")

    def training_candidates(self):
        """Future selectors receive only training questions; no response data."""
        return json.loads(
            canonical(
                [
                    q
                    for q in self.questions
                    if q["kind"] == "pair" and q["split"] == "train"
                ]
            )
        )

    def display_food(self, food_id):
        f = self.foods[food_id]
        return {
            k: f[k]
            for k in (
                "food_id",
                "name_zh",
                "description",
                "serving_g",
                "serving_description",
            )
        }
