# BITE-Bench 执行约束

开始前依次完整阅读 docs/RESEARCH_METHOD.md、docs/CODEX_PLAYBOOK.md、docs/AUTOMATION_ADDENDUM.md。
研究方法约束科学有效性；实施手册约束公式、数据契约、CLI、目录及 Phase 0–11；补充协议仅扩展自动化、审核与运行模式。
真实性、隐私、防止测试泄漏、协议冻结优先。不得静默修改方法、评分公式、M0–M4 或冻结划分。

当前用户要求仅完成基础建仓；复杂实现、依赖环境和实验等待后续指示。
后续从 Phase 0 开始，未满足验收不得标记 PASS。默认 hybrid_pilot，首次仅 synthetic_only 验证。
合成与真人数据隔离；缺失营养保持 null；不得伪造真人选择、人工审核、性能或资源测量。
真实数据、密钥、原始同意记录及私有审计日志不提交 Git。
维护 docs/RUN_STATUS.md、docs/DECISIONS.md 和 artifacts/manifest.json。
当前执行位置为用户的 macOS 本地目录；文档中 Windows/WSL/RTX 5060 是目标环境，不代表已核验本机或远程主机。
