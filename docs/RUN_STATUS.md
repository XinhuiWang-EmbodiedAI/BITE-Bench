# BITE-Bench Run Status

更新：2026-10-13（Asia/Shanghai）。用户已授权开始实验并连接 5060；默认 hybrid_pilot，首先 synthetic_only。

研究约束：真实偏好与合成数据隔离；营养事实来自可追溯确定性输入；缺失值保持 null；审核与最终测试冻结不可绕过。正式 RQ1/RQ2 尚无结果。

| 阶段 | 状态 | 实际证据 / 剩余事项 |
|---|---|---|
| Phase 0 | PASS | 5060 WSL2：uv sync --locked、bite --help、env doctor、pytest、ruff 均成功 |
| Phase 1 | PASS | 五个合成食品、两个菜单、两个用户；合同、份量/日聚合、缺失阻断、权重/调整/BT 方向不变性验收通过；本地和远程各 32 项测试 |
| Phase 2 | NOT_STARTED | 尚未实施 |
| Phase 3 | NOT_STARTED | 尚未实施 |
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

下一步：Phase 2 — USDA 客户端、候选食品清单、单位映射和审核队列；正式食品未经审核不能升级为 approved。

远程最终诊断：项目 Python 3.12.14；GPU 可见，显存使用快照 871 MiB / 8151 MiB；torch 未安装，Ollama localhost connection refused。该快照不代表模型峰值显存。

网络恢复记录：中止本任务的慢速下载；经本地下载并在两端校验 uv.lock SHA256 的四个 Linux wheel，以包名从本地目录安装，再完整 uv sync --locked 和验收。失败与替代路径均有日志。
