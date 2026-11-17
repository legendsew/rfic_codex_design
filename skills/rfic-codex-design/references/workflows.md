# RFIC 工作流

## 0. 首次运行检查

由 Codex 分别在实际运行任务的 Windows 主机和 Linux 虚拟机上检查 `python --version`（Linux 也可用 `python3`）、`python -m pip --version`，并验证所需包能被同一个解释器导入。主机检查 `requests`；虚拟机的 `RFIC.py` 本身只用标准库，读取数据或绘图时检查 `numpy`、`matplotlib`。缺包时，在对应项目目录运行 `python -m pip install -r requirements.txt`，安装后复查导入与 `python -m pip check`。优先使用可写的虚拟环境，避免改动系统 Python；安装前确认网络和权限。不要通过直接导入带登录或文件写入副作用的项目模块来检查环境。

## 1. 在线候选设计（Windows）

将 `assets/rfic_codex_project_web` 复制到工作目录。在该目录安装依赖：`python -m pip install -r requirements.txt`。复制 `json/param.pa.example.json` 或 `json/param.matchingcircuit.example.json` 为 `json/param.json`。按 `rfic_web_run.py` 的校验及模板填写键和值；不要同时配置两种任务。授权后，在项目根目录的交互式终端运行 `python rfic_web_run.py`，由用户本地输入凭据。导入客户端也可能触发认证，不要用 import 试探配置。

- **PA**：`Frequency` 填中心频率（GHz），例如 24，而不是 23–25。效率权重 `DE_P1dB_w` 不等于效率硬约束。查看网站返回的候选及其估算条件，再确认是否接收。读取 `json/pa_opt.json` 中的指标和 `A/…` 有源生成代码。
- **MatchingCircuit**：`freq_value` 填中心频率，`freq_scope` 是独立参数。输入匹配选 `SINGLE_DIFF`，输出匹配选 `DIFF_SINGLE`。按网络参考面核对 `Z_L` 与 `Z_opt`：输入端处理外部单端参考阻抗与 PA 的差分输入，输出端把外部 50 Ω 负载变换为 PA 所需的差分最佳负载。明确阻抗是实测值、共轭值还是负载牵引目标，不要把网站的 `Zin,conj` 再取一次共轭，也不要把最佳负载当作 PA 本身的输出阻抗。保留每轮 Smith/IL 图（`png/`）、归档（`gds/`）、生成代码和 Cp/Cs，避免配错轮次。
- 客户端按任务 ID 轮询，并可能交互确认是否采纳。超时先核对原任务是否已提交、是否仍在算，再决定是否重试；避免重复扣积分。令牌和账号 ID 缓存（`json/token.json`、`json/usrid.json`）只留本地。协议里的 MD5 摘要不等同于加密，也不应公开。

## 2. 部署 Cadence 工作副本

1. 在 Linux 工作站或虚拟机上先找到此工程实际启动 Virtuoso 的工作目录，即加载项目插件的 `.cdsinit` 和配套 `cds.lib` 所在目录；这不是 Cadence 的软件安装目录。将 `assets/rfic_codex_project` 整个复制为该目录的直接子目录。例如启动目录为 `/home/example`，则项目应在 `/home/example/rfic_codex_project`，`virtuoso_dir` 写父目录、`project_name` 写子目录名。若用 SSH，只连接用户授权的主机。保留 `rfic_codex_symbol/` 的 OA 目录和隐藏文件。
2. 复制 `json/deploy.example.json` 为 `json/deploy.json`。该文件从模块所在项目读取，但脚本生成的运行路径使用 `<virtuoso_dir>/<project_name>/`，两者须指向同一工作副本。因部分命令通过 shell 构建且未对每个路径加引号，优先使用不含空格或 shell 特殊字符的运行目录；需使用特殊路径时先核查对应调用。
3. 核对 `virtuoso_dir` 中的 `cds.lib` 和初始化设置；确认 `tech`、`mos_name`、`model_path` 和 `model_type` 对应实际 PDK 与有效模型段。`lib_name` 是独立设计库，不是 PDK 本体。检查 `setup_file_path` 对应的 Wizard 层映射，以及 `emx_addr`、`emx_work_addr` 和 `proc_file_addr`。示例不是可直接使用的通用环境。
4. 在已加载 Cadence 环境的终端验证 `virtuoso`、`strmout`、`ocean` 和 EMX 可用。Wizard 依赖当前表单，需要可用图形会话；SSH 无 DISPLAY 时应先确认使用桌面还是虚拟显示，虚拟显示不出现在用户桌面。发布版不要求手工预载 `pcell/run.il`：Python 会为不同步骤重写它。不要并发共享同一工作副本；`run.il`、`ocean/RFIC.ocn` 和某些中间结果会被重写。

## 3. 生成、提取和整机仿真

在工作副本的 `python/` 下调用已有 `RFIC.py` 函数。发布包未附固定的 `RFIC_run.py`。按下面顺序组织调用，先用独立测试名验证环境：

