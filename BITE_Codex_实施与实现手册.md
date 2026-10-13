# BITE-Bench / Codex 执行与实验手册

> **Engineering Playbook · v1.0 · 2026-10-13**  
> 面向：Codex、Luna 或其他具有终端、文件系统、编程、测试能力的执行型 AI Agent。  
> 方法学上位规范：[BITE_研究方法与实验设计.md](./BITE_研究方法与实验设计.md)  
> 项目目标：在 RTX 5060 8GB、i5-13400F、32GB RAM、Windows 10 + 可选 WSL2 的机器上，从零建立可运行、可审计、可重现实验项目。

---

## A. 给执行 Agent 的任务合同：先读这一节

### A.1 你的身份与最终职责

你是本项目的软件工程师、ML 实验工程师和数据质量审计员，**不是负责虚构数据或论文结论的写手**。请先阅读研究规格书，保留其中 RQ1–RQ4 的含义，按本手册的依赖顺序实现数据层、TasteNet、营养数值底座、多 Agent、评价、模拟和论文图表。

**总原则：能在真实环境里验证的就实际运行；不能验证的明确写 `NOT RUN`、记录阻碍，并继续完成不依赖该阻碍的其他模块。** 不要为展示“完成度”模拟真人回答或伪造模型性能。不要替用户提交真实人体问卷，不要自动在公共渠道发布受试者数据。

### A.2 任务优先级

1. 科学协议不变：参考上位方法文件；工程中若发现公式不合理，写入 `docs/DECISIONS.md`，提交明确的改动理由，等待用户对**重大方法变更**确认。
2. 保证可运行：从 CPU-only + synthetic fixture 起步，保证整条管线没有隐形 GPU、API Key 或联网依赖。
3. 再验证真实依赖：FoodData Central、Ollama、Qwen、WSL/CUDA、可选 PyTorch。
4. 后续才进入真实参与者数据、正式性能比较和图表输出。
5. 不以“让所有模块都用 LLM”为目标；营养数值由代码保证，LLM 只提供角色化有限判断。

### A.3 明确禁止

- **禁止**编造 48 个食物的营养数值、参与者评分、实验得分、置信区间、计时或 VRAM 测量。测试夹具允许 `is_synthetic=true`，正式报告必须剔除。
- **禁止**将 API Key、受试者原始记录、私人联系方式或 `.env` 提交到 Git；禁止把食品来源或图片授权状态瞒写为已验证。
- **禁止**使用测试偏好来拟合用户口味、调整 Agent Prompt、选择权重、拟合校准参数或选择学习策略。
- **禁止**静默将未知营养成分设为零；未知状态必须显式传播，触发限制/拒绝/数据质量标记。
- **禁止**修改 Windows 驱动、启用需要重启的系统功能、打开公网监听端口或删除用户既有文件，除非获得明确授权。
- **禁止**自动训练/下载超出 8GB 显存预算的大模型；先量化、串行、限制上下文，并先测量。
- **禁止**以匿名同意记录不全的用户数据直接发布论文可复现包。

### A.4 日志与自动续接

项目根目录需要常驻维护三个文件：

- `docs/RUN_STATUS.md`：阶段、任务、最近执行命令、实测输出、已知阻碍、下一步。
- `docs/DECISIONS.md`：记录工程和方法权衡（日期、选项、证据、决策者、影响范围）。
- `artifacts/manifest.json`：记录每个结果的 `run_id`, config SHA256, dataset SHA256, code commit, model name/digest, seed, status, file paths。

每完成一个阶段，就更新这三个文件。如果会话中断，下一位 Agent 应能只阅读这三个文件和两个主文档，从断点继续；不要依赖聊天记忆。

**状态命名固定**：`NOT_STARTED`, `IN_PROGRESS`, `PASS`, `BLOCKED`, `FAILED`, `NOT_RUN`。不能在任何真实采集未完成的情况下将正式 RQ1/RQ2 标为 `PASS`。

---

## B. 部署目标与前置核验

### B.1 已知硬件，不得擅自扩大假定

- Windows 主机：`Windows 10 Pro 19045`；CPU `Intel Core i5-13400F`；RAM `32GB`；GPU `NVIDIA GeForce RTX 5060, 8GB`；SSD 约 `1TB`。
- 用户通过 SSH/Tailscale 远程管理，网络端口应默认只对 localhost 绑定。**不要改变现有 SSH 或 Tailscale 配置**。
- 用户是否已安装 WSL2、Ubuntu、uv、Ollama、PyTorch、GPU 内存可用量：**必须通过命令核验**，不要猜。

### B.2 第一轮安全侦测命令（PowerShell，逐条执行）

```powershell
Get-ComputerInfo | Select-Object WindowsProductName, WindowsVersion, OsBuildNumber
nvidia-smi
wsl --status
wsl -l -v
Get-Command uv, git, ollama, python -ErrorAction SilentlyContinue | Select-Object Name, Source
Get-PSDrive C
```

若 WSL 不存在，只报告缺失和安装前置需求；安装 WSL、修改 BIOS 虚拟化、重启需要用户明确许可。WSL2 初始化可参考：

```powershell
# 仅在确认已经得到授权、并核实 Windows 支持后执行
wsl --install -d Ubuntu-22.04
wsl --update
wsl -l -v
```

**关键**：NVIDIA 官方要求 WSL 内不要另装 Linux NVIDIA 驱动；GPU 由 Windows 驱动映射。若执行 `nvidia-smi` 在 WSL 内找不到，尝试 `/usr/lib/wsl/lib/nvidia-smi`，结合 WSL/Windows 版本分析；不要通过安装 `nvidia-driver-*` 来碰运气。

参考：https://docs.nvidia.com/cuda/archive/12.8.1/wsl-user-guide/index.html

### B.3 推荐运行模式与降级路径

| Mode | 前置依赖 | 可以完成 | 不能声称 |
|---|---|---|---|
| `mock` | Python、基础数据包、合成小样本 | 全链路单元测试、营养计算、CLI、流程演示 | 真实模型/人类性能 |
| `cpu_real` | 真实营养数据、真实偏好数据 | TasteNet 的轻量训练与正式评估、规则基线 | 真实 Multi-Agent 优劣（若未使用 LLM） |
| `local_llm` | Ollama 可用，Qwen 推理通过测试 | Agent 调用、讨论、M0–M4 比较 | 人类对齐优势（若未采集独立菜单评价） |
| `full` | 上述均完成且独立测试数据冻结 | 主实验、消融、长时程模拟与论文结果 | 现实医学健康结论 |

**最重要的降级规则**：WSL/CUDA 未通过不应阻挡 FoodBench schema、CLI、TasteNet CPU 基线及单元测试。可以转向 Windows 原生 Ollama + 本地 Python 做阶段性验证，但要记录使用了哪一种宿主/客体模式，尤其注意 Windows/WSL 不应重复加载不必要的模型实例。

### B.4 WSL/Ubuntu 内检查

```bash
uname -a
python3 --version
command -v uv || true
command -v nvidia-smi || true
/usr/lib/wsl/lib/nvidia-smi || true
free -h
pwd
```

如 WSL 已可用，建议源码放在 Linux 文件系统 `~/projects/bite-bench`，不要默认在 `/mnt/c/...` 建立数据量较大的模型项目。代码数据可按用户意愿配置独立备份；不要自行删除已有仓库。

### B.5 Python 与依赖管理

采用 **Python 3.11 或 3.12 + uv**，以单一 `pyproject.toml` 和 `uv.lock` 管理依赖。初版核心依赖：

- `numpy`, `pandas`, `scipy`, `scikit-learn`, `pydantic>=2`, `typer`, `PyYAML`, `httpx`, `matplotlib`, `seaborn`, `rich`, `pyarrow`。
- 开发测试：`pytest`, `pytest-cov`, `ruff`, `mypy`（类型检查可逐步推进）。
- 可选 UI：`streamlit`（仅本地），或 FastAPI + 简单页面（若做 web 游戏）。
- 可选模型：`torch`，先确认兼容 GPU/驱动/wheel 再装，不影响 SciPy 版 TasteNet。
- Ollama 访问：优先直接 `httpx` 请求本地 `/api/chat`；是否添加官方 `ollama` Python 包由工程一致性决定。

建议初始化：

