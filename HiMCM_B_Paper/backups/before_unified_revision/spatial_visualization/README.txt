Canberra 分区可视化草图

用途
为当前三功能区模型提供可核对的空间对照，帮助判断设备是否服务于人群。
两张图保持为独立 PDF；本次尚未改动正文或主论文 PDF。

文件
../figures/17_zone_thermal_maps.pdf：七种配置的空气温降与 SET 改善矩阵。
../figures/18_occupancy_service_maps.pdf：A36、AB30、AB30-R 的功能区示意、
  人流、局部设备数量、覆盖率及分区服务量。右侧柱状图使用相同横轴范围。
17_zone_thermal_maps.png、18_occupancy_service_maps.png：便于快速查看的预览。
zone_comparison.csv：全部 21 个“方案-区域”的汇总数据，保留未四舍五入数值。
verification.json：数值核对结果与原始输入的 SHA256。
make_spatial_maps.py：完整后处理和绘图程序。

数据与来源
直接读取工程已有 deployment_model/scenario.json、time_series.csv、
candidate_results.csv。原模型、参数来源与参考文献见 deployment_model/README
及 sections/rail_model.tex 和主论文参考文献。本图没有增加实测数据。
三功能区 Access（出入区）、Core（核心候车区）、Edge（边缘区）分别为
352 平方米。两小时平均人数为 57.2、121.0、41.8；对应人时为
114.4、242.0、83.6 person-hour。面积、人流及送风范围均为规划情景假设。
A 为风扇；B、C 为两类蒸发设备，规格采用原模型定义。
方案编号中的数字是全站总台数，图块内的设备数字是当地台数。
AB30-R 保持 AB30 的 18A+12B，总台数和耗电相同，只改变分区数量分配。

计算定义
设 i 为时间样本，z 为区域，s 为方案，n[z,i] 为当地人数，时间步长为 dt。
下标 0 为相同天气与人流下的无设备基准，所有差值均为“基准减方案”。
空气温降 = sum_i n[z,i]*(T[0,z,i]-T[s,z,i]) / sum_i n[z,i]。
SET 为模型采用的 Standard Effective Temperature（标准有效温度）。
每区的未直接送风人群及 A/B/C 覆盖人群共享该区 T、RH、MRT，
各自使用原模型的风速；SET 由 pythermalcomfort.models.set_tmp 重新计算，
使用站立、1.2 met、0.5 clo，以及原情景气压等参数，不从不适值反推。
SETbar[s,z,i] = sum_g f[s,z,g]*SET[s,z,i,g]，g 指上述四个人群子组。
图中 SET 改善 = sum_i n[z,i]*(SET[0,z,i]-SETbar[s,z,i]) / sum_i n[z,i]。
直接覆盖率 f 的计算与原模型一致：每类设备数量乘覆盖面积，再除以分区面积，
各设备足迹假设不重叠，区内人群假设均匀分布。

D[s,z,i] = sum_g f[s,z,g]*max(SET[s,z,i,g]-26,0)。
分区服务量 U[z] = sum_i n[z,i]*(D[0,z,i]-D[s,z,i])*dt/3600，
单位为 person·°C·h。负值表示该区不适加重，不能截断为零。
SET 改善与不适缓解是不同定义。本次情景所有相关 SET 都在参考值以上，
因此两者数值相同；改变情景后不保证相同。
所有分区 U 相加须复现原候选的总服务量，人时相加须复现原总人时。

读图与限制
同一指标在所有方案中使用共同的零中心色标：蓝色为降低，红色为增加。
两种指标的单位相同但色标范围分别设定；比较前应读色条。
A36 的空气温降为负，因为原模型将设备电功率全部计为当地显热；
其 SET 改善仍为正。图保留这两个结果，不能把风扇画成降低空气温度。
AB30-R 核心区 SET 改善增加，但出入区、边缘区收益下降；
这一配置演示分配权衡，不代表它在所有方案中最优。

这两张图只表达三功能聚合区，不是实测站台平面或连续温度场。
矩形的相邻关系与轨道条带大小只作示意，不表示真实轨道或平台位置。
轨道及非候车区域不获得乘客服务收益，且未建立热湿状态。
灰色斜线表示“未求解”，不是“零温降”；不能由此推断轨道没有热交换，
或据此计算逸散到轨道的冷量。不要对三个区作平滑插值冒充精细空间预测。
这些图可诊断模型的分配效果，不能仅凭颜色验证实际安装的可靠性。

若要获得真正的站台温度/SET 分布，需要进一步明确平面几何、设备坐标、
障碍物、开口、乘客分布及气流交换。可先细分控制体，再根据数据条件决定
是否采用二维网格/CFD；应同时报告气流或换热参数假设与网格敏感性。
若把轨道纳入热传输计算，应将“热湿计算域”和“乘客收益计分域”区分：
轨道仍允许传热和气流交换，但乘客权重为零。

复现
在工程根目录运行：python3 spatial_visualization/make_spatial_maps.py
依赖沿用 model/requirements.txt；本次使用 Python 环境：
/Users/sunyijie/Documents/code/himcm-2026-b/.venv/bin/python
运行会更新两张 PDF、PNG、CSV 及核对记录；不改动热湿模型输入或正文。
图中单位、公式与数据核对已检查，交付 PDF 也经过 Poppler 渲染查看。
