HiMCM B 论文工程

日常使用
1. 编辑 HiMCM-MidMCM_Summary.tex。
2. 图表都在 figures/，每张图是独立 PDF，主论文不包含绘图代码。
3. 替换图片时，覆盖同名 PDF 即可；也可以修改主文件里的 includegraphics 文件名。
4. 双击 compile.command（或在终端运行 zsh compile.command）。脚本使用本机
   /Library/TeX/texbin 下的 latexmk / pdfLaTeX，编译结果更新到工程根目录的
   HiMCM-MidMCM_Summary.pdf。build/ 仅保存编译中间文件与日志。
5. 整个文件夹一起移动仍可编译。直接在其他 LaTeX 编辑器中打开主 .tex 也可以；
   编辑器工作目录需设为本文件夹，或运行所附脚本。

文件结构
HiMCM-MidMCM_Summary.tex       主论文源文件
HiMCM-MidMCM_Summary.pdf       本机编译的论文
figures/                      13 个独立 PDF 图表（下列文件）
figure_sources/               流程图、原始冷柜/候车亭图片及分区图的独立绘图源文件
model/                        公交站模型、六张数值图与 CSV 结果
station_model/                半开放铁路候车区动态模型、三张新图与验证结果
sections/rail_model.tex        Task 2(b) 的英文正文，由主文件载入
compile.command               使用本机 TeX Live 的编译脚本
build/                        编译中间文件，不需要手动编辑

图表对应
00_cooling_service_process.pdf   第一题：从运行条件到服务效率的流程图
01_local_conditions.pdf          巴士站：分区温度、湿度和 SET
02_efficiency_and_quality.pdf    单位电耗收益与剩余不适
03_humidity_sweep.pdf            湿度变化
04_occupancy.pdf                 乘客空间分布
05_delivery_decision.pdf         送风损失下的条件选择图
06_sensitivity.pdf               参数敏感性
07_bus_shelter_geometry.pdf      用户提供的候车亭基准结构图
08_shelter_zoning.pdf            由纽约市尺寸导出的三分区平面图
09_open_display_case.pdf         第一题：开放式多层冷藏展示柜结构图
10_rail_dynamics.pdf             站厅人流、换气与热湿状态随时间变化
11_rail_efficiency.pdf           站厅三种设备的效率及剩余不适
12_rail_ventilation.pdf          站厅外界空气交换的敏感性

修改绘图数据
六张数值图的输入为 model/scenario.json，计算与绘图程序为 model/simulate.py。
如需重新绘图，请使用 Python 3.11 以上版本，并安装 model/requirements.txt 中的依赖。
图表 PDF 可直接独立替换；仅替换 PDF 和重新编译论文不需要安装 Python。
第一题流程图源文件位于 figure_sources/，可修改后运行该目录内的
rebuild_process.command 单独生成对应 PDF。
不要只修改图中数字而不相应更新正文结果。

研究状态
当前稿包含第一题及第二题 2(a)、2(b)，不表示整篇比赛论文已完成。
图中数值是明确假设下的情景模拟，并非真实设备测试数据。
正文保留来源引用、未完成部分说明和初步 AI 使用记录。
桌面原来的同名散放文件为之前的版本；后续请以本工程内的主文件为准。

新增候车亭图说明
figure_sources/bus_shelter_original.png 保留原图，make_shelter_geometry.py
将原图排入独立 PDF，正文中的图号和来源由 LaTeX 统一管理。
正文和模型现统一采用纽约市常规型（Regular）候车亭尺寸：
长4.2672米、宽1.5240米、高2.7178米，毛平面面积6.5032128平方米。
沿长度三等分，每区面积2.1677376平方米。来源是NYC Street Design Manual，
不是纽约州所有公交站台的统一尺寸。
天气、人流和局部送风仍是明确假设；12人不是实测客流或核定容量。
make_shelter_zoning.py读取model/scenario.json与几何模块，可独立重绘分区PDF。
人流数量和局部送风条件保持不变时，六张数值图结果不变；这是当前模型的条件性质，
不意味着真实气流与几何无关。model中的geometry_checks.json记录几何相关验证。
实际部署仍需测量座椅/结构占地、净可用区域、人流及送风情况。
原图是位图，PDF保留其像素内容，不声称已转成真正的矢量绘图。
插图前论文备份保存在 backups/before_shelter_diagram/。

本次采用真实尺寸前的工程备份保存在 backups/before_nyc_geometry/。

新增开放式冷柜图说明
原始“开放式冷柜.png”保留在工程根目录，同时备份为
figure_sources/open_display_case_original.png。
figure_sources/make_open_display_case.py 可重新生成独立插图 PDF。
PDF保留原始像素，仅用页面视窗省去图片底部原有图号与来源行；
主论文统一显示图号、图注及核实后的厂家引用。
图中Hillphoenix CF为中温冷藏展示柜，用来说明开放式结构和层架位置，
没有把它写成冷冻储存设备或将外形尺寸当作制冷性能数据。
此次插图前的主稿备份位于 backups/before_open_display_case/。

半开放铁路候车区模型
station_model/scenario.json 保存所有情景假设；simulate_station.py 读取这些参数，
并调用 model/thermal_backend.py。运行方式见 station_model/README.txt。
正文推导位于 sections/rail_model.tex，三张图均为独立 PDF，可分别替换。
站厅长宽高、空气交换、设备循环风量和列车人流曲线均为示例假设，
不代表某个实际车站；验证针对守恒、数值收敛和指标一致性，不是现场精度证明。
新增 Task 2(b) 前的改动文件备份位于 backups/before_rail_model/。
