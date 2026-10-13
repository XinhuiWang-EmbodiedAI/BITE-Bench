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
