# BITE-Bench

基于个性化美味学习与多智能体协作的饮食效用评估研究项目。

开始前依次阅读：

1. [研究方法](docs/RESEARCH_METHOD.md)
2. [实施手册](docs/CODEX_PLAYBOOK.md)
3. [自动化与人工介入补充协议](docs/AUTOMATION_ADDENDUM.md)

Phase 0/1 已在 RTX 5060 主机的 WSL2 环境验收通过：Python 3.12 + uv 锁定依赖、bite CLI、环境诊断、合成数据契约及 32 项测试。正式实验尚未运行。
默认研究模式为 `hybrid_pilot`；首次工程验证使用 `synthetic_only`。

研究方法优先约束科学结论；实施手册规定 Phase 0–11、接口和验收；补充协议规定自动化、审核和人工任务。
原始资料保留在根目录，docs 中的副本保持原文，来源及 SHA256 见 artifacts/manifest.json。
原文中的历史文件名链接可能与实际文件名不同，请使用上方入口。

按 Phase 0–11 顺序推进。进度见 [RUN_STATUS](docs/RUN_STATUS.md)，决策见 [DECISIONS](docs/DECISIONS.md)。
不得将合成数据当作真人数据，不得绕过审核或测试冻结，不得虚构实验结果。

基础验收命令：

```bash
uv sync --locked
uv run bite --help
uv run bite env doctor --json
uv run pytest -q
uv run ruff check src tests
```

macOS 若 editable 安装的 `.pth` 被隐藏文件标志影响，可使用 `uv sync --locked --no-editable --reinstall-package bitebench` 后以 `uv run --no-sync` 验证。普通安装在源代码变更后需要重建；目标 WSL2 环境已通过上述原始验收命令。

Phase 2 已实现来源检索、单位映射、配方估算、候选清单、审核队列和正式数据门禁。真实检索已取得 1 条 USDA 未审核提案；正式食品/菜单仍为 0，Phase 2 正式门槛 BLOCKED。

```bash
uv run python scripts/build_candidate_manifests.py
uv run bite review prepare
uv run bite review queue --only-actionable
uv run bite review view
uv run bite data report --input data/curated/foodbench48.csv
uv run bite data validate --input data/curated/foodbench48.csv --strict
uv run bite menu validate --input data/menus/day_menus.csv --food-data data/curated/foodbench48.csv
```

正式门禁当前预期返回 exit 2（BLOCKED），因为尚无已审核食品。个人 USDA_FDC_API_KEY 设置在不提交的 .env 中；正常检索预算默认 96 次，DEMO 模式限制少量 smoke。离线可显式 --network-budget 0，复用已保存的真实来源快照。源数据与流程说明见 [数据字典](docs/DATA_DICTIONARY.md)，当前最小人工任务见 [审核待办](docs/HUMAN_ACTIONS.md)。

## 独立离线采集模块

[apps/bite-collect](apps/bite-collect/README.md) 提供本机 SQLite 自动保存的匿名问卷、50 次成对比较、8 次直接评分、恢复/撤回、采集员进度和分区导出。当前仅为明确标记的 synthetic 工程演示；正式真人采集关闭。Windows 可使用携带 Python 运行时的离线 ZIP，也可用 Python 3.12+ 直接运行。
