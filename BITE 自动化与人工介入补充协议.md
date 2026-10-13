# BITE-Bench 自动化与人工介入补充协议

> **Automation & Human-in-the-Loop Addendum · v1.1 · 2026-10-13**  
> 类型：**第三份补充文档**，不是对原研究方法和工程手册的替代。  
> 配套：[`BITE_研究方法与实验设计.md`](./BITE_研究方法与实验设计.md)；[`BITE_Codex_实施与实验手册.md`](./BITE_Codex_实施与实验手册.md)。  
> 当前建议模式：**B = Hybrid Pilot（单人/少人真实偏好 + 自动化系统）**；保留 A（全合成工程验证）和 C（完整多人实验）的切换能力。  
> 适用环境：家用 Windows 10 / 可选 WSL2，RTX 5060 8GB，32GB RAM，通过 SSH/Tailscale 远程执行。

---

## 0. 给 Codex / Luna 的第一条指令

**先完整阅读三份文档，不要跳过既有方法学及测试约束。** 原研究规格书约束科学解释和实验有效性；原工程手册约束数学公式、schema、CLI、目录结构和阶段划分；本文件仅补充**执行模式、自动化权限、人类任务路由、数据审核与阶段升级**。对于本文件未覆盖的事项，严格沿用原文档。

如果出现冲突：

1. 任何时候，**真实性、隐私、禁止测试泄漏、研究协议冻结**优先于自动化便利。不能用本补充文件绕过原手册的 `BLOCKED` 门槛。
2. 数学定义、主要实验比较、样本与数据划分以《研究方法与实验设计》和《Codex 实施与实验手册》的原定义为准；本文件不能直接修改 `rubric_v1.yaml`、M0–M4 或主假设。
3. 本文件对**自动化运行方式、何时请求人工、审计与试点升级**优先。若需要改变冻结的实验方法，提出变更请求，在 `docs/DECISIONS.md` 记录后生成新版本协议，禁止静默覆盖。
4. **不要把计划中的命令误称为已存在**。以下的新增 CLI 为实现规范，必须由 Codex 编写、测试、再调用。

**首要目标：**不因等待真实受试者、复杂中餐的数据审核、USDA API Key 或 GPU 问题而阻塞整个软件工程。优先运行 CPU + 合成 fixture 的工程验证；独立模块可继续开发，但禁止冒充真实研究结果。

---

## 1. 研究工作流三种运行模式

| 模式 | 代码与实验自动化 | 数据来源 | 可对外声称的结论 | 典型用途 |
|---|---|---|---|---|
| **A / `synthetic_only`** | 尽量全自动 | 合成食物、合成用户、合成偏好；以及独立的已核实真实食物数据子集（若有） | **工程正确性及合成环境结果**；不能声称真实人类对齐能力 | 第一阶段端到端冒烟测试与游戏原型 |
| **B / `hybrid_pilot`** | 尽量全自动 | 已审核的真实食物数据 + 1 至少量真人偏好与菜单选择 | **个人案例 / 可行性试验**；不能据此推广到一般人群 | **项目默认模式** |
| **C / `full_study`** | 尽量全自动 | 已审核 FoodBench-48 + 24 名志愿者的真实标注 + 独立菜单评价 | 探索性群体研究；需如实报告样本局限与区间 | 可选的完整实验与正式文章 |

A → B → C 是推荐成长路径，不强制线性进行。任一模式都应保留同样的数据契约、日志、版本哈希和测试划分，不许把合成记录补进真人样本量。

### 1.1 最重要的语义区分

- `pipeline_pass`：代码可运行、测试通过。**不等于研究假设得到验证**。
- `nutrition_review_pass`：指定的食物记录具备合格来源及完成必要审核。**不等于所有中餐有实验室测定营养值**。
- `human_pilot_available`：至少有一个自愿参与者的真实回答。**不等于有可靠的群体外推结论**。
- `main_study_complete`：满足锁定协议中预设的真实采集与评价门槛，并成功运行分析。**不意味着假设成立或指标必然更优**。

