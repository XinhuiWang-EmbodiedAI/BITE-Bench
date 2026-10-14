# 合成问卷使用说明

当前仅是 synthetic_only 工程演示，真人采集未启动。营养夹具和所有回答记录均标为 SYNTHETIC，不用于真人效果或医学结论。项目实际位置为本机 WSL /home/adminhh/projects/bite-bench。

启动：

```bash
uv run --no-sync bite split freeze
uv run --no-sync bite split freeze-questionnaire
uv run --no-sync bite label app --mode synthetic_only
```

确认说明后输入 DEMO，再输入 new。自行保存恢复/撤回 token；数据库只保存其 hash。不要填写姓名、联系方式或身体数据。

流程：训练偏好 → 冻结测试偏好 → 训练锚点评分 → 所有菜单隐藏营养选择 → 所有菜单显示合成营养选择。食物题只评价预期好吃程度；锚点为 0–10 预期美味，非试吃结果。left/right/tie/skip 原样保存。是否吃过可选 unknown；饥饿程度自愿填写 0–10 或 unknown。

输入 exit 暂停，下一次选择 resume 并输入 token；选择 withdraw 可删除数据库里的用户及关联记录。此前导出副本不会自动删除；真人生命周期尚未启用。

导出（按实际数据库路径）：

```bash
uv run --no-sync bite label export --source outputs/runs/phase3/synthetic/questionnaire.sqlite --out outputs/runs/phase3/synthetic/train.csv
uv run --no-sync bite label export-survey --source outputs/runs/phase3/synthetic/questionnaire.sqlite --kind anchors --out outputs/runs/phase3/synthetic/anchors.csv
uv run --no-sync bite label export-survey --source outputs/runs/phase3/synthetic/questionnaire.sqlite --kind menus --out outputs/runs/phase3/synthetic/menus.csv
```

默认训练导出不读取测试答案，只有显式 --split test 才导出测试。测试文件不能交给调参/训练器。小规模演示默认随机组，也可 --group active；主动查询仅使用当前合成训练答案。

五食品夹具仅包含 8 道 taste、4 个锚点、1 个菜单 pair，不满足正式 40/10/8 和 12 菜单 pair 设计。完整 Phase 3 仍未验收通过，Phase 2 正式数据仍 BLOCKED。


## 完整规模合成验收

```bash
uv run --no-sync bite label smoke-sized --out outputs/runs/phase3_sized_new_run --sessions 24
```

命令创建独立48食品/60菜单夹具，冻结组别和40/10/8设计，再模拟24个合成会话并验收；输出目录必须全新。它不会启动真人采集，real_participants=0。候选池大于20，但每会话只选择20个策略题，未问候选不算训练答案。

也可使用完整规模夹具手动测试终端界面：

```bash
uv run --no-sync bite label app --mode synthetic_only --protocol data/splits/synthetic/phase3_sized_v1.json --questionnaire data/splits/synthetic/questionnaire_sized_v1.json --food-data data/fixtures/synthetic/phase3_sized/foods.csv --database outputs/runs/phase3_sized_demo/synthetic/questionnaire.sqlite
```

完整规模演示按冻结组别计划分配，先20覆盖题，再20主动或随机题，然后10测试、8锚点及12菜单pair双阶段回答。group保持planned。首次无有效标签时active使用零效用先验；不虚构模型质量。训练/测试均严格标为synthetic。
