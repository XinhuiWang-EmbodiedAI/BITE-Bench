# BITE-Bench：基于个性化美味学习与多智能体协作的饮食效用评估

> **Research & Experimental Specification · v1.0 · 2026-10-13**  
> 状态：研究方案 / 尚未开展正式数据采集和实验。  
> 配套工程文档：[BITE_Codex_实施与实验手册.md](./BITE_Codex_实施与实验手册.md)  
> 目标产物：可复现实验、小游戏原型，以及后续一篇以机器学习论文为形式的趣味研究文章。

## 0. 摘要（项目定义，而非实验结果）

**BITE-Bench（Balanced Intake–Taste Evaluation Benchmark）** 探索一个刻意生活化但具备技术内核的问题：在饮食目标、营养约束、有限能量预算和个人口味差异并存的条件下，一顿饭、一天或连续多天的饮食方案，应如何被评价？研究包含三个耦合模块：① 使用人类成对偏好建立个性化美味预测器 **TasteNet**；② 在确定性营养计算的基础上，由角色分工明确的 **Multi-Agent Committee** 形成可追溯的饮食总评分；③ 使用长期模拟检验不同饮食策略对即时愉悦、约束满足与食物多样性的权衡。

本研究明确区分**人类真实观测、营养数据库测量/估算、研究者设计的价值函数和合成模拟**，不以模拟分数声称医学健康效果，也不预设多 Agent 比简单公式更优秀。整体基调：研究程序严谨，研究话题与案例具有幽默性。

## 1. 研究问题、假设与边界

### 1.1 研究问题

- **RQ1（偏好学习）**：有限且带噪声的成对比较，能否学习个体对未评价食物的美味偏好？个性化、食物特征、主动学习分别有多大贡献？
- **RQ2（综合评价）**：控制信息和推理预算后，多角色协作是否比单 Agent、单步 LLM、以及预注册的确定性加权评分更符合人类整体饮食选择，同时遵守既定营养约束？
- **RQ3（长时程）**：当同一个人以相同候选食物和目标饮食连续选择多天时，重复、饮食历史与目标设定如何改变评分、选择和效用轨迹？
- **RQ4（人类价值差距，探索性）**：只看“好吃”和看见营养信息后的“愿意长期吃”，这两种偏好排序存在多大的偏移？

### 1.2 可证伪假设（必须允许结果不成立）

- **H1**：在已知用户的留出比较集上，个性化 TasteNet 相比总体平均偏好/非个性化模型降低 pairwise NLL；在未见过的食物上效果待定。
- **H2**：Multi-Agent 讨论相对独立评分，在独立的人类总体偏好判断上提高一致性；等预算单 Agent 是必要对照。若不成立，应解释角色偏差、冗余推理和评分漂移。
- **H3**：显式输入饮食历史并启用多样性/重复项后，模拟饮食选择的重复度降低；是否提高真实的长期满意度**不能仅凭模拟证明**。
- **H4（探索性）**：显示营养信息会改变一部分参与者对日菜单的最终选择，改变程度存在个体差异。

主要假设：**H1 的 NLL 改善、H2 的独立人类偏好对齐改善**。H3/H4 为探索性，避免多重比较后挑选显著结果。

### 1.3 不做什么

1. 不把 BITE Score 称作已验证的健康量表或营养医学建议。
2. 不声称真实食后饱腹、疾病风险、体重变化与长周期幸福感已被模拟准确预测。
3. 不让 LLM 根据照片猜营养数值后直接当成真值。
4. 不训练视觉语言大模型的全参数版本；RTX 5060 8GB 主要承担量化 LLM 推理，TasteNet 优先采用轻量模型。
5. 不用自动生成的偏好标签冒充真人意见；**synthetic/demo** 和 **human/observed** 必须在数据层隔离。
6. 在用户提供真实数据前，正式性能数字应标记为 `NOT RUN`，不得制作伪造论文结果。

## 2. 概念与任务定义

### 2.1 四个层次