继续使用旧手册的统一阶段状态：`NOT_STARTED`、`IN_PROGRESS`、`PASS`、`BLOCKED`、`FAILED`、`NOT_RUN`。新增的 `BLOCKED_BY_HUMAN_DATA`、`BLOCKED_BY_NUTRITION_REVIEW` 等只作为 **`reason_code`**，不新增顶层状态枚举。

---

## 2. 自动化权限矩阵：哪些事情允许 Codex 自主处理

| 任务 | 默认允许自动执行 | 人工介入条件 | 必须保留的痕迹 |
|---|---|---|---|
| 创建项目目录、代码、测试、文档 | 是 | 涉及删除/覆盖用户已有数据时 | Git 变更、测试日志 |
| `uv` 虚拟环境内安装锁定的依赖 | 是 | 需要提升权限、系统级修改时 | `uv.lock`、版本信息 |
| CPU 合成数据构造与 smoke tests | 是 | 无 | `is_synthetic=true`、种子、产出清单 |
| 从 USDA 等来源检索食品记录 | 是（受许可证、限流和访问条件约束） | API Key 不存在、数据匹配冲突时 | 原始响应、检索时间、source ID |
| 自动完成营养字段映射、单位换算、异常检测 | 是 | 异常记录或者语义不确定时 | 变换版本、QA 报告 |
| 将候选数据升级为正式 `reviewed` | **否：必须有审核凭据** | 由人确认关键事实或提供可核查的既有审核凭据 | reviewer、时间、决定、证据 |
| 生成 60 份候选日菜单 | 是 | 不合理或缺关键营养的菜单需审核/剔除 | 菜单类别、来源食物版本、QA |
| 实现问卷 UI、匿名 ID、数据导出 | 是 | 对外发放、收集真人数据前要确认同意说明及学校要求 | 表单版本、冻结划分 |
| 代真人填写偏好和菜单评价 | **禁止** | 必须有真人自主作答 | 真实记录不包含自动生成标记 |
| 训练 TasteNet、跑多 Agent、仿真、消融、统计 | 是 | 缺少必要真实数据时仅跑合成或标记阻断 | seed、hash、model digest、数据层级 |
| 自动写图表、结果报告、论文草稿 | 是 | 对外宣称科学结论或发表前审阅 | 图表 provenance、数据链接 |
| 下载/试运行 4-bit 小模型 | 符合原手册资源预算时可执行 | 大量下载、改变驱动、系统级安装、端口公网暴露时 | 模型名称、digest、显存实测 |
| 公布原始受试者数据、公开仓库、发表论文 | **禁止自动执行** | 需要明确授权和相应数据/伦理审查 | 发布决策记录 |

**默认策略：**能通过代码、规则、单元测试或者具有明确元数据的来源客观验证的事项先自动验证；只有身份/语义判断、人类真实偏好、伦理或对外发布需要人工。不得反复就相同的低风险工程细节询问用户。

---

## 3. FoodBench-48：数据全自动搜集 + 风险分层人工审核

### 3.1 必须识别的营养数据风险

1. **身份匹配：**食物名称、生产商品牌/版本、烹饪方式、配方是否一致；USDA `fried chicken` 不等于任意中式炸鸡。
2. **重量基准：**per 100g vs per serving；生/熟、去骨/带骨、可食部分、实际标准份量。
3. **单位：**kJ 与 kcal；sodium_mg（钠）与 salt_g（盐）；g 与 mg；原始数据转化必须记录公式和原单位。
4. **宏量元素与其他营养：**蛋白质、脂肪、碳水、膳食纤维、钠；添加糖不能用总糖直接替代。
5. **复合菜品：**原料净重、食用油、盐、酱汁、烹调重量变化及产出净重；不假装存在唯一的“火锅一份”热量。
6. **来源与许可：**API 记录 ID、原始快照、检索日期、使用条款、图片许可与署名。
7. **缺失值：**`null` 永远是未知，不能转换成零、取随机值或直接采纳 LLM 猜测。

