---
name: rfic-codex-design
description: Design and verify RF power amplifiers with RFIC-GPT and Cadence. Use for PA or matching-network candidate design, Wizard import, EMX extraction, Spectre simulation, input impedance measurement, load-pull, or simulation-driven PA tuning.
---

# RFIC Codex Design

先确认工艺、供电、中心频率、验收频带和硬性指标。区分在线估算、有源核心仿真、理想负载牵引和含实际匹配网络的整机仿真；不要拿前几种结果替代后者。网站的中心频率字段始终填中心点；带宽另有字段时按接口填写，整机仍按用户指定频带验收。

按任务读取 [运行说明](references/workflows.md) 对应章节：

- 在线候选：用 `assets/rfic_codex_project_web` 的 `PA` 或 `MatchingCircuit`；先确认账户、积分及提交授权。只准备参数时不要运行或导入客户端。
- 环境：分别检查主机与虚拟机所用的 Python 解释器和依赖；缺包时在对应环境中按 `requirements.txt` 安装并复查。把 Cadence 工作副本放在有效 `.cdsinit`、`cds.lib` 所在的 Virtuoso 启动工作目录下。调用 `create_lib()` 和 `register_symbolLib()`，分别创建工艺绑定设计库、注册随附符号库。Wizard 需要图形会话；EMX/OCEAN 使用命令行。
- 优化：用工作频带内 S11/S22 先判断失配发生在哪一端。失配优先调对应网络的 Cp/Cs，必要时测 Zin、更新输入匹配，再固定 IP1dB 做 load-pull 并回代负载；收敛后设计输出网络。匹配尚可但性能仍不足时，先调放大管尺寸使增益、OP1dB、效率达标，再调中和管尺寸使 Kf > 1、B1f > 0；最后复查整机性能与匹配。

每轮保存生成代码、Cp/Cs、阻抗和端口约定、对应的两个四端口模型及仿真条件。发现日志、结果文件和实际运行状态不一致时，先验证产物，不盲目重试或覆盖。达到指标、收到停止要求、用完迭代预算或缺少必要环境时，汇报实测值、未通过或未验证项、结果路径与下一步。