| 对象 | 规范定义 | 允许的输出 | 特别注意 |
|---|---|---|---|
| 食物变体 `food_variant` | 食物名称 + 配方/品牌/烹饪方式 + 标准份量 | 预期美味、营养向量及来源 | “红烧肉”并非单一恒定热量食品 |
| 一餐 `meal` | 在某个时段摄入的若干食物变体及份量 | 味觉聚合、营养贡献 | 不应以低热量代替吃饱 |
| 一日 `day_plan` | 若干餐构成的一天饮食 | 0–100 BITE 分项和总分 | 营养充足/适度以日尺度计算为主 |
| 序列 `trajectory` | 同一用户连续 7 或 30 天 | 每日评分、约束、累计效用 | 全部长期结果均为模拟，除非另收纵向真人数据 |

这里把 **一日评分定义为主要总分**。对单餐可以显示“局部预览评分”，但由于日营养目标尚未观察完整，不能把一个菜的“健康得分”当作全日评价。

### 2.2 用户与情境

设用户为 `u`，食物为 `f`，份量为 `p`，日菜单为 `D_t`，连续天数为 `t=1..T`。情境 `c` 包括 `goal`（均衡/享乐/健身/长期主义）、当天预设能量和蛋白质目标、膳食习惯、已知禁忌与近期历史。严禁将受试者的生理敏感信息视为必要字段；实验采用虚构或自愿选择的标准化画像，不要求真实体重、疾病或身材数据。

## 3. FoodBench-48 数据集

### 3.1 目标规模（计划值，不是完成值）

- 48 个规范化的食物变体，覆盖 8 个**互斥的研究标签** × 每类 6 个：主食、肉/蛋、蔬菜/豆制品、水果、甜品、饮料、快餐组合、其他餐品。现实食物可跨类别，但数据库只为抽样设置一个 `primary_category`。
- 24 位成年自愿参与者；每人 50 次成对比较（40 次训练采集、10 次冻结测试），预计 1,200 次对比。每人另有 8 个锚点直接评分以校准效用尺度。规模较小，统计推断应克制。
- 60 份经规范化的候选**日菜单**，包括营养均衡、热量偏离、明显重复和不同偏好匹配等案例；从中按固定方案形成测试比较对。
- 多 Agent 综合评价的独立真人评测，目标为每人 12 次日菜单两选一，总计最多 288 个选择，兼顾可控问卷时长和覆盖率。

48、24、60 均为**目标样本量**；不能为达到配额编造营养、图片或人类标注。

### 3.2 食物数据的最小字段

- 标识：`food_id`, `name_zh`, `name_en`, `primary_category`, `recipe_variant`, `brand_or_source`。
- 标准份量：`serving_g`（克）、`serving_description`（文字）、是否为可食部分；所有每份指标必须与这个份量匹配。
- 营养每 100 g：`energy_kcal`, `protein_g`, `fat_g`, `carbs_g`, `fiber_g`, `sodium_mg`；有条件时增加 `saturated_fat_g`, `added_sugar_g`。
- 追溯：`source_system`, `source_record_id`, `source_url`, `retrieved_at`, `data_quality`, `method`（数据库原值/官方标签/按配方计算/研究者估算）、`uncertainty_note`。
- 图像：`image_path`, `image_license`, `image_attribution`, `image_is_illustrative`。不能将网上随意下载的图片视为可公开再分发。
- 过敏原、食物限制和 `availability` 是可选属性；未知即 `null`，绝不自动判定无风险。

**缺失与异常**：数值为 `null` 表示未知，**绝不以 0 填充**；能量必须 >0 才可作主食物记录，明确 0 kcal 饮品可单独标注；单位必须明确（尤其 `sodium_mg` 与 `salt_g`）；违反热量/份量合理性规则的记录必须人工审查。对主实验日菜单，关键字段（energy、protein、fiber、sodium、份量）不齐时阻断正式总分，或明确降低覆盖范围，不允许模型自动补数。

### 3.3 营养数据来源及合规

