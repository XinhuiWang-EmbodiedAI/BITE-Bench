# BITE-Bench Run Status

更新：2026-10-14（Asia/Shanghai）。用户已授权开始实验并连接 5060；默认 hybrid_pilot，首先 synthetic_only。

研究约束：真实偏好与合成数据隔离；营养事实来自可追溯确定性输入；缺失值保持 null；审核与最终测试冻结不可绕过。正式 RQ1/RQ2 尚无结果。

| 阶段 | 状态 | 实际证据 / 剩余事项 |
|---|---|---|
| Phase 0 | PASS | 5060 WSL2：uv sync --locked、bite --help、env doctor、pytest、ruff 均成功 |
| Phase 1 | PASS | 五个合成食品、两个菜单、两个用户；合同、份量/日聚合、缺失阻断、权重/调整/BT 方向不变性验收通过；本地和远程各 32 项测试 |
| Phase 2 | BLOCKED | 工程验证通过：本地与 5060 各 57 项测试及 lint；来源提案 1 条，正式食品 0/48、批准 0，正式菜单 0/60 |
| Phase 3 | IN_PROGRESS | 浏览器采集及终端问卷、菜单双阶段、主动查询均有合成验收；正式食品和真人门槛仍未满足 |
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



## Phase 3 合成划分冻结与存储层 — 2026-10-13

实际执行位置已核实为本机 WSL /home/adminhh/projects/bite-bench；macOS 为历史环境。Phase 2 仍 BLOCKED，真人采集关闭。

- 五食品夹具：4 个训练对、2 个 known-food 测试对、2 个 cold-food 测试对、1 个冷食品、4 个训练锚点 ID。只用于部分工程验证，不满足正式 40/10/8 设计，不是正式 protocol.lock。
- 冻结文件包含食品快照 SHA256，拒绝不同内容覆盖；审计检查配对唯一性、冷食品训练泄漏和来源快照变化。主动候选访问只开放训练对。
- synthetic-only SQLite：匿名 UUID、哈希撤回 token、锁定展示顺序、事务和唯一性、幂等重复、冲突拒绝、保留 tie/skip、训练/测试分开导出、撤回关联删除。真人记录与非 synthetic 数据库路径被拒绝。
- 默认导出 train，test 必须显式选择。撤回删除数据库内用户及关联记录，不自动回收此前导出副本。真人生命周期仍待实施。
- 实测 66 passed in 0.46s，ruff 通过；split audit PASS；合成存储 smoke 写入 1、重复写入 0、导出 1、撤回后答案 0。
- 验收命令：uv run --no-sync pytest -q -p no:cacheprovider；uv run --no-sync ruff check src tests；uv run --no-sync bite split freeze；uv run --no-sync bite split audit。日志 outputs/reports/phase3_*，manifest 记录哈希。
- 调度失败记录：PowerShell stdin CRLF 导致 heredoc/cat 解析错误，非登录 shell 无 uv PATH，一次 base64 shell 引号失败。已用登录 shell 或 uv 绝对路径核验最终代码和实际日志，不将调度失败当作通过。
- 下一步补充锚点评分、菜单双阶段存储，再实现合成 UI 与恢复流程。整个 Phase 3 仍 IN_PROGRESS。未更改公式、M0–M4、正式冻结协议，未提交或推送 Git。


## Phase 3 合成问卷续接 — 2026-10-14（Asia/Shanghai）

- 新增独立合成三餐菜单 questionnaire_menus.json 和 questionnaire_v1.json。原五食品划分 phase3_v1.json 未修改，正式 protocol.lock.yaml 未生成或覆盖。仍是部分工程夹具（8 道 taste、4 个锚点、1 个菜单 pair）。
- 终端问卷 bite label app：合成说明确认后创建匿名记录，保存说明版本；token 暂停/恢复与撤回；随机组按稳定哈希排序提问，左右位置按用户/题目/seed 固定；显示标准份量，保留是否吃过和自愿饥饿字段。
- 锚点评分 0–10，拒绝非训练锚点、冷食品、NaN 和真人标记；不可静默覆盖。菜单必须三餐、来自冻结合成食品。全部隐藏营养题完成后才允许显示营养，双阶段沿用相同左右顺序；营养由现有确定性 calculator 计算并标为 SYNTHETIC。
- 数据库新增 anchors、menu_displays、menu_answers、queries、notices。唯一键防重复；BEGIN IMMEDIATE 序列化答案提交，测试验证并发重复仅写一次。候选池只存训练题 ID 与 hash；无拟合模型时 model_state_sha256=null。active 组调度明确拒绝，不能假称已完成主动学习。
- 实测最终 74 passed in 0.40s，ruff 通过。真实执行的终端 CLI smoke：taste 8、anchor 4、菜单回答 2 / 独立 pair 1，暂停恢复、营养隐藏、锚点/菜单 CSV 导出与撤回均通过。撤回后八张用户相关表均 0 行；先前合成导出副本保留，未冒称物理清除全部副本。
- 日志 outputs/reports/phase3_questionnaire_*，manifest 新增带 source/config/dataset/questionnaire hash 的工程 run。开始写三餐夹具时脚本缺少 json 导入，已修复并重跑，未伪造验收。
- Phase 2 BLOCKED；真人采集、正式食品审核、真实 H1/H2、完整 40/10/8 与每人 12 个菜单 pair 的研究验收仍未满足。整个 Phase 3 IN_PROGRESS。
- 下一步：实现有模型状态哈希的主动查询接入、固定覆盖题/自适应题划分和完整规模合成验收；正式调查继续等待数据审核、冻结与合规授权。终端 UI 为首版，不宣称已实现 Streamlit 浏览器版。


