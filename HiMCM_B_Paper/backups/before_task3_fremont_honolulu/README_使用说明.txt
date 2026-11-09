HiMCM B — CP-SET 完整五问稿（2026-11-08）

打开与编译
当前论文：HiMCM-MidMCM_Summary.pdf
主文件：HiMCM-MidMCM_Summary.tex
双击 compile.command，或运行 zsh compile.command。
使用本机 /Library/TeX/texbin 下的 latexmk/pdfLaTeX；build/ 保存中间文件。
请一起移动整个工程，所有正文和图表使用相对路径。

本次重构
1. 第2—4页包含 Introduction（Background/Problem Restatement/Our Modeling Framework）、
   五条 Assumptions and Justifications、双栏三线 Nomenclature 表。
2. 方法正式命名 CP-SET Framework；新增完整任务流程图。
3. Task1—2完整保留原33个编号公式与11个核心图；平均残余符号统一为 Rbar。
   两问连同新增干热测试位于第5—14页，共10页；正文使用12pt。
4. Task3新增Phoenix Ullman Terrace和Singapore Satay Street两个具体场馆。
   全候选η排名不施加覆盖、残余、成本门槛；等覆盖比较单列。
5. Task4用热性能、通行空间、年能耗和年成本做约束决策，含价格/物理敏感性。
   覆盖约束下的Pareto集合与全候选效率集合分开报告。
6. Task5包含给HiMCM COO的一页备忘录及公众博客。
7. 所有场景估计及合理简化集中Section2；正文去除反复的防御性免责声明。
   经用户确认，正文保留一句最简AI披露及两项参考文献；其余说明在独立AI报告。

最终分页
21页计数内容（摘要、目录、完整解答、备忘录、博客、参考文献）+1页AI报告。
所有图表仍为单独PDF，正文只用includegraphics载入，可直接替换后重新编译。
图26/27/28/29分别为干热测试、跨场馆效率、综合效果与完整框架图。
其他旧图继续保留为计算素材；原有图形与模拟结果未被覆盖重算。

关键结果
极热干热：40℃、RH15%/20%下，A的η仍最高；C提供更大的人均SET改善。
39℃域内检查保持相同排序。42℃及较高MRT只存作显式诊断外推，不用于正文结论。
跨场馆：等60%覆盖时，Phoenix的C效率高于B；Singapore的B高于C。
综合政策：Phoenix A10C2，Singapore A10；推荐条件、价格和服务门槛见Section2及Task4。
这些结论来自公开场地背景和表列规划参数，源数据与计算链保存在工程中。

正文文件
sections/introduction.tex         引言与全流程图
sections/assumptions.tex          五条假设、公交/站台参数
sections/venue_assumptions.tex    新场馆及成本/政策参数
sections/nomenclature.tex         核心符号
sections/core_models.tex          Task1与公交模型
sections/extreme_heat.tex         新增干热测试
sections/rail_model.tex           站台模型
sections/unified_results.tex      站台效率结论
sections/applications.tex         Task3跨场馆比较
sections/effectiveness_complete.tex Task4四目标决策
sections/operator_memo.tex        COO备忘录
sections/public_blog.tex          公众博客
sections/references_complete.tex  参考文献主文件
sections/references_venues.tex    新场馆及运营来源
sections/ai_report.tex            独立AI说明
旧版未完成的 sections/effectiveness.tex 已移出活动工程，替换前版本保存在备份内。

计算与图表
model/：公交模型；新增extreme_heat_test.py及分开的有效/边界与诊断CSV。
shared_model/、deployment_model/：共用局部混合、Canberra动态模型及冻结结果。
venue_model/：新增场馆完整整数枚举、成本、尺度及敏感性结果。
figure_sources/：可重绘图源；make_cp_set_framework.py生成完整框架图。
figures/：全部独立PDF。
references/：原研究笔记、干热适用域审计及新场馆来源审计（含访问日期）。

本次新增计算的复现命令
/Users/sunyijie/Documents/code/himcm-2026-b/.venv/bin/python model/extreme_heat_test.py
/Users/sunyijie/Documents/code/himcm-2026-b/.venv/bin/python venue_model/run_venues.py
/Users/sunyijie/Documents/code/himcm-2026-b/.venv/bin/python venue_model/verify_scope.py
/Users/sunyijie/Documents/code/himcm-2026-b/.venv/bin/python figure_sources/make_cp_set_framework.py
zsh compile.command
Python依赖沿用model/requirements.txt；验证记录见revision_verification.json及各计算目录。
本次未重跑原公交/车站整套求解；原物理代码、参数及既有数值文件保持不变，前次检查记录保留。

版本和提交资料
本次替换前备份：backups/before_competition_revision/
队号已按用户提供的信息设置为18588。
AI报告列明工具与用途；请将真实会话导出和Gemini原始记录随团队的AI使用档案保存，
按COMAP要求补入完整提示与保留输出。具体模型版本应来自原始工具记录，勿凭空补写。
