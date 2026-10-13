# BITE-Bench Run Status

更新：2026-10-13（Asia/Shanghai）。用户已授权开始实验并连接 5060；默认 hybrid_pilot，首先 synthetic_only。

研究约束：真实偏好与合成数据隔离；营养事实来自可追溯确定性输入；缺失值保持 null；审核与最终测试冻结不可绕过。正式 RQ1/RQ2 尚无结果。

| 阶段 | 状态 | 实际证据 / 剩余事项 |
|---|---|---|
| Phase 0 | PASS | 5060 WSL2：uv sync --locked、bite --help、env doctor、pytest、ruff 均成功 |
| Phase 1 | PASS | 五个合成食品、两个菜单、两个用户；合同、份量/日聚合、缺失阻断、权重/调整/BT 方向不变性验收通过；本地和远程各 32 项测试 |
| Phase 2 | BLOCKED | 工程验证通过：本地与 5060 各 57 项测试及 lint；来源提案 1 条，正式食品 0/48、批准 0，正式菜单 0/60 |
| Phase 3 | IN_PROGRESS | 独立 apps/bite-collect taste 采集模块合成工程 PASS；菜单问卷、主动学习及真人正式门槛未完成 |
| Phase 4 | NOT_STARTED | 尚未实施 |
| Phase 5 | NOT_STARTED | 尚未实施 |
| Phase 6 | NOT_STARTED | 尚未实施 |
| Phase 7 | NOT_STARTED | 尚未实施 |
| Phase 8 | NOT_STARTED | 尚未实施 |
| Phase 9 | NOT_STARTED | 尚未实施 |
| Phase 10 | NOT_STARTED | 尚未实施 |
| Phase 11 | NOT_STARTED | 尚未实施 |

## 实际环境

- 本地：macOS arm64；项目 Python 3.12.14，uv 0.12.17。无本地 NVIDIA GPU，未安装 torch。
- 5060 主机：Windows 10 Pro build 19045；WSL2 Ubuntu，用户 adminhh。
- Linux 项目：/home/adminhh/projects/bite-bench，置于 WSL 家目录。
- GPU：NVIDIA GeForce RTX 5060，8151 MiB，驱动 591.86；一次探测使用 1065 MiB（快照，不是实验峰值）。
- WSL 可见内存约 15 GiB、swap 4 GiB、家目录文件系统可用约 955 GiB。
- 系统 Python 3.14.4 保留；已安装用户级 uv，并创建 Python 3.12.14 虚拟环境，锁定核心及开发依赖已同步完成。
- WSL localhost Ollama 尚未响应；Qwen 推理、PyTorch CUDA：NOT_RUN。

## 验证与失败记录

- 本地最新 pytest：32 passed in 6.15s；远程：32 passed in 0.32s；两端 lint 均通过。
- 已构建五个合成食品、两个合成菜单、两个合成用户；没有真实食品审核、参与者或菜单选择数据。
- 合成数据验证：5 rows，全部 synthetic；未训练 TasteNet，未运行仿真。
- 本地 macOS editable .pth hidden 标志造成导入失败，普通安装并明确重建后通过；详情见 outputs/reports/failures.md。
- 为避免读取旧安装，本地验证使用 uv sync --locked --no-editable --reinstall-package bitebench 后 uv run --no-sync。
- 根目录原始资料的外部修改保留，不覆盖、不纳入本轮提交；docs 三份规范副本继续作为依据。

原始日志位于 outputs/reports/（默认不上传）；manifest 记录哈希。
仓库现为公开（用户确认）；无密钥或真人原始数据进入本轮提交。

下一步：保持 Phase 2 正式数据验收阻断，补全来源与人工审核；后续 Phase 3 合成数据工程验证不能替代正式数据验收。

## Phase 2 实际执行结果

- 完成 USDA 检索、内容哈希缓存、请求预算和 429 处理；GET 过滤请求实际返回 400，改用官方 POST JSON 后成功，失败日志保留。
- 单位与营养 ID 映射、LOQ、冲突与缺失传播、食谱估算、人工审核收据和正式菜单门禁已实现；不自动补齐未知值。
- 48 个食品身份候选、60 个菜单身份草稿均不代表正式可用数据。实际取得 FDC 170379（Broccoli, raw）来源提案 1 条；份量和蔬果质量仍缺失，多能量口径待审核。
- 正式食品、批准记录和正式菜单表均只有表头：0/48、0、0/60。未收集参与者或真实偏好；正式 RQ1/RQ2、Qwen 和长期仿真均 NOT_RUN。
- 审核队列共 49 项（48 个食品与 1 个 API 配置项），当前可行动 2 项。离线审核页面仅导出人工填写的收据，不自动批准或写入正式数据。
- 最终本地 57 passed in 6.31s，5060 57 passed in 0.30s，两端 lint 通过。一次测试因缺少 json 导入出现 1 failed / 54 passed，修复后重跑通过，日志保留。
- 两端正式食品、菜单和审核收据严格门禁均返回预期 BLOCKED / exit 2；工程测试通过不能替代这些验收条件。
- 日志位于 outputs/reports/phase2_* 与 outputs/remote_evidence/phase2_*；来源缓存不进入公开仓库，manifest 记录实际文件哈希。