自动校验应包括非负值、份量大于零、常见单位误转换、极端能量密度、食物名称不匹配、明显生熟冲突、来源 ID 缺失、图片许可证缺失。**合理性范围只负责标记异常，不自动证明数据正确**；例如基于宏量营养的估算能量可能因纤维、酒精、有机酸及数据库计算方法而与标签值不同，不能因简单 4/4/9 公式不一致就直接改写食品数据。

### 3.2 严格区分三个相互独立的维度

- `data_quality`：使用原工程 schema，例如 `verified_label / database / recipe_estimate / unknown`，代表**数据来源类型**。
- `review_status`：`unreviewed / auto_checked / needs_review / approved / rejected`，代表**审核流程状态**。`auto_checked` 不能等价 `approved`。
- `research_eligibility`：`eligible / ineligible / insufficient_data`，代表在**某一次特定分析中是否足够**。

三个字段不能互相覆盖。一道菜可以是 `recipe_estimate` + `approved` + `eligible`；这仍不是实验室测量。一道菜也可以是 `database` + `needs_review` + `insufficient_data`。

建议将审核信息放在**侧表** `data/reviews/food_review_ledger.csv`，不要不兼容地改写原 `FoodVariant` 的必需字段契约：

```csv
food_id,food_data_sha256,review_status,risk_level,reviewer_id,reviewed_at,evidence_ref,decision_note
F001,<sha256>,approved,low,human_01,2026-10-13T10:00:00+08:00,usda:<record-id>,Matched cooked broccoli and edible serving
F002,<sha256>,needs_review,high,,,recipe:kungpao_v1,Oil/finished weight unresolved
```

以上 CSV 是**schema 示例行**，不是声称已核验的真实食物或审核事实。实际的 `food_data_sha256` 必须由程序对数据快照计算，`reviewer_id` 不允许虚构。

### 3.3 审核优先级与处理策略

| 风险层级 | 示例 | 自动化动作 | 人工动作 | 正式研究处理 |
|---|---|---|---|---|
| Low | 有明确标签的瓶装饮料、唯一匹配的原型食材 | 抽取来源、核对单位、生成审核卡 | 确认关键匹配和份量；按审核协议批量通过也需记录责任人 | 通过后可纳入 |
| Medium | 烤/煮/炒的普通食品、来源有多个近似结果 | 候选排序、冲突检测 | 确认具体版本及食用份量 | 未确认时保持待审 |
| High | 宫保鸡丁、麻婆豆腐、火锅、自由组合菜 | 记录配方、油盐假设、计算原料加权和产出净重 | 确认规范化食谱及不可确定因素 | 缺关键字段时剔除或另列估算子集 |

**审核操作不要求人体试吃或送检**；通常是核对记录/食谱及关键假设。正式实验需报告 `database/verified_label/recipe_estimate` 组成，并将数据库或标签直接支持的子集与包含配方估算的子集分别做稳定性分析。

### 3.4 自动化处理算法（必须实现）

```text
food_candidate_manifest.csv（只包含候选身份）
  -> source_search（检索与候选证据）
  -> record_match（名称、品牌、加工状态、配方、来源匹配）
  -> unit_normalization（标准化至每100g）
  -> data_quality_validation（缺失、极端值、冲突、授权）
  -> risk_classification（low/medium/high；附触发规则）
  -> proposed_food_records.csv + food_review_queue.csv
  -> [人工仅审核队列/审批批次]
  -> reviewed_food_snapshot + review_ledger + SHA256
  -> 正式日菜单生成与审计
```

自动选到唯一数据库记录也**不能自动编造人类审核事件**。无人审核前可在 `provisional` 数据分支上继续 smoke、游戏原型、营养组件单元测试；正式运行如果要求 `review_status=approved` 则继续 `BLOCKED`。