```bash
mkdir -p ~/projects/bite-bench
cd ~/projects/bite-bench
uv init --name bitebench --package --python 3.12
uv add numpy pandas scipy scikit-learn 'pydantic>=2' typer pyyaml httpx matplotlib seaborn rich pyarrow
uv add --dev pytest pytest-cov ruff mypy
uv sync
uv run python --version
uv run python -c "import bitebench; print(bitebench.__file__)"
```

`uv` 未安装时按官方 https://docs.astral.sh/uv/getting-started/installation/ 安装，先检验操作系统、访问权限和已安装版本。不要把 `curl | sh` 作为无条件自动执行步骤。Python GPU 仅在需要时装，并以 https://pytorch.org/get-started/locally/ 选择当前支持的 CUDA wheel；切勿根据 `nvidia-smi` 的“CUDA Version”臆测 pip 安装参数。

---

## C. 推荐仓库布局（严格对齐）

```text
bite-bench/
├── README.md
├── AGENTS.md                         # Codex 自动执行契约（从本文件摘录）
├── pyproject.toml
├── uv.lock
├── .gitignore
├── .env.example
├── config/
│   ├── default.yaml
│   ├── diet_profiles.yaml
│   ├── rubric_v1.yaml
│   ├── taste_models.yaml
│   ├── agents.yaml
│   ├── experiment_plan.yaml
│   └── protocol.lock.yaml           # 冻结研究参数，正式实验不可临时修改
├── docs/
│   ├── RESEARCH_METHOD.md           # 上位方法文件的本地复制
│   ├── CODEX_PLAYBOOK.md            # 本文档的本地复制
│   ├── DATA_DICTIONARY.md
│   ├── ANNOTATION_GUIDE.md
│   ├── RUN_STATUS.md
│   └── DECISIONS.md
├── data/
│   ├── fixtures/synthetic/          # 小规模合成样本，禁止进入真人实验结果
│   ├── curated/                     # 经人工核查的食物数据
│   ├── raw/                          # 原始下载/标注（默认不提交）
│   ├── private/                      # 真实参与者答案（强制 gitignore）
│   ├── splits/                       # 冻结 train/val/test ID & hashes
│   └── menus/                        # 60 份经审核的日菜单
├── src/bitebench/
│   ├── __init__.py
│   ├── cli.py                        # 统一命令入口 bite
│   ├── config.py
│   ├── core/
│   │   ├── schemas.py               # Food, Meal, DayPlan, TastePair, Score
│   │   ├── hashing.py
│   │   ├── seeds.py
│   │   └── validation.py
│   ├── data/
│   │   ├── usda_client.py
│   │   ├── openfoodfacts_client.py
│   │   ├── recipe_builder.py
│   │   ├── curation.py
│   │   ├── splits.py
│   │   └── io.py
│   ├── labeling/
│   │   ├── protocol.py
│   │   ├── pair_selector.py
│   │   ├── storage.py
│   │   └── ui.py
│   ├── taste/
│   │   ├── features.py
│   │   ├── global_bt.py
│   │   ├── feature_bt.py
│   │   ├── personalized.py
│   │   ├── calibration.py
│   │   ├── inference.py
│   │   └── metrics.py
│   ├── nutrition/
│   │   ├── units.py
│   │   ├── calculator.py
│   │   ├── oracle.py
│   │   └── constraints.py
│   ├── agents/
│   │   ├── llm_backend.py
│   │   ├── prompts.py
│   │   ├── agent_t.py
│   │   ├── agent_n.py
│   │   ├── agent_f.py
│   │   ├── agent_l.py
│   │   ├── schemas.py
│   │   ├── protocols.py
│   │   └── aggregator.py
│   ├── evaluation/
│   │   ├── human_alignment.py
│   │   ├── comparison.py
│   │   ├── bootstrap.py
│   │   └── ablation.py
│   ├── simulation/
│   │   ├── environment.py
│   │   ├── policies.py
│   │   ├── evaluator.py
│   │   └── runners.py
│   ├── reporting/
│   │   ├── figures.py
│   │   ├── tables.py
│   │   └── provenance.py
│   └── util/
│       ├── cache.py
│       └── logging.py
├── tests/
│   ├── unit/
│   ├── integration/
│   ├── contract/
│   ├── regression/
│   └── fixtures/
├── scripts/
│   ├── check_environment.py
│   ├── run_smoke.sh
│   └── freeze_protocol.py
├── outputs/                        # 自动生成，不作为事实来源
│   ├── checkpoints/
│   ├── runs/
│   ├── figures/
│   ├── tables/
│   └── reports/
└── artifacts/
    └── manifest.json
```

`.gitignore` 至少：`.venv/`, `.env`, `data/raw/`, `data/private/`, `outputs/`, `__pycache__/`, `.pytest_cache/`, `*.pyc`；如经授权将输出 Git LFS/外部存储再单独配置。**不要将已验证的 `data/curated` 及合法可发布小样本无脑忽略**。

`pyproject.toml` 应注册命令入口（根据仓库使用的 build backend 调整）：

```toml
[project.scripts]
bite = "bitebench.cli:app"
```

`uv run bite --help` 是项目健康检查的一部分。CLI 以 Typer 子命令定义，严格避免同一命令名在不同阶段改变含义。`uv init` 的项目名必须是 `bitebench`（而不是默认从 `bite-bench` 推导出来的 `bite_bench` 包名）；如已生成 `src/bite_bench/`，应同步修改包路径与打包配置，直至 `import bitebench` 成功。

---

## D. 数据契约：先确定 schema，再实现模型

### D.1 文件格式约定

- 结构化可审计输入：`CSV`/`Parquet` + schema；所有外部接口使用 `pydantic` 对象。
- 计算结果：`Parquet` + 同名 `metrics.json`，统一 `run_id` 与 `source_hash`。
- 配置：YAML；最终实验由 `protocol.lock.yaml` 和生成时的 SHA256 冻结。
- 原始 LLM 输入/输出：存 `outputs/runs/<run_id>/llm_audit.jsonl`，只存已匿名化的模型上下文、角色、提示词版本、输出、耗时和使用 token。含私人受试者信息的审计日志仅本机私有存储。
- 时间使用含时区的 ISO 8601；单位在字段名中表明；没有测量的字段使用 `null`。

### D.2 FoodVariant 最小 Pydantic 规范

建议定义：

```python
class FoodVariant(BaseModel):
    food_id: str
    name_zh: str
    name_en: str | None = None
    primary_category: str
    recipe_variant: str
    serving_g: float                   # > 0
    energy_kcal_per_100g: float | None
    protein_g_per_100g: float | None
    fat_g_per_100g: float | None
    carbs_g_per_100g: float | None
    fiber_g_per_100g: float | None
    sodium_mg_per_100g: float | None
    fruit_veg_g_per_serving: float | None  # 仅有可核查构成时填写
    source_system: str
    source_record_id: str | None
    source_url: str | None
    retrieved_at: str | None
    data_quality: str                  # verified_label / database / recipe_estimate / unknown
    image_path: str | None = None
    image_license: str | None = None
    is_synthetic: bool = False
```

加 validator：`serving_g>0`；营养值如非空不得负数；`fruit_veg_g_per_serving` 不得超过 `serving_g`；`source_system` 不能空；对 `data_quality=database` 必须可追踪来源 ID/URL。能量等字段为 `None` 时，正式评分应中断或标记该菜单不可计分。

### D.3 菜单协议

```python
class MealItem(BaseModel):
    food_id: str
    servings: float                    # >0; e.g. 1.5 servings

class Meal(BaseModel):
    meal_id: str
    slot: str                          # breakfast/lunch/dinner/snack
    items: list[MealItem]

class DayPlan(BaseModel):
    menu_id: str
    meals: list[Meal]
    profile_id: str                    # 画像 ID
    history_ref: str | None = None
    is_synthetic: bool = False
```

`servings` 以数据库标准份量为单位，不与“克”混淆：每份摄入克数 = `serving_g * servings`。每个 `food_id` 必须在数据库中；菜单生成时不得混用原料级和菜品级 ID，避免重复计算。可选 `price` 不进入 v1.0 主指标。

### D.4 偏好协议

```text
user_id, pair_id, left_food_id, right_food_id, choice,
assignment_group, query_policy, split, seen_left, seen_right,
self_reported_hunger, display_order_seed, timestamp, is_synthetic
```

