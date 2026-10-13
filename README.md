# BITE-Bench

基于个性化美味学习与多智能体协作的饮食效用评估研究项目。

开始前依次阅读：

1. [研究方法](docs/RESEARCH_METHOD.md)
2. [实施手册](docs/CODEX_PLAYBOOK.md)
3. [自动化与人工介入补充协议](docs/AUTOMATION_ADDENDUM.md)

已开始 Phase 0：Python 3.12 + uv 锁定依赖、bite CLI、环境诊断和基础测试。正式实验尚未运行。
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
