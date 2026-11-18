# RFIC CODEX Design

用 Codex 结合RFIC-GPT 与 Cadence Virtuoso：从自然语言指标出发，获取有源核心和匹配网络的生成代码，在 Virtuoso 中生成电路与版图，用 EMX 和 Spectre 验证整机，再按仿真结果优化迭代。

## 项目概述

### RFIC-GPT

冉谱的 RFIC-GPT，是一款智能生成式设计平台。通过建立针对工艺特性的垂直AI模型和智能体，在秒级时间，生成符合指标和面积的无源网络和“端到端”射频模拟单元电路的原理图和版图，为射频和高速模拟链路芯片设计师提供了快捷高效的便捷利器。它不仅是一款全新的国产智能化AI设计平台，在国际上也处于领先地位。RFIC-GPT 最大特点是协助射频设计者快速收敛，找到最优设计点、大幅度减少迭代次数、简化并加速复杂的设计流程。

### RFIC-CODEX

本项目通过结合RFIC-GPT与Cadence Virtuoso，能根据RFIC-GPT的计算结果将原理图和版图导入Cadence Virtuoso，并根据实际仿真结果自行优化电路设计。在Codex中使用该Skill，用户仅使用自然语言，Codex便能自行完成电路仿真、优化的全流程。该Skill目前仅支持PA原理图的设计，版图级仿真和其它射频电路的设计功能正在开发中。

## 安装和运行 Skill

1. 在powershell中输入命令
   > python "$env:USERPROFILE\.codex\skills\.system\skill-installer\scripts\install-skill-from-github.py" --repo legendsew/rfic_codex_design --path skills/rfic-codex-design --method git
   
   即可安装

2. 在Codex中输入：
   > $rfic-codex-design
   
   即可调用Skill。
   
   首次使用建议发送
   > $rfic-codex-design 检查运行环境。
   
   来配置skill运行所必须的环境。 

## 仓库内容

- [SKILL.md](skills/rfic-codex-design/SKILL.md)：供 Codex 识别任务和选择流程。
- [workflows.md](skills/rfic-codex-design/references/workflows.md)：部署、调用方式、结果验收与排错。
- `assets/rfic_codex_project_web/`：Windows 在线设计客户端及 PA、匹配参数示例。
- `assets/rfic_codex_project/`：Cadence 的 Python/SKILL 接口、部署配置示例与匹配端口符号库。

