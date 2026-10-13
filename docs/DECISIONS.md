# Decisions

## 2026-10-13 — 基础初始化

- 用户要求当前仅完成最基本任务，复杂构件后续实施。
- 使用当前目录作为项目根目录，采用手册 docs 布局，三份副本逐字节保留原文并记录 SHA256。
- 实际工程手册文件名为 BITE_Codex_实施与实现手册.md；映射至 docs/CODEX_PLAYBOOK.md，不改原文研究方法。
- 默认 hybrid_pilot，首次验证 synthetic_only；尚未创建或冻结实验协议。
- 仓库默认私有；未发布受试者数据或研究结果。
- 本机 gh 原先缺失，已通过 Homebrew 安装；尚未完成 CLI 登录。
- GitHub 私有仓库通过已登录浏览器创建；使用现有 SSH 认证推送，无需新增凭据或 CLI 登录。

## 2026-10-13 — Phase 0 启动

- 用户确认仓库已公开，并授权开始实验、连接 5060。
- 使用现有 SSH 别名和身份；恢复现有 Tailscale 会话后连接成功，未修改 SSH 配置或驱动。
- 目标主机 WSL2 Ubuntu 已存在；项目部署至 Linux 家目录 /home/adminhh/projects/bite-bench。
- WSL 系统 Python 3.14.4 不替换；uv 0.12.17 安装于用户目录，项目单独使用 Python 3.12.14。
- 先核验 GPU 映射，不据此声称 PyTorch CUDA 或 Qwen 已可运行。
- 根目录原始资料存在用户侧变化；本轮不覆盖、不提交这些修改。docs 规范副本仍为研究依据。
- 本地 editable 导入发生 ModuleNotFoundError：bitebench.pth 带 macOS hidden 标志，Python site 忽略它；清除本项目安装与缓存 .pth 的 hidden 标志后重新安装/运行恢复。曾试用的 no-editable TOML 字段不受支持，已移除；没有遗留无效设置。
- 本地最新 pytest：20 passed；环境诊断、数据校验与 lint 已重跑。Phase 1 尚缺完整验收，不能据此标 PASS。
- 最终采用普通安装重建解决本地 editable 隐藏标志问题；更新源文件后明确 --reinstall-package bitebench，避免旧安装影响测试。
- 远程大包慢速下载被主动中止；四个官方 PyPI Linux wheel 的哈希与 uv.lock 一致，并在主机复核。按文件路径安装会触发 uv sync 的来源差异；失败尝试保留后，改为包名 + --find-links 的离线安装，再完整锁定同步成功。
- 通过 stdin 传送 Bash 验收脚本避免 Windows/WSL 嵌套 shell PATH 转义问题。
- 目标环境最终：32 passed in 0.32s，ruff 通过，GPU 映射有效。Phase 0/1 PASS；正式人类指标和 Qwen 推理均 NOT_RUN。

## 2026-10-13 — Phase 2 来源与审核工程

- 无个人 USDA API key 时阻断新请求；允许重放有哈希的真实缓存。官方 DEMO_KEY 仅用于小规模真实来源冒烟验证，不视为人工审核。
- USDA GET 数据类型过滤实际失败；采用 POST JSON 检索后取得真实 FDC 170379。来源保留，缺失份量与蔬果质量保持未知。
- 48 个食品身份与 60 个菜单草稿不是正式数据；正式表保持空表，批准数为 0。禁止自动批准、伪造审核人或把合成测试夹具用于正式评估。
- 审核要求显式 human 身份、审核人、时间、证据、备注与食品哈希；记录变化使批准失效。审核页面只导出人工填写收据。
- 能量 ID 优先级是可审计的来源处理实现；多口径冲突需审核，不改变研究方法或冻结协议。
- 本地与远程各 57 项测试和 lint 通过；三项正式门禁均 BLOCKED。Phase 2 总体 BLOCKED，工程验证通过。
- 中间测试缺少 json 导入已修复并重跑。状态归档脚本首次遇到编码解析错误，代码提交成功后单独补录状态，未据此省略验收。

## 2026-10-13 — 独立本机采集系统（用户授权范围）

- 使用独立 Python 标准库 + SQLite + 本地浏览器，实现离线采集工程，不引入根项目依赖变化；新增 Bank 验证器负责问卷契约，正式食品适配仍需遵循核心 Pydantic 与审核门槛。
- 正式 FoodBench-48 未完成，因此仅使用 16 食品文字 synthetic fixture；所有会话和导出强制 synthetic / research_eligible=false，真人题库与 human 导出硬拒绝，没有正式采集开关。
- 问卷文件、同意版本、heldout 划分、每人展示顺序在任何回答前保存 hash 和完整快照；更换输入题库只影响新会话。40/10/8 与 5 known/5 cold 不变。采用固定 fixture 策略验证 UI，不声称已实现正式主动学习或完成 Phase 3 全部验收。
- SQLite 每题事务和唯一约束；幂等重试只接受相同 payload，拒绝覆盖原回答。暂停或断网不改答案；服务中断时保留页面内未确认 payload 并阻止换题，重启后刷新 CSRF 再重试。elapsed ms 包含休息/停机，不冒称纯反应时。
- 原始说明确认独立表，不出现在答案导出中；随机恢复码只存 hash，页面换人清空凭据。撤回级联删除当前数据库记录，但已下载备份/导出需操作者另外删除。CSV 空值为 null，tie/skip 不重新编码，训练文件与最终测试文件分开并写 allowlist。
- 采集员仅凭每次启动的临时访问码读取匿名进度和导出，不读取个人答案、不代填、不批准研究数据。HTTP 仅 127.0.0.1、Host/Origin/CSRF 校验，无远端资源、遥测或云同步。
- 构建携带 Python 官方 3.14.7 x64 embeddable runtime 的 Windows ZIP；固定官方 SHA256，包含 LICENSE，仅修改隔离 _pth 增加应用父目录。解压无需安装、改 PATH 或管理员权限；不打包运行数据。
- 原生 Windows 验收发现备份目标连接释放缺陷（WinError32），修复并保留失败记录；最终 macOS/WSL/原生 Windows 各 23 项通过，仓库 80 passed，浏览器完整 58 题验证通过。仅宣称工程正确性，无真人性能、GPU/资源峰值或研究结果。
- 保留会话开始时既有和并行完成的其他仓库改动；仅新增本模块、README 入口及维护三份进度文件，未提交或推送任何真人原始数据。