优先 [USDA FoodData Central](https://fdc.nal.usda.gov/api-guide/)（REST API、API Key、数据 CC0），中餐采用可核查的配方分解与匹配表，并存储来源版本。其次可选 [Open Food Facts](https://openfoodfacts.github.io/openfoodfacts-server/api/tutorials/license-be-on-the-legal-side/)（ODbL 数据库许可、图片 CC BY-SA 等不同许可，需要保留归属与许可说明）。其众包数据不保证完整与准确。优先使用自制配图或取得再分发许可的图片。

食谱推算：将原料按质量加权，明确生熟转换、烹饪油吸收和份量假设；所有此类数值标记 `recipe_estimate`，不得等同实验室测定。建议主分析同时报告 A（原始数据库/标签可信数据）与 B（包括估算菜品）两个子集的结果稳定性。

### 3.4 三个不同的数据层

1. **Food data**：食物与营养，允许对模型可见；经过审核且版本冻结。
2. **Preference data**：成对美味选择、少量绝对评分；划分训练/测试；测试答案永远不可进入模型和 Prompt。
3. **Evaluation data**：全日菜单的独立真人两选一与营养准则；不得被用于调整最终测试模型的权重。

所有发布的 demo 数据必须在 `synthetic/` 下，并带 `is_synthetic=true`。真实数据以匿名随机 ID 保存，原始同意记录单独处理，不上传公开仓库。

## 4. Experiment I：TasteNet 个性化美味预测

### 4.1 标注协议

给参与者展示两项**标准份量**食物的文字和有许可的图片，提问：**“只考虑你预期的好吃程度，不考虑热量、价格和健康，你更想吃哪一种？”** 提供“选左”“选右”“差不多/无法判断”。`tie` 需要单独处理或按预注册规则排除于二分类训练；不得随机改写为左右选择。记录 `has_tried_left/right`、饥饿水平（自愿）、反应时间和顺序。展示左右位置随机化，锚点与测试问题固定设计。

- **10 道冻结测试题**：每个参与者 5 道来自训练可见食物、5 道涉及训练未见食物（cold-food）；在收集训练答案前创建并封存。测试题不能出现在主动学习候选池里。
- **40 道训练题**：建议 20 道覆盖性的固定锚点 + 20 道策略生成的查询。若对比主动学习和随机抽题，用随机分组（12 人/组），测试集相同分布；该规模结论仅视为探索性，后续可扩大样本。
- **直接评分**：每人对 8 个训练锚点给出 0–10 预期美味，作为潜在效用与分数尺度校准的数据；冷启动测试食物不允许作为这些校准锚点。
- **图片偏差**：标注“看图预期口味”，不标注“真实入口感官体验”；后续有条件再做实际品尝小样本子实验。

全局先确定 `heldout_food_ids`（例如 8 个）以测试真正的新食物泛化；剩余食物进行训练。否则仅留出**比较对**无法验证未见食物的泛化。

### 4.2 基线与模型

- **B0 群体偏好常量/先验**：不利用个体信息，预测同分或群体平均。
- **B1 Global Bradley–Terry**：学习每个训练食物的群体效用；冷食物回退至群体先验。
- **B2 Feature Bradley–Terry**：利用食物特征向量 `z_f` 对新食物泛化。
- **B3 Personalized TasteNet**：利用用户低维嵌入和食物特征建模差异；训练数据规模不够时使用强正则化，必要时仅设用户类别偏好，不强行训练神经网络。

推荐方程：

$$P(f_i\succ f_j\mid u)=\sigma(s_{u,i}-s_{u,j}),\qquad
s_{u,i}=\mu_i+\boldsymbol\beta^\top \mathbf z_i+\mathbf p_u^\top W\mathbf z_i.$$



对未见食物 `mu_i` 不可从训练标签学习，预测时以零中心先验代入，仅使用特征项；对未见用户，`p_u=0` 或通过少量偏好适配。训练最小化成对二元交叉熵（tie 单独建模或排除）加 L2 正则；采用多随机种子/Bootstrap 检验稳定性。

### 4.3 美味分数校准与不确定性

BT 的潜在效用仅由**差值**确定，存在平移不辨识性；它原本不是 0–10 的“绝对美味”。为在 BITE 中使用数值分数，先锁定一组训练锚点，基于直接评分学习单调映射 `g(s)`，定义 `TasteScore = clip(10*g(s),0,100)`。该映射只能使用训练数据拟合，绝不使用最终测试评分。可比较线性/保序校准，样本少时优先简单模型。

预测不确定性建议分两层：成对选择的概率置信度（用 NLL/Brier/校准曲线检验）和分数的不确定性区间（例如用户聚类 Bootstrap 及多随机种子）。对新用户、新食物、来源模糊的菜品，应显式标注不确定性高。不要将 LLM 自报“置信度”视为可靠概率。

### 4.4 评估与报告

**主要指标**：测试成对 NLL（越低越好）；**辅助**：准确率、Brier Score、Spearman（仅在有足够完整排序数据时计算）、锚点直接评分 MAE。报告 `known-food` 与 `cold-food` 分开指标，同时给整体指标。测试者、比较对、食物 ID 的 split 信息随结果归档。

主动学习比较：在相同固定测试题和查询预算 `10/20/30/40` 下比较策略；真实分组人数少，须报告标准误/置信区间并写明功效不足，不能用同一主动学习日志无偏地推算从未提出的随机提问结果。

## 5. Experiment II：Multi-Agent 饮食总评分

### 5.1 明确“客观营养计算”与“AI 判断”之间的权限

**Nutrition Engine 是唯一的营养数值源**：每份营养 = 每 100 g 数据 × 食用克数 / 100；日总量 = 当日各食物之和。计算完成后可设置缺失值警报、份量上限、能量/蛋白质目标适配检查。LLM 不得自行重新生成 kcal、protein、fiber、sodium 数值。

四个角色共享一个量化 LLM（按轮次调用同一权重，并非四个独立训练的专家），各自只对任务授权范围作判断：

| Agent | 核心输入 | 输出/权限 | 禁止 |
|---|---|---|---|
| Taste（T） | TasteNet 分数与区间、食物组合、用户偏好 | `taste_adjustment`（组合/情境效应，建议 [-10,10]）、理由 | 修改 TasteNet 权重、捏造试吃体验 |
| Nutrition（N） | 确定性宏量与营养缺口 | 解释哪些目标符合/不符合、证据 ID、数据质量疑点 | 修改营养数值、凭空打出医学风险值 |
| Fitness（F） | 目标、总能量、蛋白质、各餐分布 | 目标适配解释、是否违反既定硬约束 | 把增肌/减脂目标等同于普适医学建议 |
| Long-term（L） | 连续日食物 ID、重复统计、目标、候选变化 | `sustainability_adjustment`（有限范围）、对单调重复的解释 | 宣称预测真人未来幸福程度 |

N/F 的**数值维度由可重现规则产生**；N/F Agent 负责证据检查、解释和异议，不允许在聊天中偷偷改分。T/L 允许在预注册的有限范围内提出主观调整，应用权由聚合器控制。这种设计依然是多 Agent 评价委员会，但把事实错误和主观判断分开。

### 5.2 确定性评分底座（先定义好，再允许 Agent 参与）

对用户 `u` 的日菜单 `D`，各分数归一化到 `[0,100]`：

1. **Taste baseline**：用 TasteNet 对每道完整菜品预测，再按**每餐各独立菜品等权、一天各餐等权**平均得到 `q_T^base`；这种约定适用于结构相似的日菜单。若菜品数量悬殊，开展加权方式敏感性分析。每个独立菜品应是完整可选单元，不能拆成几十个调料刷分。
2. **Nutrition oracle `q_N`**：根据预注册、按目标画像设定的纤维充足、食物组多样性、钠等缺口/过量规则计算；每个营养子项需有范围定义、数据来源、上限和缺失处理。初版可使用配置文件中的加权惩罚函数（不是通用临床健康量表）。
3. **Fitness oracle `q_F`**：根据目标热量偏离、目标蛋白质达成以及预设能量上下界给出分数。单纯极端低热量不能获得满分；欠摄入与超摄入均应有代价。
4. **Long-term baseline `q_L^base`**：来自可复现的近期相同菜品出现频率、类别覆盖率与连续重复规则；其具体折损曲线为**研究者假设**，不得描述为人群规律。

一个可实现的统一模式是：

$$q_T=\operatorname{clip}(q_T^{base}+\delta_T,0,100),\quad
q_N=h_N(D;\theta_N),\quad
q_F=h_F(D,G_u;\theta_F),\quad
q_L=\operatorname{clip}(q_L^{base}+\delta_L,0,100).$$

其中 `delta_T`、`delta_L` 由各自 Agent 建议，受有界范围、Schema 和证据约束；无证据、LLM 不可用或 JSON 无效则调整设为 0 并记录 `fallback_reason`，绝不可无声地把失败当真实 0 分。`h_N`,`h_F` 和重复规则应发布配置版本与单元测试。

总评分：

$$\boxed{
S_u(D)=\operatorname{clip}_{[0,100]}
\Big(\sum_{k\in\{T,N,F,L\}}w_{u,k}q_k(D)-\lambda V(D)\Big),\quad
\sum_k w_{u,k}=1,\;w_{u,k}\ge 0.
}$$

`V(D)` 为**独立于 Agent 主观评分**的违规惩罚，含明确命名的软约束违规；硬约束（如明确定义的用户排除食物、关键营养字段缺失）应判为 `ineligible`，而不是给出似是而非的 58 分。惩罚参数在验证集选择、测试前冻结。严格区分**分项评分**、**违规状态**、**最终 BITE 总分**。

建议初始权重（均属实验参数，不是健康科学结论）：

| Profile | Taste | Nutrition | Fitness | Long-term |
|---|---:|---:|---:|---:|
| Balanced | 0.35 | 0.30 | 0.20 | 0.15 |
| Hedonist | 0.60 | 0.15 | 0.10 | 0.15 |
| Fitness | 0.20 | 0.25 | 0.40 | 0.15 |
| Long-termist | 0.25 | 0.30 | 0.15 | 0.30 |

评估权重敏感性时使用预注册的 simplex 网格或 Dirichlet 采样，展示排名稳定性；不要只挑能产生有趣冠军的那一组权重。

### 5.3 三种主体方法与公平预算对照

- **M0 Deterministic**：完全固定规则，不调用 LLM；T/L 的调整为零。这是所有方法必须打败的廉价基线。
- **M1 Single-Agent**：同一模型阅读完整输入，对 T/L 调整提出建议，N/F 数值仍由 Oracle 决定；一次调用。
- **M2 Independent Multi-Agent**：四个角色独立生成结构化报告，互不读取其他 Agent 输出；固定聚合。
- **M3 Deliberative Multi-Agent**：先独立，再交换**不含私人原始数据**的结构化摘要，至多一轮异议/修订；仅纠正可定位的错误或信息遗漏。
- **M4 Budget-Matched Single-Agent**：给单 Agent 与 M3 尽量接近的总生成 token/轮次，控制“多花推理预算”混淆。

四 Agent 的输出必须能形成审计轨迹：`role`, `score_or_adjustment`, `evidence_ids`, `rationale`, `disagreement`, `confidence_note`, `prompt_version`, `model_digest`。如果检测到所引证的 `evidence_ids` 不存在，标记无效并回退。汇总器不再调用 LLM 做秘密打分。

**讨论轮的操作定义**：只允许修订 `delta_T`, `delta_L` 或对数据完整性提出异议；不能动 `q_N/q_F`、营养输入、真值、用户目标。保存讨论前后变化，并测量分数漂移、无效引用率和同题重复调用的一致性。

### 5.4 独立的外部评估（避免循环论证）

**独立人类主观效标**：在 60 个日菜单形成的预注册比较对上，邀请同样或独立的一组参与者评选更愿意采用的菜单；评分前有“不显示营养信息”和“显示营养信息”两个任务，顺序固定或平衡随机化。主指标为系统总评分差 `S(A)-S(B)` 对**显示营养后总体选择**的 pairwise NLL 和准确率。若希望多 Agent 评分预测概率，须仅在验证集上拟合 `P(A≻B)=sigmoid(κ(S_A−S_B))` 的 `κ`；测试集不能拟合 κ。

**独立客观效标**： Nutrition Oracle 单独核查候选菜单的能量、蛋白质与被设为硬约束的项目；报告违规率、缺失处理合规率、营养计算单元测试通过率、信息幻觉率。食品营养判断不等于真实未来健康收益。

**重复稳定性**：对相同输入使用多个种子/若干重复调用报告方差与 rank reversal；温度 0 不等于绝对确定性。统计置信区间按**参与者为聚类单位**重采样，防止 288 次判断被误当作 288 个独立人群样本。

### 5.5 RQ4：Taste–Health Preference Gap

同一参与者在营养可见前后对相同菜单对进行选择，以“切换比例”“McNemar 配对检验（样本足够时）”“排序偏移”作为探索性结果。不存在完整排序时不要强行使用排序距离。若收集的是 pairwise 数据，直接计算 `switch_rate` 更透明。主动告知参与者营养数值均为规范化标准份量、部分配方为估算。

## 6. Experiment III：7/30 天长期饮食模拟

### 6.1 状态、动作与转移

状态 `x_t = (profile, daily_targets, rolling_history, available_foods, rng_state)`；动作选择一份合法日菜单 `D_t`，或由固定模板库组合三餐。**第一版优先从 60 份已审查的日菜单中选择**，减少任意组合产生不可食用配方或不满足能量需求的风险。转移仅更新历史、营养累计、重复统计和下一轮候选。它是决策仿真环境，不是人体代谢模型。

### 6.2 对照策略

- Random Valid：从满足硬约束的菜单均匀随机选取。
- Greedy Taste：仅最大化 TasteNet 预测的日美味基线。
- Calorie Efficiency：最大化预先定义并带分母稳定项的美味/热量启发式；作为刻意朴素的反例。
- Single-Agent Planner：以 M1 输出作排序依据选择菜单。
- Multi-Agent Planner：以 M3 输出作排序依据选择菜单。
- Optional Oracle Planner：使用隐藏评估器作**上界参考**，必须明确 oracle 不可在真实场景获得。

每种策略使用**相同用户画像、候选集、约束、历史初始状态及随机种子**；同种方法不能因为遇到无效菜单就获得不同试验轮数。为避免计算爆炸，候选规模固定（如每一日 8 个），预先生成并存档候选索引。

### 6.3 结果评价：不能用规划者自己的奖赏裁判自己

- `external_preference_alignment`：对于有人类评分覆盖的菜单/比较对，记录外部模型或直接人的偏好对齐；超出覆盖范围的天数显示 `not_observed`。
- `nutritional_constraint_rate`：由冻结的营养引擎计算。
- `daily_diversity` / `repeat_rate`：客观计数，不由 Agent 自行声称。
- `reference_utility`：事先冻结的统一**评估者**函数（可能包含 TasteNet 的冻结估计），对所有策略一致，必须公开其人为假设；作为模拟相对指标而不是现实幸福度。
- `policy_score`：各策略自己的内部打分，仅供诊断，不用作策略优劣的唯一证据。
- `decision_cost`：平均 tokens、调用次数、缓存命中率、延迟、GPU 内存占用。

长期效用示意：

\[
J(\pi)=\sum_{t=1}^T\gamma^{t-1} [U_{ref}(D_t)-\lambda V_t]-\rho R(D_{1:T}).
\]

`γ, λ, ρ` 及厌倦函数属于预注册模拟参数，进行多档敏感性分析（例如 `γ∈{0.95,0.99,1.0}`；重复惩罚关闭/弱/强）。同时报告不折现的日均效用，防止时间尺度造成误读。

建议：**7 天为主、30 天为扩展、每条件 30 个随机种子**；如本地 LLM 调用成本超预算，先用离线评分缓存与 7 天实验验证，再扩大，不允许因为算力成本改变模型间公平性。

### 6.4 幽默但有可检验含义的反例

- **Infinite Broccoli Paradox**：过度奖励低热量/纤维，是否产生只推荐单种蔬菜的非法/不合理方案？
- **Seven-Day Fried Chicken Challenge**：贪婪美味策略是否反复选择炸鸡？启用历史后重复率是否下降？
- **Calorie Price of Happiness**：单位热量愉悦最大化能否在日能量与营养约束下保持良好表现？

这些是模拟压力测试的名称，**不允许预写“必然失败/必然成功”**。

## 7. 消融、稳健性与负对照

### 7.1 TasteNet 消融

`GlobalBT`, `FeatureBT`, `Personalized Full`, `w/o User`, `w/o Food Features`, `w/o Active Query`, `w/o Calibration`。其中 `w/o Calibration` 只应比较需要绝对评分的 MAE/总评分，原始 BT 的 pairwise NLL 不应被校准映射错误地改变。

### 7.2 Multi-Agent 消融

`M0`, `M1`, `M2`, `M3`, `M4`, `M3 w/o TasteNet`, `M3 w/o T-adjustment`, `M3 w/o L-history`, `M3 w/o Discussion`, `M3 w/o N-explanation`, `M3 w/o F-explanation`。删除角色时**保持客观 N/F 约束底座不变**，否则消融混入了删除事实的影响；另外单独设“去除营养事实”作为故意失真的 stress test，**不可当作正常方案**。

### 7.3 稳健性

1. 食物营养数值扰动（仅在合理来源误差范围内，标注 synthetic perturbation）。
2. 主观权重从四种 profile 改为固定网格；输出排名 Kendall τ / 翻转率。
3. LLM Prompt 的措辞与角色顺序变化，测量稳定性。
4. LLM 关闭或超时，检查固定回退机制是否产生完整、可审计的结果。
5. 同样的 `input_hash` 重放时是否可从缓存检索到原始响应与版本。
6. 紧急输入/对抗文本不得越权更改营养数值、评估字段或系统 Prompt。

## 8. 数据划分、统计与防泄漏

- 以 `user_id`, `food_id`, `pair_id`, `menu_id` 为稳定主键；测试配对在采集前由脚本生成并哈希冻结。
- 设计 `train/val/test`：TasteNet 的 train 由 40 道训练题构成；调参通过训练数据的内部验证/交叉验证；10 道题为最终测试。`heldout_food_ids` 与任何训练校准标签互斥。调参时不读取测试标签。
- Multi-Agent 的菜单应有 `development_menu_ids` 与 `final_eval_menu_ids`；Prompt、评分权重、温度、κ 校准参数只在 development 设置。
- 以**受试者**为首要抽样单位的聚类 Bootstrap（建议 2,000 次）输出主要指标差的 95% CI；若资源限制可先做 200 次以验证代码，但不能在论文中将其作为最终 CI。
- 预注册主指标 H1=NLL 差、H2=总体偏好的 NLL/准确率；其余标记 exploratory。差异置信区间跨零时不报告“显著提升”。
- 24 人属于小型探索性样本，分组主动学习试验尤其可能统计功效不足。论文应直接报告样本量和 CI，不造出 p 值显著性。

## 9. 主要论文图表预定

| 编号 | 图/表 | 必须标示的真实来源 |
|---|---|---|
| Fig. 1 | BITE Pipeline（FoodBench→TasteNet/Oracles→Agents→Aggregator） | 研究方法示意 |
| Fig. 2 | TasteNet 学习曲线：查询预算 vs NLL | 人类留出数据（或醒目 Demo） |
| Fig. 3 | 用户 × 食物口味热力图 | 人类偏好或模型估计，图注区分 |
| Fig. 4 | 多 Agent、单 Agent、规则模型在外部偏好上对比 | 人类独立比较 |
| Fig. 5 | 7/30 天策略模拟：客观约束、重复率、参考效用 | SIMULATION |
| Fig. 6 | Taste–nutrition Pareto Front / 权重敏感性 | 标准化餐单及预注册评分 |
| Table 1 | FoodBench 数据数量、来源、缺失率、质量层级 | 经审查的实际表 |
| Table 2 | 主实验结果（CI、单位、种子、样本量） | 真实测试集 |
| Table 3 | 消融与计算成本 | 可复现实验日志 |

图表生成脚本必须读取 `results/*.parquet` 或 `metrics.json`，而非直接写死图表值。模拟图需清晰标注“Simulation”；没有真人标注时只能输出 Demo，不得称为实证结果。

## 10. 工程环境与资源边界

建议部署：Windows 10 19045 主机的 **WSL2 Ubuntu**（需实际检查是否已启用），CUDA 能用则运行量化本地 LLM，TasteNet 先使用 CPU 的 `numpy/scipy/sklearn` 基线；后续需要才加入 PyTorch。推荐 `Qwen3-4B-Instruct-2507 Q4_K_M` 经 Ollama **一份模型顺序扮演四角色**；推理结果 JSON Schema 验证。Ollama 模型发布页面显示约 2.5GB 模型文件，但这不等于最大 VRAM 使用量；KV cache 和框架额外消耗需实测。建议从 4K 左右的上下文开始。

重要：服务器主机 RTX 5060 8GB、32GB RAM、i5-13400F，优先保证项目可在 CPU 上完成数据库与数学模型任务；LLM 不可用时按 `mock`/`fallback` 跑通管线，并在结果里显著标识“不可用于正式 Multi-Agent 性能结论”。

Windows/WSL 安装按 [NVIDIA CUDA on WSL](https://docs.nvidia.com/cuda/archive/12.8.1/wsl-user-guide/index.html)；不可在 WSL 中误装 Linux NVIDIA 内核驱动。PyTorch 的 CUDA wheel 请按官方当前安装页面验证，不能将 Windows 驱动 `CUDA Version` 直接当成 PyTorch wheel 版本。Ollama JSON Schema 参考其 [Structured Outputs](https://docs.ollama.com/capabilities/structured-outputs)。

## 11. 验收与结论表达原则

**最低可接受的完整研究版本**：营养来源可追溯；TasteNet 在冻结测试集评估；M0–M4 可重复跑通；Multi-Agent 与外部真人偏好有独立比较；至少 7 天模拟在相同候选集和种子下比较；所有消融输出 CI 和有效样本量；代码、配置、失败日志、随机种子可归档。

可能结果：如果多 Agent 的成绩没有超过固定规则或单 Agent，应如实解释其推理成本、角色冗余和稳定性问题。**论文的吸引力来自问题与发现，不来自必胜的预设。**

## 12. 伦理与数据管理

参与者须知情、自愿、18 岁及以上（项目不面向儿童）。不采集姓名、身份证、精确位置、健康诊断等无关信息；随机化 ID 替代身份。提供退出与删除本人数据的办法。偏好标注数据可能间接涉及饮食限制，避免收集敏感解释。若将来作为正式涉及人的学术研究投稿或公开数据，先按照所在机构的程序咨询伦理审批/豁免要求，再开展相应采集和发布。营养评价不应以“好/坏食物”道德化个人选择。

数据目录与 Git 规则：`data/raw/human/`、`data/private/`、`.env`、带授权限制图片不提交公开仓库；可以公开审计过的营养表、匿名且获授权的衍生数据、模拟数据及代码。记录同意版本、保留期限、许可。

## 13. 与 Codex 实施文件的关系

本文件定义科学问题、原则、实验标准，具有**方法学优先级**。配套《BITE_Codex_实施与实验手册.md》定义文件结构、命令、模块接口、可执行测试与执行顺序。若工程实现与本文件冲突，Codex 必须显式提出差异并修正实现或提交变更建议，不能静默修改研究方法。

## 14. 主要外部参考与当前核查链接

- USDA FoodData Central API Guide：https://fdc.nal.usda.gov/api-guide/
- USDA FoodData Central Data Documentation：https://fdc.nal.usda.gov/data-documentation/
- Open Food Facts License：https://openfoodfacts.github.io/openfoodfacts-server/api/tutorials/license-be-on-the-legal-side/
- WHO, Healthy diet（2026-01-26；适用于膳食原则而非本研究评分公式）：https://www.who.int/news-room/fact-sheets/detail/healthy-diet%E2%81%A3%E2%81%A0
- Ollama Qwen3 4B Instruct 2507 Q4_K_M：https://ollama.com/library/qwen3:4b-instruct-2507-q4_K_M
- Ollama Structured Outputs：https://docs.ollama.com/capabilities/structured-outputs
- NVIDIA CUDA on WSL：https://docs.nvidia.com/cuda/archive/12.8.1/wsl-user-guide/index.html
- PyTorch Install：https://pytorch.org/get-started/locally/

**声明**：参考链接支持工具、数据来源与基本膳食原则，不代表本研究 BITE 指标已得到同行评议或医学验证。`v1.0` 中全部样本量、模型结构与超参数都是**预期方案**，在正式结果收集前需要冻结一个 `protocol.lock.yaml` 版本。
