# BITE Collect — Windows 本地离线版本

独立模块：不改研究方法，不依赖 FoodBench-48 完成，不依赖根项目安装或 GPU。
当前只能运行 **SYNTHETIC DEMO / synthetic_only**，正式真人采集硬关闭。演示交互或自动测试产生的回答均 `is_synthetic=true, research_eligible=false`，不是 observed human 数据。没有真实人类实验结果。

## 启动

使用带 Python 运行时的 Windows ZIP：解压到有写入权限的本地目录，双击 `start-windows.cmd`，保持终端打开。浏览器访问 **http://127.0.0.1:8765/**；控制台为 **http://127.0.0.1:8765/collector**。控制台访问码在启动终端显示，每次重启更换。整个运行过程不需要网络、pip、Node、管理员权限或系统安装。

从源码启动需要 Python 3.12 或更新版本（Windows `py -3` 或 `python`）：

```powershell
cd apps\bite-collect
python run.py validate
python run.py serve
python -m unittest discover -s tests -v
```

macOS / WSL / Linux 也可使用同一代码。仓库现有环境：

```sh
.venv/bin/python apps/bite-collect/run.py serve
.venv/bin/python -m unittest discover -s apps/bite-collect/tests -v
uv run --no-sync pytest -q
uv run --no-sync ruff check apps/bite-collect src tests
```

若端口占用，用 `--port 8767`；访问对应的 **127.0.0.1** 地址。服务仅监听 IPv4 loopback，拒绝其他 Host；不要使用 localhost 别名或主机局域网 IP。VPN 接管本地流量时，在 VPN 客户端绕过 loopback/局域网，或暂时暂停代理。无需修改服务器绑定地址。

## 体验流程

1. 阅读带版本的说明，确认 18+、自愿、了解合成演示；未确认不能建立会话。
2. 系统产生 UUIDv4 匿名 ID 和随机恢复/撤回码。**先下载或私下保存码**；数据库只存其 SHA256。码不是姓名或联系方式。
3. 50 次成对比较：40 train，10 test（5 known-food + 5 cold-food）。题库与每人左右顺序在任何回答之前冻结。选择 left/right/tie/skip；“是否吃过”和 0–10 饥饿程度可不回答。
4. 8 次不同训练锚点直接评分，0–10，可跳过，没有默认分数。纯美味任务不显示营养或内部 split。
5. 每题通过 SQLite 事务收到保存确认才前进。重复点击或重试同一 payload 幂等；不同回答不能覆盖已有记录。
6. 暂停后、浏览器刷新后或服务重启后，输入恢复码继续首个未答题。换人按钮暂停旧会话并清空页面内的码、回答和选择；完成旧会话不影响新会话。
7. 参与者可用同一码撤回删除本机回答、同意确认和题目分配；保留其他会话。采集员只能看进度、导出，不代填或更改回答。

如果本机服务中断，当前未确认的 payload 保留在页面内，界面不跳题；服务恢复后重试原回答（重启后的 CSRF token 自动更新）。**未获确认的回答没有持久化保证**，请保持页面打开；刷新后按数据库最后确认进度恢复。没有云端请求、服务工作线程、缓存远端数据或跨设备同步。

## 数据保存、导出、备份

默认 SQLite：`apps/bite-collect/runtime/synthetic/collect.sqlite3`。WAL + synchronous=FULL；每题事务，唯一 `(user_id, question_id)`，外键、完整性 hash 校验。原始说明确认在独立 `consents` 表，不出现在答案导出中。数据库和任何备份包含访问凭据的哈希与说明确认，必须私下保存；不提交 Git。

```powershell
python run.py status
python run.py export --out exports/synthetic/session-001.zip
python run.py backup --out backups/synthetic/session-001.sqlite3
```

导出和备份拒绝覆盖已有文件。`--db`、`--out` 必须有独立 `synthetic/` 路径分区；即使路径标记 synthetic，也会检查题库和数据库来源。`--purpose human` 会硬报错。

导出 ZIP 内含：

- `synthetic/train_pairs.csv` — 唯一允许的比较训练输入。
- `synthetic/train_ratings.csv` — 唯一允许的评分校准输入。
- `synthetic/test_pairs.csv` — 仅最终评价，不能调参、拟合、选 Prompt 或抽题。
- `synthetic/questionnaire_snapshots.json` — 题库版本、原始说明模板和 heldout 划分，不含个人同意接受记录。
- `synthetic/frozen_assignments.json` — 匿名会话预先冻结的题目及真实展示顺序。
- `synthetic/manifest.json` — 实际计数、来源标记、文件 SHA256、训练输入 allowlist。

CSV UTF-8 BOM；空单元格表示 null。tie/skip 原样保留；不自动改成左右标签。评分 skip 对应 null，0 是明确评分。`reaction_time_ms` 是服务器从**第一次展示到提交**的经过时间，包含暂停、刷新和停机，不能冒称纯作答耗时。时间为带时区的 UTC ISO 8601。

撤回会级联删除当前数据库的全部会话记录并截断 WAL；它不删除已下载导出、备份、文件系统快照或恢复码文件，操作者须另行删除这些副本。丢失恢复码不能仅凭公开 UUID 取得访问权限。本机系统账户可以读取 SQLite，此应用不提供磁盘加密或防御本机管理员的能力；Windows 数据目录访问权限由本机操作者管理。

## 题库接入与范围

参见 [QUESTIONNAIRE_CONTRACT.md](QUESTIONNAIRE_CONTRACT.md)。`--bank` 接受独立 JSON；不用修改 UI 就可开发新的 synthetic 文字问卷。旧会话使用数据库里的快照，新题库只影响新会话；已有冻结顺序或题库 hash 被篡改时，读取、写入和导出均报错。

本版本用 16 个明确合成的食物描述验证软件，并不是完成 FoodBench-48。营养未知保持 null。40 个训练对采用明确的 fixture 固定策略，保留前 20 个覆盖块和后 20 个查询策略字段；**没有实现或声称完成正式主动学习实验**。训练候选接口不包含 test、heldout 食物或测试答案。

正式 FoodBench 适配器、机构伦理/豁免确认、正式同意文本（用途、期限、公开范围）、食品审核、真实协议/划分冻结与真人入口需要后续单独完成。当前加载真实题库会拒绝；无正式采集开关。独立菜单双阶段评价属于后续 Phase 3/8 范围，本轮不实现、不改变其方法。

## 构建可携带 Windows ZIP

构建器只接受固定 SHA256 的 [Python 官方 3.14.7 Windows x64 embeddable ZIP](https://www.python.org/downloads/release/python-3147/)，不联网、不安装软件、不改 PATH。官方运行时包含其 LICENSE；唯一兼容性修改为 `python314._pth` 增加应用父目录，以便隔离运行时导入本模块。应用仍支持 Python 3.12+。

```sh
python apps/bite-collect/build_windows.py \
  --runtime-zip /path/to/python-3.14.7-embed-amd64.zip \
  --out outputs/packages/bite-collect-windows-x64.zip
```

只打包明确列出的源码、题库、文档和测试，不包含 SQLite、同意记录、答案、备份、导出或控制台密钥。解压后的原生 Windows 测试：

```powershell
.\runtime-python\python.exe run.py validate
.\runtime-python\python.exe -m unittest discover -s tests -v
```

构建产物属于工程演示，不是正式研究成果包。