### 3.5 审核卡最低展示字段

一个人工审核条目至少应展示：`food_id`、中文/英文名、选中的标准化版本、标准份量克数、源记录名与链接、source ID、每 100g 的 kcal/protein/fat/carbs/fiber/sodium、缺失字段列表、原始单位、烹饪/配方假设、风险标记、Codex 建议及证据、`approve / request_change / reject` 按钮。

*“Codex 建议通过”只是建议，不等于研究者已经批准。*

---

## 4. 人类参与任务：限制到两个真正不可替代的环节

### 4.1 人类任务 H1：预期美味偏好

- UI 询问“只考虑**预期好吃程度**，不考虑健康、热量和价格，你更偏好哪种？”
- 标准份量与食物描述必须相同规范；条件允许时用可再分发的图片；图片不存在时允许文本版本。
- 每人的完整研究计划：**40 道训练对 + 10 道冻结测试对 + 8 个训练锚点的 0–10 直接评分**（50 次二选一 + 8 次评分）。
- B 模式的单人 Pilot 可以从少量步骤开始验证交互，但只有满足相应预设样本条件时才运行该层级的完整评价；不足时明确 `pilot_partial`。
- 必须记录 `left/right/tie/skip`、实际展示顺序、问卷阶段、是否吃过、非必需的当下饥饿水平（自愿），并避免营养信息影响纯美味标注。
- **这是看图/看描述的预期美味**，除非存在真实试吃，不要称为“客观美味”或“品尝后的味觉”。
- test 对与 heldout food 在收集数据前冻结；主动学习只接触训练候选池。单人 Pilot 的标注若用于调试或改权重，之后不能又原封不动算作未经使用的最终测试。

### 4.2 人类任务 H2：独立综合饮食选择

- 使用冻结的日菜单比较对，给出菜品组成、标准份量，以及经审核的营养信息。
- 默认每人 **12 组日菜单 pair**；展示阶段可能包含 `taste_hidden_nutrition` 和 `overall_visible_nutrition`。一个 pair 的双阶段回答是**2 条选择记录**，并不等于 2 个独立菜单比较对。
- 主评价采用 `overall_visible_nutrition`，遵守原手册；另一阶段用于 Taste–Health Preference Gap。
- 所有真实答案写入私有数据存储，**不得交给 LLM 生成，也不得作为当前测试集合上的 Prompt 或权重调优依据**。
- 独立综合评价是“参与者报告更想选择哪份菜单”，**不是**真实长期健康效果的测量。

### 4.3 人工任务不是：每天替 AI 记饮食 / 手动输入 48 道菜所有营养值

这些属于应该自动化的脏活。用户仅审核来源、配方关键假设和结果解释；一旦审核完成，数据版本冻结后反复调用即可，不需要每轮实验重复人工参与。

### 4.4 真人采集的最低伦理与隐私边界

- 在邀请其他人前核实学校对匿名偏好调查是否需要伦理审批或豁免；必要时完成程序再启动采集。
- 自愿参与、成年、可退出；用匿名 ID，不主动收集姓名、手机号、身份证或健康状况。
- 向受试者说明数据用途、保存方式、撤回路径、公开范围；只发布经允许的汇总统计。
- 默认把 `data/private/`、原始同意记录、私有审计日志加入 `.gitignore`，不通过公开 Git 仓库传输。

---

## 5. 执行策略：全部工程阶段尽量自主推进，不因缺人而中断

以下内容与原手册 Phase 0–11 一一对齐；**只添加执行策略，不改具体方法和评价准则**。