`choice ∈ {left, right, tie, skip}`。`split ∈ {train, val, test}`。标注存储须同时记录**实际展示的左右顺序**；训练时只能按 food_id 的固定对称表示和 choice 决定正负标签，避免方向偏差。对相同 `(u, a, b)` 重复记录不视为新独立样本；可检查一致性。

### D.5 LLM Agent 合同

响应 JSON Schema 的核心字段：

```json
{
  "role": "T",
  "adjustment": 4.0,
  "evidence_ids": ["taste_food_003", "menu_lunch"],
  "rationale": "该组合在给定偏好下有较好的口味互补性。",
  "needs_review": false,
  "issue_codes": []
}
```

实际 JSON 中 T/L 的 `adjustment` ∈ `[-10,10]`；N/F 必须输出 `adjustment=0`，只输出解释和异议标记。若违约，记录失败、不接受其输出；最多修复/重试两次后使用明确 fallback。不允许多次重试直到出现“漂亮的分数”。

对汇总结果至少定义：

```text
run_id, menu_id, user_or_profile_id, method,
q_t_base, delta_t, q_t, q_n, q_f, q_l_base, delta_l, q_l,
weighted_pre_penalty, violation_penalty, total_0_100,
eligibility, unknown_fields, warnings, provenance, is_synthetic
```

`eligibility ∈ {eligible, ineligible, insufficient_data}`。`insufficient_data` 时 `total_0_100=null`，不是 0。

---

## E. 参数文件：把研究决策和代码分离

### E.1 `config/rubric_v1.yaml` 推荐起点

**重要**：以下是供实现起步的**人为游戏规则**，不代表科学认可的个人营养需求；后续论文应原样报告并做敏感性分析。

```yaml
version: rubric_v1
score_range: [0, 100]
scoring_level: day
profiles:
  balanced:
    taste: 0.35
    nutrition: 0.30
    fitness: 0.20
    long_term: 0.15
  hedonist:
    taste: 0.60
    nutrition: 0.15
    fitness: 0.10
    long_term: 0.15
  fitness:
    taste: 0.20
    nutrition: 0.25
    fitness: 0.40
    long_term: 0.15
  long_termist:
    taste: 0.25
    nutrition: 0.30
    fitness: 0.15
    long_term: 0.30
reference_goals:
  # 虚拟成人示例，仅用于 benchmark；不是给真人设定的营养处方
  energy_target_kcal: 2000
  protein_target_g: 90
  fiber_target_g: 25
  sodium_upper_mg: 2000
  fruit_veg_target_g: 400
  energy_tolerance_fraction: 0.25
nutrition_penalty_weights:
  low_fiber: 35
  high_sodium: 35
  low_fruit_veg: 30
fitness_penalty_weights:
  energy_target_deviation: 60
  protein_shortfall: 40
long_term:
  warmup_score: 75
  repetition_penalty_max: 50
  category_gap_penalty_max: 50
  target_unique_categories_7d: 6
agent_adjustment_bounds: [-10, 10]
soft_violation_lambda: 0.0   # v1 启动阶段未启用附加软惩罚，避免重复扣分
hard_constraints:
  reject_unknown_required_nutrients: true
  reject_user_excluded_foods: true
required_nutrients:
  - energy_kcal
  - protein_g
  - fiber_g
  - sodium_mg
  - fruit_veg_g
```

每个画像在 v1.0 可以共享**虚拟参考目标**，改变价值权重；如 later 做增肌、减脂，则单独定义 `energy_target`, `protein_target`, `limits` 并将虚拟目标写清。不要自动根据用户真实身体信息推算目标。

### E.2 Oracle 数学定义（给工程师一个唯一实现）

首先把每项食物的按份营养求和为 `E, P, FIB, NA, FV`：

```text
shortfall(x,target) = clip((target-x)/target, 0, 1)
excess(x,upper)    = clip((x-upper)/upper, 0, 1)
deviation(x,target,tol) = clip(abs(x-target)/(tol*target), 0, 1)
```

则：

```text
q_N = clip(100
   - 35 * shortfall(FIB, fiber_target)
   - 35 * excess(NA, sodium_upper)
   - 30 * shortfall(FV, fruit_veg_target), 0, 100)

q_F = clip(100
   - 60 * deviation(E, energy_target, 0.25)
   - 40 * shortfall(P, protein_target), 0, 100)
```

上述函数的 `target>0`，否则报配置错误；所有 `E/P/FIB/NA/FV` 必须完整，否则状态是 `insufficient_data`。用户设定的禁忌食物、项目内部上限等硬约束必须独立判断，不得用高 Taste 分抵销。该 `q_N` 只代表**选定的有限营养指标**，并非完整膳食质量，更不是医学诊断。FAO/WHO 指导提供基本原则，但系数 35/35/30 是研究者假设，必须消融。

`q_T_base`：一个 meal 中每道**完整菜品**的 `TasteNetScore` 等权平均；day 的各个 meal 均值等权平均（固定三主餐及必要时 snack 的归一化逻辑）。`q_L_base`：没有历史时设为 75 且 `history_cold_start=true`；有历史时，计算最近 7 天重复比例 `repeat_ratio` 和食物类别覆盖率 `unique_category_count`，公式：

```text
q_L_base = clip(100
    - 50 * repeat_ratio
    - 50 * clip((6 - unique_category_count)/6, 0, 1), 0, 100)
```

`repeat_ratio` 必须有明确可复现定义：过去七天日菜单中，**同一完整菜品在首次出现以外的出现次数** / 这七天的菜品总出现次数，均按 food_id 计数。不能跨不同标准份量或近义名称偷偷合并。选择新一天前计算历史分数时，把**候选当日饮食临时加入窗口**，所有候选采用同一规则；首次历史空白时按统一 warmup=75。保证窗口长度不足 7 天时以实际已观测天数计算，并记录天数。

### E.3 分数计算顺序

1. 验证输入、份量、用户禁忌、营养所需字段；无法评分返回 `insufficient_data/ineligible`。
2. TasteNet 输出每道菜分数和可靠性；组装 `q_T_base`。
3. Nutrition Engine 计算 `q_N`, `q_F`；History Engine 计算 `q_L_base`。
4. 运行所选 Agent 协议，应用有界调整 `delta_T`, `delta_L`；N/F 只解释。
5. 根据画像权重加权，减去有定义的附加软约束惩罚（v1 默认为零），`clip[0,100]`。
6. 生成完整的评分拆解、证据链、模型 digest、运算规则版本和 warnings。

对于未来多个食物的完整 meal 组合，先以人工评价检查简单等权的稳健性；**不要让大模型在未验证时隐式改变同餐菜品权重**。

---

## F. 阶段计划：每一步都设完成门槛（Stage Gates）

> 下面的 CLI 命令是**要求 Codex 实现的项目接口**，并非宣称这些命令现在已经存在。先实现对应模块，再运行命令。任务若受真实参与者/API 权限等条件阻挡，应产出完整代码和 `BLOCKED` 记录，而不是杜撰输入填上。

### Phase 0 — 环境侦测和仓库启动

**目标**：所有执行的硬件假设有证据；建立可复现 Python 环境和 Git 项目。

执行：

1. `nvidia-smi`, `wsl -l -v`, `uv --version`, `git --version`，存日志 `outputs/reports/environment_probe.txt`。
2. 如 WSL 已启用，在 WSL Linux 家目录创建项目；如没有 WSL，不强行安装，先搭建 Windows CPU-only 路线。
3. `uv init`, 创建目录、 `.gitignore`, `.env.example`（只含变量名和注释，不含真实密钥），注册 `bite` CLI，创建 `README` 与三份进度记录。
4. 安装核心依赖，执行 `uv sync`、`uv run pytest`（此时至少 smoke test）。
5. 编写 `bite env doctor --json`，输出 Python、platform、torch CUDA 可用性（如已安装）、Ollama 状态、GPU 信息（若能访问）、数据目录写入权限，所有失败以字段 `ok=false` 返回而不让 CLI 崩溃。

验收：

```bash
uv run bite --help
uv run bite env doctor --json
uv run pytest -q
```

产物：`pyproject.toml`, `uv.lock`, `docs/RUN_STATUS.md`；最少 1 条测试通过；无人工问卷依赖。**不得在本阶段因 GPU 不可用而失败整个项目**。