1. 调用 `create_lib()` 创建绑定到目标 PDK 的设计库；随后必须调用 `register_symbolLib()`，在 Virtuoso 中注册随包的 `rfic_codex_symbol` 库。确认该名字解析到本次使用的 OA 库，且能打开 `inport_symbol` 和 `outport_symbol`。若同名库已注册，函数不会重绑，先核对现有映射，再放置匹配端口。
2. `generate_schematic(4, pa_code, cell_name)`、`copy_schematic(cell_name)`：通过 Wizard 更新 CSPA 模板后把有源电路复制到设计库。将共享模板视为会被修改的中间资产。
3. 对输入、输出分别调用 `generate_schematic(3, net_code, net_name)` 和 `start_emx(net_name, f_low, f_high)`。频率传数字 GHz，例如 `3, 150`；上限和下限按实际 HB 谐波与仿真覆盖确定。若使用五次谐波，验证 23–25 GHz 时上限至少覆盖 125 GHz。检查 GDS、日志和本轮新生成的 `.s4p`，确认频率及端口顺序 `pri_p, pri_m, sec_p, sec_m`。若 EMX 报标签不靠近边缘或未找到，检查标签层/用途和导出 GDS，把对应标签移至实际端部边缘后重跑，不改金属拓扑来掩盖错误。
4. `generate_testbench(cell_name)` 安装输入、输出模型；调用 `start_ADL_simulation(cell_name, pa_code, R, L, Cp_in, Cs_in, Cp_out, Cs_out, s4p_in, s4p_out)`。传给 OCEAN 的量用 Spectre 可读字符串，例如 `"2k"`、`"500p"`、`"41.91f"`；S 参数路径用 Cadence 可读的 Linux 绝对路径。确认电容与同一版图结果对应，不把回退模型与新版本电容混用。抽头 R/L 是仿真假设，不是与频率、偏置无关的固定设计值。

## 4. 结果与优化

整机报告通常位于 `output/RFIC_<cell>/RFIC_<cell>.txt`。验证有本轮的数值行，导出或绘图时将 Pin 作为横坐标。发布版的 HB Pin 点表不是均匀扫描；若压缩点两侧采样太疏，局部加密后再报数值。

- Gain = Pout − Pin，单位 dB。先从线性区确定小信号增益，再找增益下降 1 dB 的交点。交点的输入是 IP1dB，输出是 OP1dB；在同一点插值 DE。漏极效率用 `100 × Pout(W) / (Vdd × Idd_DC)`，Idd_DC 是 HB 零次谐波电流，不是基波，也不等于独立 DC 分析的 Iq。
- S11/S22 是输入/输出小信号反射；报告记录 `ymax(mag(spm(...)))` 的线性幅值，不是 dB。SP 全扫范围的最大值不能当成工作带内最差值；带内验收应从带内波形取极值，并按需要用 `20 log10(|S|)` 换算。PA 大信号最佳负载仍用 HB / load-pull 判断。
- Kf 和 B1f 检查频率范围内满足 `Kf > 1`、`B1f > 0`；临近阈值时检查未四舍五入的数据及更密频点。将中心点达标和频带采样点达标分开报告，不把离散点当作连续频带保证。

先在同条件下扫 Cp/Cs。必要时复制有源电路至独立测试单元，用 `measure_Zin`、`Zin_ADL_simulation` 测输入阻抗；沿用报告中的差模/半电路归一约定，换参考面时再换算。更新输入网络后，用 `load_pull(cell)` 准备理想负载测试台，用 `load_pull_simulation(...)` 对每组 `ZLoad_real, ZLoad_imag` 求值。先在参考理想负载下找 IP1dB，之后粗扫与细扫负载时固定该 Pin，不把这个 Pin 下的 Pout 直接叫作每组负载的新 OP1dB。发布版入口一次只跑一组负载；外层串行调用并核对网格完整，初始化函数只在该批开始调用一次。回代候选负载重测 Zin，收敛后再设计输出网络，并重新验证实际网络下的整机指标。

### 根据反射结果选择优化方向

1. **先判匹配。** 在规格频带内比较 S11、S22 与目标：S11 不达标优先查输入匹配；S22 不达标优先查输出匹配，并结合负载牵引区分小信号反射与大信号最佳负载。两端都不达标时分别建立基线并一次调整一端，再做整机复验。不要用带外反射决定要不要改管，也不要把良好的 S22 当作大信号负载已最优的证据。
2. **再调放大管。** 若带内匹配尚可、负载核对后增益或 OP1dB 仍不达标，先固定其余可控条件，改变放大管的 `Mul`、`NoF`，寻找满足增益、OP1dB、效率等性能约束的候选。记录每组稳定性；不稳定候选只供下一步调中和，不作为最终结果。
3. **最后调中和管。** 对性能合格但稳定性不足的候选，固定放大管尺寸，调整中和管的 `Mul2`、`NoF2`，检查规定频率范围内 Kf > 1、B1f > 0。中和也会改变增益和阻抗，所以每轮重新检查性能；若无法兼顾，退回其他放大管候选。最终重测 Zin 和最佳负载，必要时重做匹配，接回实际输入、输出网络复验带内指标。保留基线、参数和每轮结果。