| 原手册阶段 | 无人参与时 Codex 应立即完成 | 有真人或已审核数据后再做 | 正式研究门槛 |
|---|---|---|---|
| P0 环境 | 检查 5060/WSL/uv/Ollama 可用性，CPU 回退 | 需要系统级修改时请示 | 环境记录真实，不假设 GPU 运行 |
| P1 Schema | 数据契约、synthetic fixtures、单元测试 | — | 测试可重跑 |
| P2 FoodBench | USDA 客户端、匹配、单位转换、审核队列、菜单候选 | 批量审核真实食物与特殊配方 | 主实验需足够的有效已审核数据 |
| P3 问卷 | UI、测试拆分、匿名记录、撤回、synthetic smoke | 真人提供 H1/H2 记录 | 没有真人时标记 `BLOCKED` |
| P4 TasteNet | 全模型训练代码、synthetic baseline、CV/指标脚本 | 用合法真实训练集训练及独立测试 | RQ1 结果只有真数据才能声称人类偏好预测 |
| P5 Oracles | 计算规则、缺失值阻断、单元/性质测试 | 已审核菜单上正式计算 | 营养事实不能来自 LLM 猜测 |
| P6 Local LLM | 4-bit Qwen 试运行、fallback、token/VRAM 日志 | 系统权限/资源变更时请示 | 使用实际可用模型，失败时明示 |
| P7 Multi-Agent | M0–M4、JSON Schema、证据检查、预算公平 | 已审核菜单/已训练 TasteNet 上运行 | 固定营养事实不可篡改 |
| P8 外部评价 | 分割冻结、评价脚本、bootstrap、demo | 真实菜单偏好 H2 | 缺 H2 时主效果 `BLOCKED` |
| P9 7/30 天模拟 | 全部合成环境运行、策略对照、随机种子 | 可带入已训练真人偏好模型作为案例 | 标注 SIMULATION，不推导健康结论 |
| P10 消融绘图 | 生成全部可用的合成图、缺失标识与模板 | 用真实结果生成正式主图 | 实验不足时主图不可伪造 |
| P11 交付 | README、RUN_STATUS、DECISIONS、manifest、可复现命令 | 结果解读和后续是否扩大参与者由人决策 | 准确披露缺口 |

### 5.1 建议新增的自动化调度配置（**待实现**）

路径：`config/automation.yaml`。以下只是默认草案，不得覆盖用户已冻结的 `protocol.lock.yaml`：

```yaml
version: automation_v1
operation_mode: hybrid_pilot  # synthetic_only | hybrid_pilot | full_study
execution_policy:
  continue_independent_tasks_when_blocked: true
  allow_cpu_fallback: true
  allow_synthetic_smoke: true
  allow_synthetic_data_in_human_results: false
  request_user_on_risk_only: true
  modify_system_drivers: false
  expose_public_ports: false
  publish_human_data: false
food_review:
  source_lookup_automatic: true
  unit_conversion_automatic: true
  create_review_queue: true
  require_approval_for_formal_dataset: true
  risk_buckets: [low, medium, high]
human_study:
  collect_real_human_responses: false # 只有明确启动合规采集时才设 true
  anonymize_ids: true
  do_not_train_on_heldout: true
  never_simulate_human_provenance: true
reporting:
  require_provenance: true
  separate_simulation_from_human: true
  preserve_all_failures: true
```

注意：`collect_real_human_responses: false` 是安全默认值，表示首次无人值守执行只构建和测试系统，不在后台主动收集他人数据。用户明确开始自己的自愿问卷体验之后，可以按批准流程切换本地界面为真人输入模式。

### 5.2 建议新增命令（**由 Codex 实现后才能执行**）

```bash
# 自动搜集候选记录和风险分类；不越权标记 human approved
uv run bite review prepare --manifest data/curated/food_candidate_manifest.csv \
  --out data/reviews/

# 自动校验审核凭据和食物源版本是否一致
uv run bite review audit --ledger data/reviews/food_review_ledger.csv \
  --food-data data/curated/foodbench48.csv --strict

# 汇总待人类处理的最小清单
uv run bite review queue --only-actionable --out outputs/reports/human_queue.md

# 一键运行所有不依赖真实参与者的代码/数据/模拟验证
uv run bite workflow run --mode synthetic_only --resume

# 将已有个人真实答案视为 case study，而非群体主实验
uv run bite workflow run --mode hybrid_pilot --resume

# 展示不同研究层级真实完成程度；不要把 smoke 标成真结果
uv run bite workflow status --format markdown --out docs/RUN_STATUS.md
```

