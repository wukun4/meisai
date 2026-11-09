HiMCM B 论文工程 — 2026-11-08 效率与综合效果分层修订

打开与编译
主文件：HiMCM-MidMCM_Summary.tex
当前PDF：HiMCM-MidMCM_Summary.pdf
双击 compile.command，或终端执行 zsh compile.command。
使用本机 /Library/TeX/texbin 的 latexmk/pdfLaTeX；build/ 保存编译中间文件。
整个工程文件夹可一起移动，LaTeX引用均为相对路径。

本次修改
Requirement 1—3统一围绕冷却效率；服务充分性、访客体验、能源和成本权衡移到Requirement 4。
第二问使用η=U/E比较：全部24个候选中A3最高，六个等覆盖基准中A36最高。
覆盖率和SET保留在有效服务量的计算中，不另设覆盖率或剩余不适的方案准入门槛。
第四问新增四目标框架和带门槛的条件选择规则；成本/非热体验尚未校准，不宣称综合最优。
本次仅重组正文和从固定CSV重绘图表，物理计算代码、输入与数值输出均未修改。

保留的统一模型
冷柜：给出对象数量、服务质量、持续时间与能耗的共同评价结构。
公交：从局部热湿守恒推导送风/背景混合；原名义结果保留，并补设备发热敏感性。
车站：沿用设备、局部混合、SET和服务模块，动态计算背景温湿度与表面温度。
局部送风最终返回背景；设备热量和水分只计一次。
beta表示送风干空气混合比例；c表示人群覆盖比例，两者不能混用。
正文chi(χ)表示到达乘客前进入送风的设备电热比例；代码key仍叫alpha。
正文几何alpha(α)=0.8是候车面积有效比例，与电热比例无关。
研究引用和方法边界已经写入正文；墨西哥食堂实测结果不被当作Canberra参数。

当前范围
包含Requirement 1和2(a)/(b)，以及Requirement 4的部分决策框架，仍是工作稿。
Requirement 3的跨场馆应用、Requirement 4成本/体验标定、Requirement 5和最终摘要尚未完成。
数值为明确假设下的情景模拟，未声称现场验证或真实安装方案。
食品kg·h/kWh与人体舒适person·℃·h/kWh不能直接作数值排名。
当前名义情景的设备比较，不代表所有气候和送风条件下的普适排序。

文件组织
sections/rail_model.tex       车站推导与说明
sections/unified_results.tex  车站效率结论和表格
sections/effectiveness.tex    第四问综合效果扩展，含四目标、成本与条件选择规则
model/                       公交代码、输入、六张原数值图及新增发热敏感性CSV
shared_model/                公交/车站共用局部混合函数、退化验证及旧版基准数据
deployment_model/           Canberra动态背景、局部送风、候选部署和全部敏感性结果
spatial_visualization/        乘客局部暴露温降、SET改善与人群位置图；无连续空间插值
figure_sources/              图19及22—25源码、原始示意图与图表检查结果
references/                  新研究的阅读笔记与原文提取文本，正式引用见论文
figures/                     全部单独PDF，可直接替换同名文件后重新编译
station_model/               早期三台设备开发记录，并提供现模型复用的物理函数
backups/before_unified_revision/ 前次统一模型修订前的备份
backups/before_scope_revision/   本次效率/综合效果分层修订前的备份

图表
00 旧版服务流程（保留作素材，本次正文改用19）
01—06 公交局部状态、效率/质量、湿度、人群、送风损失、敏感性
07—09 用户候车亭、计算分区、开放式冷柜示意图
10—12 早期局部候车区结果（开发记录，当前正文不用）
13 Canberra原始结构示意图
14 当前24候选的电耗—剩余不适比较（已移到第四问，仅二维投影）
15 等覆盖方案的设备数量和剩余不适（补充素材）
16 数量—覆盖及覆盖面积敏感性（补充素材，第二问正文不用）
17 各功能区乘客加权局部温降和SET改善（补充素材）
18 设备配置、人群覆盖与服务收益地图（补充素材）
19 三种环境的模型继承关系
20 局部混合beta与送风发热chi的效率/性能敏感性（补充素材）
21 原车站评价的退化恢复、背景与局部动态对照（补充素材）
22 车站24候选及设备数量的效率比较（第二问正文）
23 局部送风beta/chi的纯效率敏感性（第二问正文）
24 公交干湿两种情景的纯效率比较（替换正文原02图）
25 覆盖面积假设对效率的敏感性（独立补充素材）

图表均由独立PDF载入，没有改成论文内嵌绘图代码。
正文优先展示机制和主要结论，其他图和原始CSV仍完整保存。
不要只改图中数字而不更新正文和对应结果表。

重算（需要 model/requirements.txt 所列Python依赖）
python model/simulate.py
python shared_model/verify_bus_delivery.py
python deployment_model/simulate_deployment.py
python spatial_visualization/make_spatial_maps.py
python figure_sources/make_model_inheritance.py
python figure_sources/make_efficiency_scope.py
zsh compile.command

用于本机计算的Python：
/Users/sunyijie/Documents/code/himcm-2026-b/.venv/bin/python

检查结果
model/unified_delivery_checks.json：共享映射、公交恢复、发热敏感性。
deployment_model/results_summary.json：预算、步长、局部闭合、旧24候选恢复等。
spatial_visualization/verification.json：图中分区服务量与总结果一致。
figure_sources/efficiency_scope_validation.json：固定CSV的13项一致性与效率排名检查。
revision_verification.json：本次编译、分页、数值文件不变和图表核对记录。
本次未重跑物理求解；原19项车站、6项公交计算检查来自前次修订，相关代码和数据保持不变。
上述检查验证数值实现，不替代现场测量。
旧版结果回归基于固定基准情景；修改参数时，应保留该基准测试，另运行新情景。
