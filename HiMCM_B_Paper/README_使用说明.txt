HiMCM B — CP-SET 论文工程（Team 18588）
2026-11-08 视觉升级定稿

当前论文与页数
HiMCM-MidMCM_Summary.pdf 共26页。
Summary Sheet 至 References：25页；Report on Use of AI Tools：第26页，独立计数。
新增连续二维场为正文Figure 11（第14页）；美国气候地图为Figure 12（第16页）；
电耗/服务与雷达复合图为Figure 16（第21页）。Section 9第22页，备忘录第23页，
科普博客第24页，References第25页。之前的六项文字精修及五张场景图均已保留。

打开与编译
双击 compile.command，或在项目目录运行：zsh compile.command
使用本机 /Library/TeX/texbin/latexmk + pdfLaTeX；编译中间文件在 build/。
工程使用相对路径，移动与交接时请保留整个文件夹。

高清图与Python脚本
visual_upgrade/make_figures.py：一次生成6组PDF和300-DPI PNG。
新增3组主图：
 figures/34_continuous_thermal_fields.{pdf,png}
 figures/35_us_climate_potential.{pdf,png}
 figures/36_energy_service_radar.{pdf,png}
合并图：37_bus_efficiency_delivery、38_station_efficiency_sensitivity。
统一温度色标图：39_bus_local_fields（原公交站局部结果，数值不变）。
Python依赖见 visual_upgrade/requirements.txt；全部原始气候数据已经归档，复图无需联网。
复图：python visual_upgrade/make_figures.py
随后：zsh compile.command
详细方法、归一化规则和数据边界见 visual_upgrade/README.txt。

图表解释
1. 二维场是原三分区结果的300×100空间重建。设备与人群点位为明确披露的假设；
   h、w混合后重算局部T、RH与SET，流线展示给定的运动学速度场，不声称做了CFD。
   原两小时U/E/q及原MILP结果不从这张示意重建图重新积分。
2. 美国地图使用NASA POWER的77个7月气候平均状态，接口实际基准期2001—2025。
   月平均状态下的湿球抑郁不等于逐小时湿球抑郁的月平均。NYC、Fremont和Honolulu
   的原论文设计工况保留，并与气候背景分开标注。包含本土48州及夏威夷，未画阿拉斯加。
3. kWh电耗与person·°C·h的SET服务量分轴展示。U+R=R0是服务余额，不能伪装成能量分流。
   原输出没有电机、换气、空置区的可识别能量损耗份额，因此未虚构这些比例。
   雷达展示纯设备与政策选中混合方案的权衡，不是新目标函数或全面占优证明。

核心结论保留
Fremont：A266C16；Honolulu：A1B1；名义MILP gap均为0。
Honolulu平均改善目标从1.50°C降至1.49°C会选择A3，阈值敏感性不变。
74个原始CSV/JSON/Python数据与计算文件哈希一致；30个显示公式块、39个编号公式不变。
逐页视觉检查与LaTeX编译完成；无溢出、缺字或未解析引用。
最新校验：visual_upgrade/final_verification.json、verification.json、frozen_manifest.json。
旧 revision_verification.json 对应上一轮文字精修，作为历史记录保留。

来源与可复现数据
visual_upgrade/data/climate_samples.json：77个地点、原始URL、时间范围与SHA-256。
visual_upgrade/data/power_*.json：NASA原始响应。
visual_upgrade/data/us-states.json、sources.json：州界及来源。
visual_upgrade/data/spatial_*.npz：二维T/SET/RH/MRT/u/v/beta网格。
visual_upgrade/data/spatial_*_assumed.csv：假设位置。
visual_upgrade/data/radar_values.csv：原始指标、归一化数值与分母。
原物理、场地与MILP模型保留在 model/、station_model/、deployment_model/、venue_model/。

提交材料
正文和正式参考文献中不含AI工具说明，相关说明集中在最后一页。
团队需保留真实对话记录及原始工具输出，供AI使用档案核对。
更新前桌面版本在 backups/ 下保留；交付ZIP省略历史备份、缓存与编译中间文件。