以上为**拟实现 CLI**，不是承诺工程已存在。与原手册已有 `bite data usda-search`、`bite data validate`、`bite split freeze`、`bite label app`、`bite taste train` 等 CLI 保持兼容；新的 `workflow` 子命令仅用于编排，不绕过各模块本身的验收。

---

## 6. Human Review Queue：把所有需要人干的事集中成一个列表

**不要每碰到一个未识别食品就中断并问用户。** Codex 先继续做独立事项，把人工项目收集在统一队列：

`docs/HUMAN_ACTIONS.md`（供人阅读）以及 `data/reviews/human_action_queue.jsonl`（供程序处理）。

每项字段至少为：

```json
{
  "action_id": "REVIEW-0001",
  "kind": "food_source_match",
  "object_ref": "food_id_or_menu_id",
  "risk": "high",
  "status": "PENDING_HUMAN",
  "question": "请确认该菜品使用哪种规范化食谱及标准份量",
  "options": ["approve_candidate_1", "approve_candidate_2", "request_revision", "exclude"],
  "evidence_paths": ["data/raw/usda/example.json"],
  "default_safe_action": "exclude_from_formal_analysis",
  "blocks": ["Phase2 formal subset", "Phase8 formal scoring"]
}
```

示例中 `evidence_paths` 为占位，只有实际存在的文件才能被放入真实队列。

人工任务按以下优先级排序：

1. **HIGH：**影响真实数据合法使用、伦理隐私、测试冻结、对外发布、系统级有风险的修改。
2. **MEDIUM：**阻碍正式 FoodBench 质量的食物身份/配方/份量核验，真实问卷启动授权。
3. **LOW：**样式、图表配色、展示形式、非关键可选字段；默认由 Codex 自行合理处理，不反复询问。

每个任务带 `blocked_modules`；仅阻断受其影响的模块。禁止因缺少一个食物的钠数据就让 `src/` 代码、Qwen 试运行或合成仿真全部停止。

### 6.1 人工批次审核规则

- 对 low-risk 候选可合并为表格让研究者批量审核，但日志仍需逐条落地，每行独立记录审核人、时间和数据哈希。
- 对 high-risk 食谱必须有针对性说明；不能使用全选“一键批准所有宫保鸡丁变体”。
- 审核后如果数据行的来源、份量或营养字段改变，其审核凭据应失效并回到 `needs_review`（使用规范化记录 hash 验证）。
- 被拒绝食物可从主分析剔除，并记录剔除率；不得静默换一条记录以凑够 48。

---

## 7. 数据防泄漏与 B 模式单人 Pilot 的特殊限制

1. **冻结在前、选择在后。** 即使只有用户本人 1 个参与者，heldout food、test pair、菜单测试题也必须先由系统冻结并记录 hash。
2. **开发性互动与正式评估不可混用。** 如果用自己的测试答案反复微调 Prompt、换模型、调整参数，该答案就属于开发数据；未来必须采集新的严格隔离测试资料。
3. **区分三种真实数据标签：** `pilot_dev`、`pilot_eval`、`full_study`；字段可以扩展到 metadata 或单独分区，避免破坏原始偏好 schema。
4. **单人统计不伪装成人群统计。** 1 人的多个食物选择不是多个独立的人；不能用按题目抽样替代对参与者群体的置信区间。
5. **用户自填数据不得由 Codex 事后“修正”。** 可以提示重复或异常，但保留原回答和更正记录。
6. **缺真人标签时：**可以测试 TasteNet 是否拟合合成真值，却不能把合成 accuracy 写作“human preference accuracy”。
7. **至少留一个不接触模型开发的外部评价阶段。** 若只有一个用户和很少的选择，结论写成 exploratory case study，报告观察到的选择和模型预测差距，不报群体显著性。
8. **模拟 Agent 是模型角色，不是人类参与者。** 即使随机模拟了 10,000 人，也不等于完成 24 人真人试验。