远程最终诊断：项目 Python 3.12.14；GPU 可见，显存使用快照 871 MiB / 8151 MiB；torch 未安装，Ollama localhost connection refused。该快照不代表模型峰值显存。

网络恢复记录：中止本任务的慢速下载；经本地下载并在两端校验 uv.lock SHA256 的四个 Linux wheel，以包名从本地目录安装，再完整 uv sync --locked 和验收。失败与替代路径均有日志。

## 2026-10-13 — 独立 Offline-first BITE Collect

- 范围：`apps/bite-collect/`，仅 `synthetic_only` 工程；总体默认模式仍为 `hybrid_pilot`。未修改三份研究规范、公式、M0–M4、既有划分或正式协议。
- 完成：版本化说明/18+/自愿确认、UUID 匿名会话和恢复撤回码、40 train + 10 frozen test 成对比较、8 train 锚点直接评分、SQLite 逐题事务、防重复/冲突、暂停/重启恢复、多人连续采集、受控采集员进度、分区导出、备份/撤回、独立 JSON 题库接口。
- Fixture：16 个明确 synthetic 文字食品，未知营养保持 null；不是 FoodBench-48。测试 5 known + 5 cold，冷食物不进入训练或评分。所有答案 research_eligible=false，真人题库和 human 导出硬拒绝。
- 实测：macOS Python 3.12.14、5060 WSL2 Python 3.12.14、Windows 10 原生 embedded Python 3.14.7，各 23 项模块测试通过；仓库 pytest 80 passed，ruff 通过。Windows 原生浏览器视觉验收 NOT_RUN；原生 HTTP/SQLite/导出/备份/撤回由自动测试验证。
- 浏览器：macOS 内置浏览器实际走完 58 题；验证说明阻断、0 分主动选择、暂停/刷新恢复、下一位复位、服务中断保留原 payload、重启后重试、防双计、控制台下载。独立测试库 2 个 synthetic 会话，导出实测 train pairs=41、test pairs=10、train ratings=8；不计入真人参与者。
- 首次 Windows 备份测试发现目标 SQLite 连接未显式关闭，导致 WinError32；修复关闭后重跑三端，失败日志保留。整包 SCP 过慢已中止；目标机在独立临时目录下载官方运行时并复核 SHA256，没有系统安装、PATH/驱动修改或公网监听。
- Windows 离线包：`outputs/packages/bite-collect-windows-x64-v0.1.0-final.zip`；带官方运行时/LICENSE，无数据库、答案、同意记录或密钥。启动后只监听 127.0.0.1。
- 运行命令：`.venv/bin/python apps/bite-collect/run.py serve`；测试 `.venv/bin/python -m unittest discover -s apps/bite-collect/tests -v`、`uv run --no-sync pytest -q`、`uv run --no-sync ruff check apps/bite-collect src tests`。Windows 包解压后 `start-windows.cmd` 或 `runtime-python/python.exe -m unittest discover -s tests -v`。
- 实际日志：`outputs/reports/bite-collect/`；源码、题库、运行时、离线包和日志 SHA256 记录在 artifacts/manifest.json。
- 本模块真实研究参与者=0；正式 HUMAN_STUDY=BLOCKED / FORMAL_COLLECTION_DISABLED_AND_FOODBENCH_NOT_APPROVED；RQ1/RQ2=NOT_RUN。未开展正式真人采集，未代真人作答。
- Phase 0/1 沿用既有验收；Phase 2 正式 FoodBench 仍 BLOCKED；Phase 3 仅独立 taste 采集模块工程 PASS，阶段总体 IN_PROGRESS。Phase 4–11 本轮未执行，不升级为 PASS。
- 下一步：经审核的 FoodBench 与正式同意/机构流程完成后再实现受控正式适配器；菜单问卷、正式 active/random 策略与评价隔离按既有方法后续实施。
