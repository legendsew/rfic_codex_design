# RFIC CODEX Design

用 Codex 串联 RFIC-GPT 的 PA 候选设计与 Cadence 仿真：从自然语言指标出发，获取有源核心和匹配网络的生成代码，在 Virtuoso 中生成电路与版图，用 EMX 和 Spectre 验证整机，再按仿真结果迭代。网站指标用于筛选候选，最终结论以本地仿真为准。

## 安装 Skill

1. 克隆或下载本仓库。
2. 将整个 `skills/rfic-codex-design/` 复制到工作项目的 `.agents/skills/` 下，保留 `references/` 和 `assets/`。
3. 在该项目中打开 Codex，输入：
   > $rfic-codex-design 先检查环境并准备设计参数，不提交任务。示例规格：65 nm、中心 24 GHz、验收频带 23–25 GHz，增益 >18 dB、OP1dB >16 dBm、DE_P1dB >25%，并检查稳定性。

只做在线候选设计可以不部署 Cadence；已有生成代码时也可以跳过在线步骤。安装 Skill 不会自动安装厂商软件、配置 SSH 或提交网站任务。手动使用时，同样从 [运行说明](skills/rfic-codex-design/references/workflows.md) 开始。

## 运行环境

| 部分 | 需要准备 |
| --- | --- |
| 在线设计 | Windows、Python 3、`requirements.txt` 中的依赖、可用的 ICProphet 账户和积分 |
| 本地仿真 | Linux 工作站或虚拟机、Python 3、Virtuoso、Spectre/OCEAN、EMX、对应许可和 PDK、RFIC-GPT_Wizard 与 CSPA 模板；导入 Wizard 时需要图形会话 |

首次运行时，分别检查 Windows 主机和 Linux 虚拟机上的 Python 与依赖；缺少依赖时，在各自工作环境中使用对应项目的 `requirements.txt` 安装。Cadence 工作副本要放在实际启动 Virtuoso 的工作目录下（即本工程使用的 `.cdsinit` 与 `cds.lib` 所在目录），并通过 `register_symbolLib()` 注册随附的端口符号库。

发布包中的 Wizard 用图形会话，EMX 和电路仿真由命令行启动。发布包不包含此前演示用的单会话 GUI 驱动或原生 ADE 二维扫描。不要把示例路径、工艺名或指标当成通用默认值。

## 仓库内容

- [SKILL.md](skills/rfic-codex-design/SKILL.md)：供 Codex 识别任务和选择流程。
- [workflows.md](skills/rfic-codex-design/references/workflows.md)：部署、调用方式、结果验收与排错。
- `assets/rfic_codex_project_web/`：Windows 在线设计客户端及 PA、匹配参数示例。
- `assets/rfic_codex_project/`：Cadence 的 Python/SKILL 接口、部署配置示例与匹配端口符号库。