## Phase 3 主动查询与完整规模合成验收 — 2026-10-14

- 新增 synthetic_bt_query_v1：仅用于查询选择的正则 BT 模型（L2=1、L-BFGS-B、200 迭代上限），不是正式 TasteNet/B3、不是校准 0–100 美味模型。只读取当前合成会话的 train 记录；tie/skip 保留并排除二分类拟合；没有有效标签时使用显式零效用先验。
- active 策略用 p*(1-p) 不确定性选择，同分按 pair_id 破同分；random 用冻结 seed 和用户 ID 的稳定随机顺序。20 个固定覆盖题完成后，各组执行 20 个策略查询；均在40次训练后转入5 known+5 cold测试。预算按实际响应计，包含 tie/skip，不把未问候选算成观测。
- query 审计存候选 ID/hash、策略版本、顺序、选中概率、模型状态和状态 hash，状态包含训练数据 hash、使用记录数、有效二分类数和排除数。暂停恢复使用已经发出的题目，避免刷新换题；训练导出仍不包含 test。
- 新建独立 data/fixtures/synthetic/phase3_sized/：48 食品、60 三餐菜单，所有营养和来源均为显式合成夹具。phase3_sized_v1.json 固定8冷食品、8训练锚点、20覆盖题、20查询预算、10冻结测试题以及随机打乱的12/12组别计划。questionnaire_sized_v1.json 固定24 final菜单、36 development菜单及12最终比较对。旧v1冻结文件原始SHA256复核一致，未覆盖。
- 实测24个合成会话全部完成：12 active / 12 random，训练960、测试240、锚点192、菜单阶段记录576；每会话12独立菜单pair，合成会话-pair观测共288（全局唯一pair仍12）。真人参与者0；这些数据绝不用于声称 H1/H2、人群效应或营养审核。
- 最终81 passed in 1.22s，ruff通过；所有 active 模型状态不含 cold-food 参数、test题目或未来训练答案，候选池审计通过。CLI bite label smoke-sized 在新run目录执行并记录metrics/CSV/SQLite。重复输出拒绝覆盖；撤回后组别计划序号不重新使用。
- 日志 outputs/reports/phase3_active_sized_*；旧冻结复核 phase3_prior_freezes_audit.json；新run纳入manifest。评分公式、M0–M4、正式协议及真实数据均未修改。未下载LLM、未提交或推送Git。
- Phase 3 合成工程验收已通过；整体仍 IN_PROGRESS，因为正式数据门槛、真人采集授权及真实问卷验收尚未完成。Phase 2继续BLOCKED。
- 下一步可进入Phase 4合成TasteNet基线、特征模型、个性化、训练锚点校准和冻结测试指标工程；主动查询模型不替代正式模型验收。

## 2026-10-14 — 两端合并与同步验收

- 合并父提交 afac467（浏览器离线采集）和 732e623（5060 Phase 3 研究问卷）；合并代码提交 8e7b93c。四处共享 README/状态/决策/manifest 冲突保留双方追加内容和全部独立 run，不覆盖任何历史验收。
- 两套模块代码原样保留；浏览器仍使用自己的16食品固定题库，研究 CLI 使用独立48食品/60菜单夹具和主动抽题。此次只同步源码与文档，不自动把浏览器接到 CLI 后端，也不混用数据库或导出。
- 本地 macOS：104 passed（另5个 subtests）、ruff 通过；5060 WSL2：104 passed（另5个 subtests）、ruff、bite --help 与浏览器题库 validate 均通过。先同步代码，再在真实 WSL 项目目录执行验收。
- 原始两端提交已保留 codex/backup-local-20261014-afac467 与 codex/backup-wsl-20261014-732e623 分支；Git bundle 和实测日志位于 outputs/sync/20261014/，manifest 记录 SHA256。首次 /tmp bundle 取回失败，改用仓库 ignored 输出目录；完整 bundle 传输较慢，改用基于共同父提交的增量 bundle。
- 原三份研究规范、rubric、已有冻结数据和原回答保持原样；真实研究仍无数据，Phase 2 BLOCKED、Phase 3 IN_PROGRESS。真人采集继续关闭，Phase 4–11 未开展。
- 本机根目录已有研究资料改动与预览文件不加入同步提交；5060 的 D:\BITE-Bench 旧副本未覆盖。开发同步目标为 /home/adminhh/projects/bite-bench。
