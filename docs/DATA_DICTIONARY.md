# 数据层与 Phase 2 文件

研究方法、FoodVariant 数据契约及 rubric 均沿用主文档。以下为工程层补充。

| 文件 | 含义 | 当前能否用于正式评分 |
|---|---|---|
| data/curated/food_candidate_manifest.csv | 48 个稳定 ID 的身份候选，8 类各 6 项；不是营养数据库 | 否 |
| data/reviews/proposed_food_records.csv | 自动检索后的未审核提案；空值表示未知 | 否 |
| data/reviews/review_cards.json | 来源名称、ID、链接、份量建议、单位变换、缺失值与风险 | 否 |
| data/raw/usda/*.json | 脱敏、带时间和哈希的真实 API 快照；默认不提交 Git | 仅作来源证据 |
| data/curated/foodbench48.csv | 规范化、经审核的正式食品表；当前只有表头 | 当前否 |
| data/reviews/food_review_ledger.csv | 审批侧表；当前只有表头 | 不含任何已批准事件 |
| data/menus/menu_candidate_manifest.csv | 60 份身份组合草案，没有份量和营养结论 | 否 |
| data/menus/day_menus.csv | 正式日菜单 JSON 的 CSV 容器；当前只有表头 | 当前否 |
| data/reviews/human_action_queue.jsonl | 食品待办与全局配置待办，区分 ready_for_review | 不适用 |

`data_quality`、`review_status`、`eligibility` 分别表示来源类型、流程状态和当前分析的可用性。`auto_checked` 永远不等于 `approved`。审批必须包含人类审核者 ID、带时区时间、证据、决定说明和对应食品哈希；侧表还记录 actor_type 与 is_synthetic。程序验证这些凭据的结构和绑定，不代替真实的人类判断。

食品关键字段或来源/份量变化后，旧哈希失效；原始审批不被自动修改为新审批。正式模式拒绝合成食品或合成审批。审核 UI 只导出用户明确输入的决定，不会自动写入正式表；未完善字段的批准按钮不可用。

## 营养映射与单位

USDA 原生 nutrient ID：1003 蛋白质、1004 脂肪、1005 碳水、1079 纤维、1093 钠。能量选择顺序：1008（传统 kcal）、2047（Atwater general）、2048（Atwater specific）、1062（传统 kJ，除以 4.184）。选择的 ID 与全部原始值/单位都会保留；多个能量基准须审核。这是开发版本映射策略，不是已冻结的研究协议。

来源与依据：[API Guide](https://fdc.nal.usda.gov/api-guide/)、[Foundation Foods Documentation](https://fdc.nal.usda.gov/Foundation_Foods_Documentation/)、[Branded Documentation](https://fdc.nal.usda.gov/GBFPD_Documentation/)。

- Foundation / SR Legacy / FNDDS 的 canonical 营养读取每 100 g 基准。品牌记录只有明确克基准时才接受；100 ml 或不明质量基准不猜密度。
- 不把 labelNutrients 的每份值再次当作每 100 g 值；每份转换必须给出正数 serving_g。
- 盐与钠不能重命名互换。可选显式盐估算使用 salt_g × 1000 / 2.5，属于近似组成变换，必须保留假设。
- 不映射未支持 ID，不用营养名称猜字段，不将总糖当作添加糖。
- 低于检出限但原值显示 0 时，保留原值和 LOQ，canonical 置未知待审核。
- 冲突值、错误单位、极端密度及 4/4/9 粗检不一致均只标记；不改写数据库事实。
- 配方以可食原料质量和成品净重计算，明确油盐留存假设；始终标为 recipe_estimate，缺失值传播，不推定成品果蔬质量。

## 数据来源检索

真实搜索使用官方支持的 POST JSON；详情使用 GET。实际 GET 过滤试验曾返回 400，日志已保留；不将其写成成功。HTTP 429 尊重 Retry-After，长等待交给队列，所有尝试受预算约束。缓存可无密钥重放，但哈希错误会阻断。

个人 API Key 仅保存在本地 .env 或环境变量，自动脱敏，不能提交仓库。DEMO_KEY 仅用于少量真实接口 smoke；DEMO_KEY 的真实数据库响应不等于合成食品，也不等于人工已审核。


## Phase 3 synthetic storage

Split: data/splits/synthetic/phase3_v1.json contains snapshot hash, heldout/anchor IDs and disjoint train/test pairs; no answers. Immutable versioned fixture, not formal protocol.

SQLite tables: metadata, users, displays, answers. Unique answer key: (user_id,pair_id,stage). Stage is train/test. Actual displayed order and seed retained. Anonymous UUID and hashed withdrawal token; withdrawal cascades to displays and answers but not prior exports.

Export defaults to train; test requires explicit selection. tie/skip remain distinct. Human collection, anchor ratings and menu dual-stage storage are not implemented in this increment.


## Phase 3 questionnaire extension

- `questionnaire_menus.json`: two separate synthetic breakfast/lunch/dinner fixtures; not approved food data or clinical recommendations.
- `questionnaire_v1.json`: immutable menu snapshots and test pair IDs, bound to the existing food split hash. Does not contain choice labels.
- `AnchorRating`: user_id, food_id, rating_0_10 [0,10], timezone-aware timestamp, is_synthetic=true; only frozen training anchors allowed.
- `MenuChoice`: user_id, menu_pair_id, menu_a_id/menu_b_id (actual left/right), stage, choice left/right/tie/skip, displayed_nutrition, order_randomization (seed), timestamp, is_synthetic=true. Stage hidden precedes visible for all pairs.
- New SQLite tables anchors, menu_displays, menu_answers, queries, notices have user foreign keys with cascade deletion. Menu answer unique key: (user_id,menu_pair_id,stage). Summary reports menu_choice_records separately from independent_menu_pairs.
- Query audit includes policy_version, candidate_pair_ids, candidate_pool_sha256, selected_pair_id and nullable model_state_sha256. Only random scheduling is integrated; no fitted model is falsely reported.
- Export-survey anchors/menus produces explicit synthetic CSV files. These are demo data; never HUMAN observations.


## Protocol-sized synthetic fixture and active query audit

- phase3_sized_v1.json: 48 synthetic IDs, 8 cold foods, 8 training anchors, 20 coverage pairs, a larger frozen training candidate pool (only 20 are selected per session), and 10 frozen tests (5 known/5 cold). training_budget=40 and adaptive_budget=20. assignment_order contains a frozen shuffle of 12 active and 12 random slots.
- questionnaire_sized_v1.json: 60 embedded synthetic three-meal menus; development=36, final=24; 12 frozen final menu pairs. No source-backed food approvals or human labels.
- QueryModel synthetic_bt_query_v1: L2=1 BT utility differences, train-only per-session fit. Tie/skip excluded from likelihood and retained in training hash and counts. Zero-label prior is explicit. No calibrated absolute food score.
- Trace adds sequence, selected_probability, full model_state and model_state_sha256; state records training_data_sha256, fitted_binary_records, excluded_tie_skip and known-food coefficients. Used model record count equals query sequence minus one. Probability is internal model output, not validated human confidence.
- assignments table binds synthetic user IDs to frozen group slots. Allocation cursor does not reset when a session is withdrawn. All rows remain synthetic and are segregated from data/private.