### Phase 1 — Schema / Mock 数据 / 数学单元测试

**目标**：用五个合成食物、两个合成菜单和两个合成用户，在完全断网情况下打通数据契约。

执行：

1. 实现 Pydantic schema、输入转换、哈希、随机种子、配置加载。
2. 明确营养单位 `g / mg / kcal` 和输入标准份量。
3. 编写 `scripts/build_synthetic_fixtures.py`，生成 `data/fixtures/synthetic/*.csv|json`，每条均 `is_synthetic=true`。
4. 实现四种主要异常：营养缺失、无效份量、不存在的 food_id、超出限制的调整值。每一种都应被测试覆盖。
5. 先用纯 Python/NumPy 做 Nutrition Engine 和 Aggregator，确保同样输入得到同样结果。

验收：

```bash
uv run python scripts/build_synthetic_fixtures.py
uv run bite data validate --input data/fixtures/synthetic/foods.csv --allow-synthetic
uv run pytest tests/unit -q
```

最低通过测试：

- 200 g、每 100 g 120 kcal 的食物，计算出 240 kcal。
- 每 100 g 的 Na 是 `mg`，不会被当成盐的 `g`。
- `fiber=None` 不变成 0；正式菜单状态为 `insufficient_data`。
- 一天餐食能量总量等于各项累加；份量乘系数 `servings` 正确。
- 四项权重加和不是 1、负权重、NaN、无限值时拒绝加载配置。
- 分数最终在 `[0,100]` 且输出 `q_t,q_n,q_f,q_l`；无法评分的结果 `total=null`。
- 比较 `(A,B)` 调换左右且反转真实选择后，BT 损失相等（方向不变性）。

### Phase 2 — 可追踪食物数据 / USDA 集成 / FoodBench-48

**目标**：搭建可审计的数据录入、外部检索和菜单校验系统。**人工审核未完成之前不能声称 48 个食物已经全部真实建立。**

建议命令：

```bash
# 在 .env 配置 USDA_FDC_API_KEY=...，绝不打印密钥
uv run bite data usda-search --query "broccoli raw" --limit 10
uv run bite data usda-fetch --fdc-id <VERIFIED_FDC_ID> --out data/raw/usda/
uv run bite data validate --input data/curated/foodbench48.csv
uv run bite data report --input data/curated/foodbench48.csv --out outputs/reports/food_data_quality.json
```

落实细则：

1. 食物清单先在 `data/curated/food_candidate_manifest.csv` 创建 48 行，`food_id` 稳定且不可复用；只填候选名称/计划类别，不填不存在的营养值。
2. USDA 请求 `https://api.nal.usda.gov/fdc/v1/foods/search` 或 `.../food/{fdcId}`，使用 `USDA_FDC_API_KEY`，缓存原始响应（带查询参数但密钥必须脱敏）；出现 429 时指数退避并尊重服务器限速。
3. 编写从 USDA nutrient ID/名称向 canonical 字段的映射表与**单元测试**，确认 Energy(kcal) 与 kJ 的区分；不要仅凭字面相似直接采信。记录 per-100g 与 per-serving 转换依据。
4. 对中餐/复合菜品，用 `recipe_builder` 保存原料、份量、产出净重和油盐假设。若数据不能支持 `fiber/sodium/fruit_veg`，保留未知并列入阻碍；可用同样可追溯的配方方法补全。
5. 手工审核 48 行的数据来源、烹饪变体、常见份量与可食部分；有授权的图片再添加，首次 CLI 和模型可用文字表示。
6. 创建 60 份候选日菜单的 manifest，从可核查食物中组合，按约定画像计算日能量与营养，区分 `reference_valid`, `stress_case`, `insufficient_data`，对每份给出采样理由。
7. 每次改动食品数值，都生成数据 SHA256/版本号；主实验锁定版本，不允许“查到新热量”自动覆盖已有测试输入。

验收：

```bash
uv run bite data validate --input data/curated/foodbench48.csv --strict
uv run bite menu validate --input data/menus/day_menus.csv --food-data data/curated/foodbench48.csv
uv run pytest tests/contract tests/unit -q
```

**门槛**：关键营养字段、来源、份量、单位全部符合规则；数据质量报告清晰列出 `verified/database/recipe_estimate`；48 和 60 的实际数量以及通过数写入状态文件。无法满足时进入下一阶段的 demo 可继续，但正式实验保持 `BLOCKED`。

### Phase 3 — 偏好问卷与主动学习小游戏

**目标**：实现真正能采集人类二选一数据的本地界面，并在采集前冻结 test set。

推荐 `Streamlit`，最少包含：

1. **Consent/说明页面**：18+、志愿、非医学建议、数据使用范围、可退出/删除；不收集真实姓名。
2. **匿名 ID 页面**：生成 UUIDv4，提供本地导出用户 token 供撤回；不要求邮箱或手机号。
3. **Taste Choice 页面**：食物 A/B、标准份量、图片及许可归属、3 个按钮（左/右/差不多）+ 跳过；不显示热量。
4. **Anchor Rating 页面**：8 道训练锚点美味 0–10 评分；界面标注“预计好吃程度”，不是“已试吃后的真实味觉”。
5. **Menu Preference 页面**：同一个日菜单对的营养隐藏、公开两个评测任务；显示食物构成和标准份量，第二步才显示核查过的营养。
6. **完成页面**：显示已完成数量和匿名 token；不公布他人个人回答。

推荐采样顺序：

```text
建立参与者随机 ID
  ↓
固定全局 heldout_food_ids + 每人 test 10 pairs（不显示答案给算法）
  ↓
训练前 20 个覆盖性 anchor comparisons
  ↓
另 20 个（主动学习策略 / 随机策略，参与者事先分组）
  ↓
冻结 test 10 个 comparisons 的回答
  ↓
8 个直接美味 anchor 评分（避免 test 冷食物）
  ↓
独立菜单评分问卷（正式测试阶段与调参隔离）
```

测试题应在参与者的整个流程设计之初冻结；如果为了体验把测试安排在后段展示没问题，但训练算法不能读取其答案。问卷的本地 SQLite 存储应具有唯一性约束 `(user_id,pair_id,stage)` 和事务，确保重复刷新页面不会无声重复统计。

**主动学习实现**：给每个候选 `(a,b)` 计算当前预测 `p`，用 `p*(1-p)` 作为最简单的不确定性采样；添加覆盖约束、禁止重复对比、禁止测试食物/测试 pair，保存每次候选池 hash、模型状态 hash、被选中的 pair 和策略版本。`tie/skip` 不等同 50%/随机标签；预先指定排除或特定似然处理。

**非常重要的分组局限**：24 人×（12 active/12 random）可能不足以稳定比较主动学习。v1 报告探索性结果，不因没显著差异就改 test。若真实参与者尚不可用，请实现 UI、加入虚构录入 fixture、测试数据库与导出，但记 `HUMAN_STUDY=BLOCKED`。

验收：

```bash
uv run bite split freeze --config config/experiment_plan.yaml --out data/splits/
uv run bite label app --mode synthetic
uv run bite label export --source data/fixtures/synthetic/labels.sqlite --out outputs/reports/synthetic_labels.csv
uv run pytest tests/integration/test_labeling.py tests/unit/test_pair_selector.py -q
```

须有自动测试证明：测试 pairs 不可能被主动提问抽到；标签写入不能双计；左右交换逻辑正确；导出文件保留 `is_synthetic`；用户撤回 token 能定位并删除其数据（私人库中）。

### Phase 4 — TasteNet Baselines、个性化模型与模型评价

**目标**：先实现全球 BT、特征 BT，再做个性化；每个模型都能产生相同格式的 `predict_pair` 和 `predict_food` 输出。

建议 API（伪签名，落实为实际 Python 对象）：

```python
class TasteModel(Protocol):
    def fit(self, training_pairs, food_features, ratings=None) -> None: ...
    def predict_pair(self, user_id: str, left_food_id: str,
                     right_food_id: str) -> float: ...  # P(left preferred)
    def predict_food(self, user_id: str, food_id: str) -> dict: ...
    def save(self, path) -> None: ...
```

实现次序：

