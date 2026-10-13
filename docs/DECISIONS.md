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
