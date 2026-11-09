HiMCM B — CP-SET 论文工程（Team 18588）
本轮：Task 3 改为 Fremont Street Experience + Honolulu Zoo 售票排队区。

打开与编译
当前论文：HiMCM-MidMCM_Summary.pdf
共24页：计入限制23页，独立AI报告1页；Task 3位于第15—18页。
双击 compile.command，或在本目录运行 zsh compile.command。
使用本机 /Library/TeX/texbin/latexmk + pdfLaTeX；中间文件在 build/。
移动、复制或交接时请一起保留整个工程，正文使用相对路径加载素材。

本轮正文
Task 3 以8382 m²步行街分析区与60 m²售票排队分析区进行跨尺度比较。
Fremont天幕长419.1 m来自官方；有效宽度20 m、Honolulu的10×6 m、
分区、人数、天气快照及设备输送参数是表3集中列出的规划假设。
热湿性质、局部h/w混合、SET、服务U/电能E沿用原CP-SET计算链。
全设备三段先算SET超额再按面积平均；需求区与设备送风段是两种划分。
此轮采用固定背景的开放场地极限；四段人数积分不假装求解新的背景ODE。
Task 3只比较效率与物理服务输出；覆盖门槛、费用及体验代理进入Task 4。

新增分析
1. 单台贡献的能耗加权平均给出全部整数可行布局的效率上界。
2. 最大可容纳纯A/B/C方案、固定几何与人数的气候交换、同密度比较。
3. 固定气候下，面积/人数同比扩大，设备保持不变或同比复制。
4. 独立边缘试验依次截去远、中、近送风段；完整设备功率和水量照计。
5. 湿度、平均辐射温度、自然风和可用面积敏感性。
6. 下游Task 4、摘要、COO备忘录和博客同步采用同一组新场地结果。

主要结果
Task 3名义效率上界：Fremont16.54，Honolulu47.71 person·℃·h/kWh。
最大可容纳纯设备：Fremont A419/B279/C209的效率11.88/5.06/5.72；
Honolulu A3/B2/C1为47.71/21.28/20.63。C1只覆盖队列的2/3。
B/C排序随气候交换而反转；Fremont背景风速0.8 m/s时效率最优型变为C。
固定密度下按比例复制设备的效率不变属于模型相似性性质，并非实测验证。

Task 4是明确政策下的全整数MILP最小年成本：Fremont A266C16；Honolulu A1B1。
两者名义求解gap均为0。不是将混合设备作为预先指定的目标。
Honolulu A3已提供1.4908℃平均改善，1.5℃政策仅高出0.0092℃；
目标降至1.49℃时改选A3。Fremont全局人时约束的最优布局对第三分区覆盖很低，
正文明确讨论分区服务要求；不能将该配置理解为全走廊均匀保护。

替换与重绘图表
所有图仍为独立PDF，正文只用includegraphics载入。
figures/27_venue_comparison.pdf    新场地纯设备效率和平均服务
figures/30_scale_transfer.pdf      受控尺度与边缘截断
figures/31_venue_layouts.pdf        概念分区与人数时序
figures/28_effectiveness.pdf       下游年成本和服务目标曲线
figures/29_cp_set_framework.pdf    更新后的全流程图
图1—11对应的原核心素材、原公交/Canberra物理代码及数值文件保持原样。

代码与源数据
venue_model/run_venues.py          新场地计算、MILP、敏感性与图表
venue_model/inputs.json            全部场地和经济假设
venue_model/local_conditions.csv  设备各局部条带的热湿/SET状态
venue_model/linear_coefficients.csv 每个zone/type的服务、能耗与成本系数
venue_model/results.json          上界、纯设备、政策最优及求解gap
venue_model/climate_cross.csv     气候交换及固定密度对照
venue_model/scale_checks.csv      面积、人数和设备的受控缩放
venue_model/boundary_clipping.csv 边缘条带保留面积与完整设备计量
venue_model/physical_sensitivity.csv / cost_sensitivity.csv / policy_curves.csv
venue_model/independent_audit.py   不调用原求解器的独立重算与小场地穷举
references/task3_sources.txt      一手来源、事实/估计边界与访问日期
sections/applications.tex         Task 3正文
sections/task3_values.tex / task3_results_table.tex 从JSON生成的数值片段

复现命令
/Users/sunyijie/Documents/code/himcm-2026-b/.venv/bin/python venue_model/run_venues.py
/Users/sunyijie/Documents/code/himcm-2026-b/.venv/bin/python venue_model/independent_audit.py
/Users/sunyijie/Documents/code/himcm-2026-b/.venv/bin/python figure_sources/make_task3_tables.py
/Users/sunyijie/Documents/code/himcm-2026-b/.venv/bin/python figure_sources/make_cp_set_framework.py
zsh compile.command
重算物理参数后，摘要及下游手写数值段也须按results.json同步更新。
审计包括守恒、SET定义、完整电耗/水量、Honolulu全部9布局、尺度与政策核对；
断言数量不代表相同数量的独立实验。最新分页、哈希与检查见revision_verification.json。

备份与提交材料
本轮替换前完整工作内容保存在backups/before_task3_fremont_honolulu/。
按先前用户选择，正文保留一处最简AI披露及参考项，其余置于独立AI报告。
真实会话导出和Gemini原始记录需由团队保存并按COMAP政策附入AI使用档案。