1. `GlobalBT`：对训练出现的食品学习 centered scalar utility，添加 L2、零中心约束防不辨识；新食物回退先验。
2. `FeatureBT`：食物 one-hot 主类 + 配方文本的可审计词袋或简易特征（不需要外部 encoder）。训练/测试特征词表必须只由 train 拟合。
3. `Personalized`：`s(u,i)=mu_i+beta·z_i+p_u^T W z_i`；考虑数据规模，低秩 `d=4` 起步，用户嵌入强正则；与全球 BT 相同训练预算，至少 3 个训练种子。
4. `Calibration`：仅用训练锚点 0–10 分拟合从 utility 到 0–100 的单调映射。拟合映射不能使用任何测试问题或新食物测试评分。新食物效用校准时适用同一映射。
5. `Uncertainty`：先通过训练数据 Bootstrap/多种子集合给相对分数区间；实现主指标 NLL/Brier 的明确算法。若 bootstrap 只有有限采样，应明示近似。
6. `Cold Food Eval`：未出现在训练比较和标定数据中的 `heldout_food_ids` 必须单独报告；特征模型和群体常量模型的差异是重点。
7. `Active Learning Study`：基于线上真实日志的实验分组，按预算绘制测试 NLL；无真实问卷时仅做合成 sanity check，不能得出效果结论。

目标 CLI：

```bash
uv run bite taste train --model global_bt --config config/taste_models.yaml --seed 17
uv run bite taste train --model feature_bt --config config/taste_models.yaml --seed 17
uv run bite taste train --model personalized --config config/taste_models.yaml --seed 17
uv run bite taste evaluate --split test --all-models --out outputs/runs/taste_eval/
uv run bite taste predict --user-id demo_u1 --food-id demo_f1 --checkpoint outputs/checkpoints/...
```

**测试样例**：

- 只要训练数据始终偏好 A > B，模型应该学出 `P(A>B)>0.5`（数据量与正则适当时）。
- 将所有训练 pair 顺序反转并反转标签，应保持预测等价。
- `heldout_food_id` 从未在训练参数 `mu_id` 中出现；新食物只靠特征泛化。
- 没有直接评分数据，`predict_food` 不能擅自输出自称校准的 0–100 值；返回 `uncalibrated` 或使用显式先验并阻断正式 BITE 评分。
- 每个测试指标输出 `n_users`, `n_pairs`, `n_cold_food_pairs`, `seed`, `ci_method`, `synthetic_flag`。

**失败条件**：用 test 选择低秩维度、正则、校准方法；仅展示一个成功种子；使用全数据生成特征字典导致标签泄漏。

### Phase 5 — Nutrition Oracle / Fitness Oracle / History Oracle

**目标**：完整实现 E.2 的确定性规则、客观约束和来源追溯。

实现方式：

1. `calculator.py`：向量化加总每份营养；数值以 Decimal/浮点一致测试控制误差，例如绝对误差 `1e-6`，不要求全程 Decimal。
2. `oracle.py`：固定 `q_N` 与 `q_F`；输入虚拟画像 profile 的目标和日菜单。
3. `history.py`（如需可新建）：固定 7 天滑窗、重复率与类别数，按当前候选形成 `q_L_base`；没有历史统一给 75。
4. `constraints.py`：hard invalid（用户排除食物、缺营养等），soft warnings（可选），结构化 `eligibility`。
5. 为所有分数提供完整分量分解，不能只返回一个浮点数。

CLI：

```bash
uv run bite nutrition score-day --menu-id demo_day_01 --profile balanced --mode synthetic --json
uv run bite nutrition audit --menu-file data/menus/day_menus.csv --report outputs/reports/menu_audit.json
uv run pytest tests/unit/test_nutrition.py tests/unit/test_oracle.py -q
```

单元测试例：

- 在 `FIB=25, NA=2000, FV=400` 时，Nutrition 得 100；若输入 NA 增加，其他不变，qN 不得上升。
- 在 `E=2000, P>=90` 时，Fitness 得 100；`E=0` 不得自动获得 Fitness 100。
- 当 7 天反复出现同 `food_id` 时，`repeat_ratio` 不得减小；同一天加相异菜品时类别覆盖不能错误下降。
- 第一天历史为空给定 75，同时 `history_cold_start=true`；同一个候选在同一历史下得分一致。
- `delta_T >10`, `delta_L <-10` 导致 schema 拒绝；NaN 不得进入最终评分。

### Phase 6 — Ollama 与 Qwen 4-bit 本地运行

**目标**：在用户 RTX 5060 上尽量保持单实例推理，得到符合 schema 的本地 Agent 响应。若未能运行，则明确降级，不造数据。

#### F.6.1 Ollama 检查与模型安装

Ollama 文档：https://docs.ollama.com/  
模型页面：https://ollama.com/library/qwen3:4b-instruct-2507-q4_K_M

```bash
# 假设 Ollama 已成功安装且当前 shell 能访问命令
ollama --version
ollama list
curl -fsS http://127.0.0.1:11434/api/tags
# 在确认容量、网络下载和可用权限后拉模型
ollama pull qwen3:4b-instruct-2507-q4_K_M
ollama show qwen3:4b-instruct-2507-q4_K_M
```

模型页面展示约 2.5GB 模型文件；不能把这个数视作实际 VRAM。建议初始 `num_ctx=4096`, `num_predict=256`, `temperature=0`，串行请求；实际显存和 token/s 通过 `nvidia-smi` 与调用日志记录。不可照搬模型页面中的 256K context 上限在 8GB GPU 上运行。

如果 Ollama 装在 Windows，WSL 内是否能直接 `127.0.0.1:11434` 访问要实际测试；不成功时优先考虑 WSL 内独立安装或显式安全的主机访问路径，**禁止为省事把 Ollama 绑定到 `0.0.0.0` 公网地址**。不要同时运行 Windows 与 WSL 的两份 Qwen 模型消耗显存。

#### F.6.2 HTTP + JSON Schema 示例

以下示例只演示网络合同；真实结构以 `agents/schemas.py` 的 Pydantic v2 为准：

```python
import httpx
from pydantic import BaseModel, Field

class AgentReport(BaseModel):
    role: str
    adjustment: float = Field(ge=-10, le=10)
    evidence_ids: list[str]
    rationale: str
    needs_review: bool
    issue_codes: list[str]

payload = {
    "model": "qwen3:4b-instruct-2507-q4_K_M",
    "messages": [
        {"role": "system", "content": "仅使用提供的证据，返回符合 Schema 的 JSON。"},
        {"role": "user", "content": "请依据已知营养和偏好报告给出角色判断，别生成营养数值。"}
    ],
    "stream": False,
    "format": AgentReport.model_json_schema(),
    "options": {"temperature": 0, "num_ctx": 4096, "num_predict": 256}
}
r = httpx.post("http://127.0.0.1:11434/api/chat", json=payload, timeout=180)
r.raise_for_status()
report = AgentReport.model_validate_json(r.json()["message"]["content"])
print(report.model_dump())
```

防护：validate agent role、`evidence_ids` 是否确实存在于当前菜单特征中；拒绝为 N/F 提交非零调整；超时、HTTP 失败、非法 JSON 时依规则有限重试，最终回退 `delta=0` 并标明失效。Prompt 应当阻止从菜单名称或参与者文本接收“忽略此前规则”之类的提示注入指令。

#### F.6.3 性能探针

实现：

```bash
uv run bite agents smoke --backend ollama --profile balanced --mode synthetic
uv run bite agents bench --n 20 --num-ctx 4096 --out outputs/reports/ollama_bench.json
```

记录 `model`, `digest`, quantization, runtime/backend, prompt tokens, completion tokens, seconds, tokens/sec, peak VRAM（若可见）, fallback_count, malformed_json_count`。实际采样必须记录机器是否同时运行其他负载。

**门槛**：10 个结构化 smoke case 中正确输出或正确受控回退 10/10；不能把“模型完全没有响应但都回退了”当作 LLM 正常可用——有效 LLM 响应率也须单独达到预设门槛（建议 `>=90%`），并记录任何错误。

### Phase 7 — Multi-Agent 三种协议 + 预算公平对照

**目标**：实现 M0/M1/M2/M3/M4，不改写营养事实。

协议详情：

```text
input = {menu, user/profile, TasteNet predictions, nutrition oracle,
         fitness oracle, frozen history stats, evidence dictionary}