### 7.1 真正需要人工时的最少交互

人类可以仅完成两种 UI：

- `Taste Survey`：二选一 + 极少量锚点评分；可以分批保存与恢复。
- `Menu Survey`：日菜单两选一，先隐藏后展示营养，记录两阶段答案。

研究者只需定期检查 `docs/HUMAN_ACTIONS.md`，而不需进入 Python 或自己管理训练脚本。

---

## 8. 原手册的五个评估方法和多 Agent 研究不变

继续保持原方案的 `M0`（确定性基线）、`M1`（single-agent）、`M2`（独立多 Agent）、`M3`（单轮讨论多 Agent）、`M4`（token 预算匹配的单 Agent）定义和**相同的营养事实**。本补充文件不新增可改变科学结论的“人工主观总分裁判”。

- TasteNet 的人类测试集指标仍是 RQ1 主证据。
- 多 Agent 是否有效，仍通过冻结的真实**日菜单 pair 选择概率与 NLL**、coverage 和调用开销检验，而不是比较它给自己的分数。
- 长期仿真仍明确为 Simulation；不能根据长期 BITE 分数推断真实人体的寿命、体重或疾病。
- 消融和敏感性分析可自动跑完，但必须使用相同的数据快照、配置哈希及允许的独立评价指标。
- 图表标签必须区分 `HUMAN`、`DATABASE`、`RECIPE ESTIMATE`、`SIMULATION`、`SYNTHETIC DEMO`。

不要为了演示好看使用人类测试结果调整权重。主实验失败、无显著差异或多 Agent 更差，均必须原样报告。

---

## 9. 新增自动化验收测试（必须落实为可运行测试）

至少覆盖：

```text
T01 食品每 100g 与每份单位转换正确；kJ 不被当作 kcal。
T02 sodium_mg 与 salt_g 明确区分；未知值保持 null。
T03 缺少必要营养/来源时 formal scoring = insufficient_data。
T04 review_status=auto_checked 不能自动升级 approved。
T05 食品关键字段 hash 变化后 review approval 自动失效。
T06 recipe_estimate 不被伪装成 lab measurement / verified_label。
T07 synthetic fixture 不得进入 HUMAN 主结果，且程序遇到时硬报错。
T08 `hybrid_pilot` 无真人数据时工程可以 PASS，真人主实验 BLOCKED。
T09 单人 Pilot 的 NLL 可按案例报告，但禁止生成伪造的群体 bootstrap CI。
T10 固定 heldout/test 数据不可被主动采样或模型拟合使用。
T11 `M0–M4` 对同一日菜单读取相同不可改写的营养事实。
T12 审核队列产生后，独立的 CPU/LLM/仿真任务仍可继续。
T13 无 API key 时自动写入 reason_code，不能自动造 USDA 响应。
T14 不接收伪造 human approval，不允许空 reviewer ID 产生 approved。
T15 菜单 pair 双阶段回答数与独立 pair 数分别统计。
T16 所有发表级图表来源于真实 run manifest，禁止绘制伪造主结果。
```

建议测试文件：`tests/unit/test_review_gates.py`、`tests/integration/test_automation_modes.py`、`tests/integration/test_human_data_separation.py`、`tests/unit/test_review_hash_invalidation.py`。自动化测试必须使用明确合成 fixtures，不能污染真实私有数据库。

### 9.1 状态报告格式（每轮自动输出）

