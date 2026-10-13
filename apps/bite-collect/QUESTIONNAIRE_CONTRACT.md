# Questionnaire adapter v1

问卷是独立 JSON 输入，`Bank.load(path)` 校验，`Store` 保存快照。不得从数据库答案推导或修改题库 split；不得复用合成 ID 为真实食品 ID。v1 只支持文字，`image_path=null`。后续图片适配器需本地可再分发授权、归属和独立校验。

```json
{
  "schema_version": 1,
  "bank_version": "synthetic_text_v1",
  "is_synthetic": true,
  "research_eligible": false,
  "consent": {"version": "synthetic_demo_consent_v1", "text": "完整版本化说明"},
  "heldout_food_ids": ["syn_cold01"],
  "foods": [{
    "food_id": "syn_f01", "name_zh": "示例（合成）",
    "description": "配方变体描述", "serving_g": 100,
    "serving_description": "示例标准份量 100 克",
    "image_path": null, "is_synthetic": true
  }],
  "questions": [
    {"question_id": "syn_p01", "kind": "pair", "split": "train",
     "food_a_id": "syn_f01", "food_b_id": "syn_f02", "query_policy": "fixture_fixed_v1"},
    {"question_id": "syn_r01", "kind": "rating", "split": "train", "food_id": "syn_f01"}
  ]
}
```

上面仅为字段说明，不能单独通过 58 题数量校验。完整输入是 `fixtures/synthetic/questionnaire.json`；构造脚本可以重建相同夹具，不生成人类答案。

校验要求：40 train pair → 10 test pair → 8 train rating。对称比较对不能重复。冷食物不能进入 train 或 rating；5 known 测试对必须来自训练可见食品，5 cold 对至少包含一个冷食物；8 个评分锚点互异且训练可见。ID 和策略标识限定 ASCII 安全字符。份量有限正数，不接受 NaN。整个题库规范化 JSON SHA256、说明 hash、每人实际左右分配 hash，在会话建立事务中保存，早于首次回答。

正式数据适配器应将经批准的 FoodBench 食品快照和已冻结的正式 pair/anchor ID 转为同一展示对象，并附食品审核凭据、协议锁 hash、来源类型、研究层级 `pilot_dev/pilot_eval/full_study` 等元数据。此版本对 `is_synthetic!=true` 或 `research_eligible!=false` 硬拒绝，未来不能通过改 JSON 标志绕过审核/伦理/正式启用门槛。营养列原样保留 null；纯美味界面仅投影名称、配方描述与份量。

`training_candidates()` 返回训练比较的深拷贝，不读取任何答案。未来主动采样模块应使用该隔离接口，还必须记录候选池 hash、模型 hash、策略版本和选择日志。本轮只使用冻结 fixture 固定题序，不接入模型，不执行 active/random 正式分组研究。

SQLite schema v1：

| 表 | 用途 | 关键约束 |
| --- | --- | --- |
| meta | schema、synthetic 数据来源 | 不兼容库拒绝打开 |
| sessions | UUID、码 hash、快照、seed、hash、状态 | synthetic=1；状态 active/paused/complete |
| consents | 原始说明及版本、确认时间和条件 | 单独表，不导出；级联撤回 |
| assignments | 每人 58 题、真实左右、首次展示时间 | 会话内题 ID/序号唯一；快照 hash 校验 |
| responses | 原始 payload、提交时间、elapsed ms | 每会话每题唯一；外键级联 |

不支持静默迁移数据库或覆盖用户原回答；不同 payload 对同一题重提会报冲突。后续人工更正流程须保留原回答与更正事件，不直接 UPDATE responses。本轮没有更正/人工审核接口。