M0 deterministic:
    delta_T = delta_L = 0
    q_N, q_F from oracle; q_T_base and q_L_base as defined

M1 single_agent:
    one LLM sees all evidence, proposes bounded delta_T, delta_L
    q_N/q_F unchanged

M2 independent_multi_agent:
    T/N/F/L each see same base facts + domain-specific instructions
    aggregate independent judgments; N/F adjustment always 0

M3 deliberative_multi_agent:
    run M2 first, build structured summary of disagreement/review flags
    at most one additional revision round for affected T/L roles
    N/F can flag evidence issues but cannot replace values
    output both before/after to audit

M4 budget_matched_single_agent:
    same data as M3, up to comparable total generated tokens/calls
    output same bounded adjustment fields; q_N/q_F unchanged
```

评分算式唯一放在 `agents/aggregator.py`，不能在每个 Agent 文件各写一套。正式比较期间，模型名称/digest、ctx、temperature、seed、Prompt、rubric 权重均通过 config 固定。记录 `effective_tokens`；如果 token 总数差异太大，要在论文表中诚实记录并做资源归一化分析。

CLI：

```bash
uv run bite agents score --menu-id demo_day_01 --method m0 --profile balanced --mode synthetic --json
uv run bite agents score --menu-id demo_day_01 --method m3 --profile balanced --mode synthetic --json
uv run bite agents evaluate --methods m0,m1,m2,m3,m4 --split development --out outputs/runs/agent_dev/
uv run pytest tests/contract/test_agent_schema.py tests/integration/test_agent_protocols.py -q
```

**测试**：

- `q_N/q_F` 在 M0–M4 中完全相同（相同菜、相同画像）。
- LLM 修改 `sodium_mg` 被拒绝；声称存在的 evidence ID 不存在时报告无效。
- 所有合法输出 `total_0_100` 按同一固定公式计算。
- `M3` 最多一轮讨论；能比较 revision 前后评分；M4 至少记录实际 token 预算。
- `M3` 结果不会自动覆盖 `M2` 原始日志。
- schema 失败仍能输出明确 fallback，而非悄悄使用上一位用户的缓存结果。

### Phase 8 — 外部人工菜单评价与主实验

**目标**：真正回答 RQ2，不能只让 Agent 给自己评分。

独立人类问卷字段：

```text
user_id, menu_pair_id, menu_a_id, menu_b_id, stage,
choice, displayed_nutrition, order_randomization, timestamp, is_synthetic
```

`stage ∈ {taste_hidden_nutrition, overall_visible_nutrition}`；**主结果使用 overall_visible_nutrition**。同一参与者 12 个菜单比较的真实选择，应在模型参数/PROMPT 最终冻结后用于测试；如果让参与者参与开发阶段，也必须将其评测题/对应记录从最终测试中隔离。

实现：

1. 固定开发菜单和最终评测菜单/比较对 ID，`data/splits/menu_eval_test.json` 保存哈希。
2. 对每个菜单在 M0–M4 下生成完整分数和有效性标记；方法不能因失败跳过困难菜单而提升准确率，须报告 coverage 并在可比共同有效集之外另报失败率。
3. 使用在 development 集学好的校准温度 `κ>0` 将分数差映射成选择概率：`sigmoid(κ*(S_A-S_B))`；`κ` 对所有方法各自只能在开发集拟合，测试集保持冻结。
4. 报告 per-method pairwise NLL（主）、accuracy、Brier、coverage、成功响应比例、均值调用成本。
5. 按参与者为聚类单位做 2,000 次 Bootstrap，报告 M3-M0 与 M3-M4 等预注册对比的差值 CI。
6. 明确报告合法菜单比例、真实营养缺失比例、校准/数据质量来源。

CLI：

```bash
uv run bite eval lock-menu-test --config config/experiment_plan.yaml
uv run bite eval score-humans --methods m0,m1,m2,m3,m4 --test data/private/menu_choices.csv --out outputs/runs/main_eval/
uv run bite eval bootstrap --input outputs/runs/main_eval/per_pair.parquet --cluster user_id --reps 2000
```

若没有真实受试者数据：只能生成空白采集模板、synthetic smoke 报告并把主评估标记 `BLOCKED_BY_HUMAN_DATA`；**不得生成主论文图 4 的真实值**。

### Phase 9 — 长期仿真与策略比较

**目标**：7 天主、30 天附加；对所有策略公平，主评估与策略自评分隔离。

推荐 API：

```python
class FoodEnv:
    def reset(self, profile_id: str, seed: int): ...
    def candidates(self, day: int) -> list[DayPlan]: ...
    def step(self, selected_menu_id: str) -> dict: ...

class Policy:
    def select(self, state, candidates) -> str: ...
```

策略清单：`random_valid`, `greedy_taste`, `calorie_efficiency`, `single_agent`, `multi_agent`。为每个 `(profile,seed,day)` **预先生成并保存 8 个相同候选**；随机策略从所有合法候选均匀抽样；失败策略选择回退策略必须一致。若 60 套菜单不够覆盖不同画像，允许同源多份配比，但必须保持可行性与记录生成器版本。

不要让 Multi-Agent Planner 先给自己选的菜打出 99 分，再报告其“平均 BITE 99 分”当作胜利。输出至少：

- `reference_utility`：一个事先冻结的模拟参考函数，仅供诊断，并声明它也有设计偏好；不作为唯一策略优劣指标。
- `nutrition_constraint_rate`：客观约束（越高越好，前提不是极度单一）。
- `repeat_rate` / `category_diversity`：客观频率。
- `estimated_taste`：冻结 TasteNet 估计，并附带数据来源（非真人食后幸福）。
- `runtime_cost`：调用次数、tokens、耗时、峰值显存。
- `human_coverage`：有独立人类评价支持的菜单比例；未覆盖部分不得推断为已验证。

CLI：

```bash
uv run bite sim prepare --config config/experiment_plan.yaml --out data/menus/simulation_candidates.json
uv run bite sim run --days 7 --seeds 30 --profiles all --policies all --mode synthetic --out outputs/runs/sim7_demo/
# 仅在真实营养、TasteNet 和本地 LLM 均通过之后开展正式模式
uv run bite sim run --days 7 --seeds 30 --profiles all --policies all --mode full --out outputs/runs/sim7_full/
uv run bite sim run --days 30 --seeds 30 --profiles all --policies all --mode full --out outputs/runs/sim30_full/
```

**性能控制**：每个 menu/history/profile/model/rubric/prompt combination 在不改变历史依赖意义的情况下缓存一次评估；key 必须包含**历史 hash**，否则“连续七天吃炸鸡”每天会误读为完全相同分数。缓存不得使用模型的上一版本响应。对一次候选可估算理论调用量并记录为 `estimated_calls`（不是墙上时间的虚假预测）。

### Phase 10 — 消融、统计、配图和论文素材导出

**目标**：用统一 CLI 跑完方法对照和消融，输出真实结果、图表和可写进 LaTeX 的表格。

消融配置（建议 YAML matrix）：

```yaml
experiments:
  taste:
    - global_bt
    - feature_bt
    - personalized_full
    - no_user_embeddings
    - no_food_features
    - no_active_query
    - no_calibration
  agents:
    - m0
    - m1
    - m2
    - m3
    - m4
    - m3_no_taste_adjustment
    - m3_no_longterm_history
    - m3_no_discussion
    - m3_no_taste_model   # 以冻结 GlobalBT 代替 TasteNet，而不是将味觉分数归零
    - m3_no_n_explanation
    - m3_no_f_explanation