```markdown
# BITE-Bench Run Status
- Working mode: hybrid_pilot
- Phase 0–11: <each existing phase status>
- Verified data rows: <measured count, not target>
- Approved food rows: <measured count>
- Menu eligibility: <measured numerator/denominator>
- Real participants: <actual count; don't include synthetic>
- Human taste train/test records: <actual counts>
- Human independent menu comparisons: <actual count>
- Local LLM: <model name/digest, measured GPU status or fallback>
- Completed synthetic smoke tests: <actual run references>
- Human-only blockers: <queue IDs and count>
- Next autonomous tasks: <specific modules that can proceed>
- Scientific results currently claimable: <precise limited scope>
```

这些字段应从数据库、日志和 manifest 计算生成，不由 LLM 手工填写想象值。

---

## 10. 供 Codex 使用的一段完整启动指令

> 阅读仓库内 `docs/RESEARCH_METHOD.md`、`docs/CODEX_PLAYBOOK.md`、`docs/AUTOMATION_ADDENDUM.md`，按规范继续开发 BITE-Bench。当前默认 `operation_mode=hybrid_pilot`，但是**首先运行 `synthetic_only` 的无真人依赖工程验证**。沿原 Phase 0–11 实现项目，优先完成 schema、FoodData Central 检索与数据审计、FoodBench-48 候选清单、审核队列、TasteNet、确定性 Oracles、四角色 Qwen Agent、M0–M4 对照和仿真。未获批准不得发起真人采集；不要伪造审核结果或人类选择。遇到食品身份/配方歧义，输出证据并加入 `docs/HUMAN_ACTIONS.md`；遇到缺少真实偏好，把正式人类评价标记 `BLOCKED`，继续所有独立工程工作。每个阶段执行单元与集成测试，更新 `docs/RUN_STATUS.md`、`docs/DECISIONS.md` 和 `artifacts/manifest.json`。不改变原研究公式、冻结划分或已明确约定的 M0–M4。优先在现有 Windows/WSL2+5060 环境上低风险运行；系统级配置修改需要明确授权。最终报告真实完成项、未完成项、实测资源开销和下一步最小人工任务。所有计划性 CLI 先实现后运行。

---

## 11. 修改现有两份文档的最小操作（可选，非必要）

**不需要重写原两份文档。** 为保证新 Agent 能发现补充协议，只建议在仓库内做三处非方法学修改：

1. 将本文件复制到 `docs/AUTOMATION_ADDENDUM.md`。
2. 在 `README.md` 或 `AGENTS.md` 顶部添加：**“开始前依次阅读 RESEARCH_METHOD.md、CODEX_PLAYBOOK.md、AUTOMATION_ADDENDUM.md。”**
3. 在 `docs/RUN_STATUS.md` 记录 `operation_mode`，默认 `hybrid_pilot`；首次未获真人同意时仅做 `synthetic_only` 测试。无须改变原 `protocol.lock.yaml`，也无须重新规划 48 食物、24 受试者、60 日菜单的正式目标。

如果以后真正改变了 TasteNet 方法、评分公式、预设样本规模或外部评价方法，才应该**同时修订原两份文档并增加协议版本号**。

---

## 12. 本补充协议的完成判据

- [ ] Codex 已把三份文件统一纳入仓库，并在 `AGENTS.md` 中指出相互关系。
- [ ] 能无真人数据跑完真实执行的 synthetic smoke，不留下伪造 human 结论。
- [ ] FoodBench 候选记录可自动检索、验证、风险分级并导出人工审核队列。
- [ ] 任何 `approved` 都有可审计审核凭据，审批结果随数据哈希变更失效。
- [ ] `hybrid_pilot` 可接收一个真人的真实偏好，并将其与 synthetic 分开存储。
- [ ] 真人 H1/H2 测试数据在使用前冻结，不能因单人模式而绕过防泄漏。
- [ ] 无人审核或缺真人答案不会阻断其他独立软件模块。
- [ ] 所有报告如实区分工程通过、合成实验、个人试点与正式多人结论。

**最终目标：把机器可以验证的重复劳动交给 Codex，把真正依赖人类的主观偏好、关键数据判断和研究伦理交还给人；在不牺牲实验真实性的条件下最大化自动化。**
