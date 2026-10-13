"""Only engineering fixtures; never FoodBench-48 or observed human choices."""

import json
from itertools import combinations
from pathlib import Path

names = [
    "米饭",
    "面条",
    "烤鸡",
    "煮蛋",
    "豆腐",
    "西兰花",
    "苹果",
    "香蕉",
    "蛋糕",
    "酸奶",
    "茶",
    "饺子",
    "玉米",
    "蘑菇",
    "燕麦",
    "橙子",
]
foods = [
    {
        "food_id": f"syn_f{i:02}",
        "name_zh": f"{name}（合成示例）",
        "description": "虚构配方文字，仅用于软件流程验证，不代表已审核 FoodBench 食品。",
        "serving_g": 100,
        "serving_description": "示例标准份量 100 克",
        "energy_kcal_per_100g": None,
        "protein_g_per_100g": None,
        "fiber_g_per_100g": None,
        "sodium_mg_per_100g": None,
        "image_path": None,
        "is_synthetic": True,
    }
    for i, name in enumerate(names)
]
known = [f["food_id"] for f in foods[:12]]
pairs = list(combinations(known, 2))
# Include all twelve training-visible foods in first coverage block.
coverage = [(known[i], known[(i + 1) % 12]) for i in range(12)]
remaining = [p for p in pairs if set(p) not in [set(x) for x in coverage]]
train = coverage + remaining[:28]
test = remaining[28:33] + [(known[i], foods[12 + i % 4]["food_id"]) for i in range(5)]
questions = [
    {
        "question_id": f"syn_p{i:02}",
        "kind": "pair",
        "split": "train" if i < 40 else "test",
        "food_a_id": a,
        "food_b_id": b,
        "query_policy": "fixture_coverage_v1" if i < 20 else "fixture_fixed_v1",
    }
    for i, (a, b) in enumerate(train + test)
]
questions += [
    {"question_id": f"syn_r{i:02}", "kind": "rating", "split": "train", "food_id": f}
    for i, f in enumerate(known[:8])
]
document = {
    "schema_version": 1,
    "bank_version": "synthetic_text_v1",
    "is_synthetic": True,
    "research_eligible": False,
    "heldout_food_ids": [f["food_id"] for f in foods[12:]],
    "consent": {
        "version": "synthetic_demo_consent_v1",
        "text": "这是 SYNTHETIC DEMO 软件验证，不是正式真人研究采集。仅限年满 18 岁、自愿体验。你将完成 50 次成对比较和 8 次 0–10 预期美味评分，可跳过任意题、随时暂停或退出。这里评价的是看文字后的预期好吃程度，不是试吃，不是营养或医学建议。系统不索取姓名、联系方式、身体或健康信息；随机匿名 ID、展示顺序、选择、是否吃过（可不答）、饥饿程度（可不答）、时间与说明确认版本只保存在本机 SQLite。所有记录标记 synthetic / research_eligible=false，不作为人类研究结果或公开发布。演示记录保留至本机操作者删除；默认不联网同步。请保存恢复/撤回码：可用它恢复或删除该会话，采集员无法替你修改回答。导出与备份由本机操作者控制，撤回会删除当前数据库记录，已下载副本需交由操作者另行删除。正式研究的数据用途、保存期限、公开范围与机构流程必须另行审核，本说明不构成正式研究同意。",
    },
    "foods": foods,
    "questions": questions,
}
Path(__file__).with_name("questionnaire.json").write_text(
    json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
)