```

**关键**：`no_calibration` 只评估绝对评分需求的质量；`no_n_explanation` 和 `no_f_explanation` 不移除客观 Oracle。另设明确标注 `stress_test_no_nutrition_facts`（仅证明鲁棒性风险，不与健康可用的主方法公平对比）。

统计：

1. H1：不同 TasteNet 在同一真人 held-out pair 上的 NLL 差，按参与者聚类 Bootstrap CI。
2. H2：M3 与 M0、M4 的真人总体偏好 NLL 差，按参与者聚类 Bootstrap CI；共同有效集对照 + 单独报告 coverage。
3. 模拟：相同 `(profile,seed)` 配对统计各策略的营养/重复/多样性差；说明其外推限制。
4. 多个次指标不应作为“显著胜利”叙述；区间跨零时写“未观察到明确改善”。

绘图脚本必须读取实际结果文件，命令例如：

```bash
uv run bite report figures --run-root outputs/runs --out outputs/figures
uv run bite report tables --run-root outputs/runs --out outputs/tables
uv run bite report provenance --out outputs/reports/reproducibility.json
```

预期图：架构、TasteNet 学习曲线、用户偏好热力图、单/多 Agent 主结果、长期策略模拟线、Pareto Front（散点计算时明确采用哪两个轴及非支配定义）。预期表：数据统计、主指标 CI、消融与调用成本。图注自动标记 `HUMAN`, `DATABASE`, `RECIPE ESTIMATE`, `SIMULATION`, `SYNTHETIC DEMO` 来源标签。

**验收**：所有图来自数据文件；无真人数据时真人相关图不可误产；表的每个值能从对应 `metrics.json`/原始结果重算；若 H1/H2 正式数据不足，成果包明确标注“论文实验尚未完成”。

### Phase 11 — 最终报告、可复现性和交付

完成后应生成：

```text
outputs/reports/FINAL_STATUS.md
outputs/reports/data_quality.json
outputs/reports/model_cards.md
outputs/reports/experiment_summary.md
outputs/reports/reproducibility.json
outputs/reports/missing_prerequisites.md
outputs/tables/*.csv
outputs/figures/*.png
config/protocol.lock.yaml
artifacts/manifest.json
```

`FINAL_STATUS.md` 必须说明：已经实际完成什么、哪些是合成验证、哪些需要真人/人工审核、哪些模型真实加载 GPU、哪些性能结果尚不能声称、如何从零重跑。不要仅给出一句“环境配置完成”。

---

## G. 质量门禁：必须写成可运行测试

以下是最低测试清单（建议转成 `pytest`）：

### G.1 数据合同

- `FoodVariant` 不接受负值、非法 serving、无来源字段的“verified”数据。
- `missing != 0`；未知和数值零行为不同，`insufficient_data` 不给总分。
- 错误单位、重复 food_id、菜单引用不存在的食物、互斥字段缺失均报明确错误。
- 标签数据保留左右位置、策略组、split 和匿名 ID。

### G.2 偏好模型

- BT pair reversal invariance。
- logits/probability 有界、无 NaN、Loss 随训练下降（synthetic controlled case）。
- `cold_food` 不包含训练过的专属食物 id 效用；锚点校准不读取测试。
- `pair_id` 在 train/test 不重合；测试题不能进入 active candidate pool。
- 用户聚类 Bootstrap 不会将同一用户的数据打散成假独立样本。

### G.3 综合评分

- 不同 Agent 协议读取同一营养 Oracle 值。
- 禁食食物触发 hard invalid，即使 TasteNet 分数 100。
- 能量不足不会被“低热量就是好”误判为 Fitness 满分。
- 相同输入和缓存版本稳定返回同一已保存结果。
- 有效评分 `0<=S<=100`；每项权重一致；无隐藏 LLM 修订。
- 拒绝不合法 evidence ID、无效 role、N/F 非零 adjustment 和超界 delta。

### G.4 仿真、公平与追溯

- 同一 `(profile,seed,day)`，所有 policy 获得相同候选索引。
- `policy_score` 与 `reference_utility` 分字段输出；禁止用前者冒充外部胜利。
- 7 天历史重复度的时间更新正确，模型缓存包含历史 hash。
- 任意测试结果都有 `run_id`, `seed`, `dataset_hash`, `config_hash`, `model_digest`, `code_version`。
- mock 模式有“synthetic”强制水印，正式统计默认拒绝混入。

### G.5 统一本地验收

```bash
uv run ruff check src tests
uv run pytest -q
uv run bite env doctor --json
uv run bite data validate --input data/fixtures/synthetic/foods.csv --allow-synthetic
uv run bite agents score --menu-id demo_day_01 --method m0 --mode synthetic --profile balanced --json
uv run bite sim run --days 7 --seeds 2 --profiles balanced --policies random_valid,greedy_taste --mode synthetic --out outputs/runs/smoke/
```

`ruff`、`pytest`、基础 mock 路径不通过则不得进入正式主实验，除非该测试本身因暂缺真实条件而有明确隔离理由。测试框架依赖随项目内 `uv.lock` 固定，不接受“在我本机恰好可以运行”作为唯一证据。

---

## H. 实验运行协议与结果冻结

### H.1 固定随机性和版本

- 典型 `train_seed=17, split_seed=23, simulation_seeds=0..29`，只用于初始一致性；最终在 `protocol.lock.yaml` 中冻结。
- Python `random`/NumPy/torch（如用）全部设置相同实验配置下的 seed。LLM 服务端可能不能保证 bitwise reproducibility，因此保存原始响应、实际参数和模型 digest。
- `git rev-parse HEAD`, `uv.lock` SHA256, `config` SHA256, food manifest hash, split hash, Prompt version, `ollama show` 结果在每次 run 中写档。
- JSONL 元数据不得含泄漏的 FDC key、用户真实身份或不必要的健康信息。

### H.2 `run_id` 规则

推荐 `<UTC timestamp>_<experiment>_<short commit>_<seed>`，示例：`20261013T084000Z_tastenet_abc1234_s17`。如果 Git 尚无 commit，标识 `dirty_<hash>`，不许写不存在的 commit ID。完整 manifest 中永远记录 `synthetic/human` 数据类型。

### H.3 冻结边界

正式真人主实验前运行：

```bash
uv run bite protocol freeze --config config/experiment_plan.yaml --out config/protocol.lock.yaml
uv run bite split audit --locked
uv run bite data report --locked
```

`freeze` 应计算 hash 并标记只读意图（不依赖 OS 权限才能满足）；若用户同意修改协议，追加 `protocol_v2.lock.yaml` 与变更记录。测试结果不能在 `v1` 标签下悄悄复写。

### H.4 分析报告准确措辞

允许：

- “在合成夹具上，数学与接口测试通过，尚无真人性能结论。”
- “在 N 名参与者及 M 道冻结测试比较中，模型 A 的 NLL 为 x（95% CI …），模型 B 为 y。”
- “在指定模拟假设和 30 个种子下，多 Agent 策略的重复率较低。”

禁止：

- “BITE 证明长期吃某类食物更健康/更幸福。”
- “Multi-Agent 必然优于 Single-Agent。”
- “模型理解真实口感”，如果只根据图片/描述作预期偏好。
- “论文有真实实验数据”，当目录里只有 synthetic 或模板。

---

## I. 给执行 Agent 的首轮任务清单（复制即可启动）

在可写的工程环境中，请**按顺序**做下列事情，不要一次性下载所有模型或并行运行全部实验：

1. **阅读** `docs/RESEARCH_METHOD.md` 与 `docs/CODEX_PLAYBOOK.md`，生成一段不超过 300 字的理解摘要放入 `docs/RUN_STATUS.md`。
2. **侦测** 当前机器、Python、uv、GPU、WSL/Ollama，并保留原始输出与失败记录。不得修改驱动或用户网络配置。
3. **创建** `pyproject.toml`、目录布局、Pydantic 核心 schema、Typer `bite` CLI、合成 fixtures 和 `pytest`。
4. **实现** 营养每份/每日聚合及 rubric oracle；给缺失字段设置显式拒绝逻辑；先完成严格的数学单元测试。
5. **实现** 数据 curation 和 USDA API client；没有 API Key 或无法核查中餐营养时创建人工待办，不要猜营养数值。
6. **实现** `GlobalBT`、`FeatureBT`、`PersonalizedTasteNet` 的训练/预测一致接口、数据泄漏测试、冷食物验证及校准。
7. **实现** Streamlit 偏好采集页面和 split 预冻结，先用 synthetic 测试，正式真人问卷等待用户主持或授权。
8. **确认** Qwen3 4B Q4 本地能否在 RTX 5060 上响应合法 schema；报告实测显存、响应成功率和模型 digest。如失败，跳过真实 Agent 结果，保留 mock+规则路径。
9. **实现** M0–M4、证据检查、缓存、回退和统一聚合器，确保同一菜单不同协议的营养事实相同。
10. **实现** 人类菜单偏好评测、聚类 Bootstrap、7 天仿真策略公平性测试和图表程序。
11. **跑完** `pytest`, `ruff`, smoke simulation，生成 `outputs/reports/FINAL_STATUS.md` 与 `artifacts/manifest.json`，列出正式实验阻碍。
12. **停止于事实边界**：如果没有真实人类数据，只交付已验证的可执行系统和 Synthetic/Demo 输出；向用户说明正式实验需要的样本采集。除非用户另行要求，不自动构造虚构论文“结果章节”。

### I.1 每次向用户报告的格式

```text
阶段：Phase X — <名称>
状态：PASS / BLOCKED / FAILED / IN_PROGRESS
已完成：<实际新增模块和文件>
运行命令：<原样命令>
证据：<测试通过数/实测模型响应/manifest 路径>
未完成及原因：<缺少的 API Key / 人工审核 / 参与者 / GPU 兼容性>
下一步：<一个能执行的具体动作>
```

不要把“准备开始做某件事”写成“已完成”。一旦真实运行和演示结果不一致，以真实运行日志为准，更新文档而非掩盖异常。

---

## J. 依赖、接口与行为的最终验收矩阵

| 交付目标 | 必须存在 | 最小可验证证据 | 无法获取真实输入时的处理 |
|---|---|---|---|
| 可部署工程 | `uv.lock`, `cli.py`, README | `uv run bite --help`, pytest | 无需真人数据 |
| 食物数据库 | schema + curation + sources | 每个正式食物有来源与标准份量，quality report | 缺失则 `BLOCKED`, 不填假数 |
| 营养底座 | `calculator.py`, `oracle.py` | 单元测试、hand-calculated examples | 合成 fixture 可以验证逻辑 |
| TasteNet | Global/Feature/Personalized BT | 冻结测试 NLL 与模型卡 | 无真人只跑 synthetic sanity check |
| 采集小游戏 | UI + split + consent + exporter | 左右互换、重复写入、撤回单测 | 问卷仍等待真实参与者 |
| LLM 适配 | Ollama + JSON schema + audit | 实测有效响应率/速度/显存 | GPU 失败用 mock 并标识 |
| Multi-Agent | M0–M4 + Aggregator | 相同事实、单轮修订、无泄漏 | 可以跑 mock，不能声称对齐优势 |
| 外部主评估 | human menu pairs + κ calibration | cluster CI 与 NLL | 没人类测试则明确 `NOT_RUN` |
| 长期模拟 | shared candidates + 5 policies | 7 天 smoke、可重放 seeds | 可标注 `SIMULATION` 单独输出 |
| 论文图表 | `figures.py`, `tables.py` | 每图对应真实结果文件 | 无结果不给假“实证图” |

---

## K. 常见错误与恢复指南

### K.1 `torch.cuda.is_available() == False`

先确认 Windows `nvidia-smi`、WSL GPU 映射、Python 环境路径、PyTorch 是否为 CPU wheel。不要直接重装 NVIDIA Windows 显卡驱动；先记录现有配置，再用官方支持版本核对。**CPU TasteNet 可以继续**。

### K.2 Ollama 报内存不足或掉到 CPU

降低 `num_ctx`、缩短 Agent Prompt、降低 `num_predict`、限制并发为 1，检查是否存在两个 Ollama 实例或其他 GPU 进程。若仍失败，使用更小模型做集成测试，但正式不同模型之间的质量不能混在一组结果中。记录 `backend=CPU/GPU/mixed` 的实测情况。

### K.3 USDA 响应缺失或 429

核对 Key 是否存在、是否已过期、查询用的 `fdcId` 是否有效、每小时限流。缓存成功响应，按指数退避重试；**API 不可用时不以模型补全数据库数值**，转为人工来源列表待处理。API 文档：https://fdc.nal.usda.gov/api-guide/

### K.4 中餐配方没有统一热量

将具体烹饪方式和原料质量定义为 `recipe_variant`，按可核查配料加总并记录估算假设；如果不清楚就保持缺失。不要合并不同餐馆、不同油量的“同名菜”作为精确同一营养记录。

### K.5 所有方法总分一模一样

先检查 `delta_T`/`delta_L` 是否实际生效、是否所有 Agent 都 fallback、是否缓存 key 缺少方法/Prompt/history，接着核对 M1–M4 有效响应率。完全同分不意味着多 Agent 毫无价值，也可能是系统没正确运行。

### K.6 Multi-Agent 准确率接近 100%

首先排查标签泄漏、从 final test 选 Prompt/κ、参与者的菜单评价是否被 Agent 直接读取、menu_id 是否泄露测试标签、随机左右平衡是否正确。然后考虑测试集太简单或样本小，不要直接将高分写成普适能力。

### K.7 7 天模拟一直只选一餐

先检查候选生成器和营养可行性、TasteNet 是否退化、是否缺少历史输入、缓存 key 的历史字段、重复统计是否按菜品 ID 正确计算。只有在机制核实后才能讨论奖励设计导致的策略偏差。

### K.8 因远程 SSH 断线而中断

每个 stage 有幂等命令、自动缓存与结果 manifest；建议使用 `tmux`（如 WSL 环境已装）运行长时实验，或使用用户允许的任务调度工具，但**不得自动设置开机自启动**。被中断的 run 标记 `INTERRUPTED`，恢复时根据 run hash 和已完成任务清单继续，不重写既有结果。

---

## L. 源文档与参考链接（供 Codex 主动查新）

1. 上位研究设计（本仓库）：`docs/RESEARCH_METHOD.md`。
2. USDA FoodData Central API：https://fdc.nal.usda.gov/api-guide/ — Key、速率限制、数据许可、食品详情。
3. USDA 数据类型：https://fdc.nal.usda.gov/data-documentation/ — Foundation、FNDDS、Branded 差异。
4. Open Food Facts API/licensing：https://openfoodfacts.github.io/openfoodfacts-server/api/tutorials/license-be-on-the-legal-side/ — ODbL、图像授权。
5. WHO Healthy Diet：https://www.who.int/news-room/fact-sheets/detail/healthy-diet%E2%81%A3%E2%81%A0 — 充足、平衡、适度和多样性原则。**本研究系数非 WHO 标准**。
6. NVIDIA CUDA on WSL：https://docs.nvidia.com/cuda/archive/12.8.1/wsl-user-guide/index.html — WSL2 GPU 映射、安全安装原则。
7. PyTorch install：https://pytorch.org/get-started/locally/ — 当前 CUDA wheel 安装选择。
8. uv：https://docs.astral.sh/uv/ — Python 环境、依赖锁定与运行。
9. Ollama Structured Outputs：https://docs.ollama.com/capabilities/structured-outputs — JSON Schema 和 Pydantic 校验。
10. Qwen3 4B Instruct 2507 Q4_K_M：https://ollama.com/library/qwen3:4b-instruct-2507-q4_K_M — 模型尺寸、名称与许可。

**注意版本漂移**：本手册编写日期为 2026-10-13；在真正实施日重新核验 SDK/模型/驱动和服务端接口，记录实际版本。保持科学 protocol 不动的前提下，可以调整**兼容性层实现**，但必须记录差异。

---

## M. 完成定义（Definition of Done）

本项目只有在下面六件事都满足时，才可以将**工程实现**标为完成：

1. 软件可以在目标节点运行基本 `mock` 管线，且拥有清晰 `uv.lock` 与单测。
2. 食物数据校验和营养评分完全可追溯，缺失处理不含假数据。
3. TasteNet 提供基线与个性化接口，训练/测试数据封存有效。
4. Multi-Agent 的 M0–M4 和本地 LLM 可用/不可用两种路径都有测试。
5. 7 天仿真在同候选、同种子的公平协议下运行，有结果日志及图表脚本。
6. 交付完整状态文件，所有剩余的人类样本、人工审核、正式结论标记真实状态。

**“工程实现完成”与“论文实验完成”不等价。** 论文主实验必须另有真实偏好标注、冻结测试、独立人类菜单评价、统计 CI 以及未被篡改的结果归档；缺这些数据就只能写研究方法和演示，不得出带“实测验证”语气的结论。

> 任务成功的标准不是 Codex 自信地说“全搞定了”，而是任意第三方能阅读说明、运行命令、核查数据来源，并在相同条件下重现相同的事实与可解释的差异。
