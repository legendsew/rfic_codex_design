# Cadence 工作副本函数使用说明

在虚拟机内，通过 run.py 调用 RFIC.py 的函数，编辑 json/deploy.json，并填写 RFIC-GPT_Wizard 的 layertrans.csv。环境部署见 [first_run.md](first_run.md)，电路调整策略见 [optimization.md](optimization.md)。

## 1 填写 deploy.json

通过 SSH 连接虚拟机后，告知用户并征得同意，再扫描虚拟机硬盘以收集所需信息。参考 deploy.example.json 填写。

```json
{
  "virtuoso_dir": "Virtuoso 运行目录，即 .cdsinit 和 cds.lib 所在目录",
  "model_path": "指定工艺库模型文件 toplevel.scs 的路径",
  "setup_file_path": "RFIC-GPT_Wizard 的 layertrans.csv 路径",
  "simulation_path": "Virtuoso 存储 ADE 仿真结果的文件夹",
  "emx_work_addr": "存储 EMX 仿真结果的文件夹",
  "proc_file_addr": "指定工艺库的 proc 文件路径",
  "emx_addr": "EMX 仿真软件路径",
  "tech": "Virtuoso 注册工艺库名，例如 tsmcN65、tsmcN40",
  "mos_name": "PA 所用 NMOS 模型名称，例如 nch_lvt",
  "lib_name": "工作库名，按 rfic_codex_<工艺库名称> 命名，例如 rfic_codex_tsmcN65",
  "project_name": "rfic_codex_project",
  "model_type": "ADE 模型段名称，查阅工艺库文件，例如 tt.lib",
  "show_gui": false,
  "gui_display": ":0"
}
```

配置必须正确，否则函数不能正常工作。

- 首次配置时可暂不填写与工艺库相关的值，其余值必须确定。
- 暂缺字段的配置仅作草稿。将 deploy.example.json 复制为 json/deploy.json 并补齐实际值后，才能导入 RFIC.py；必填字段在导入阶段就会读取。show_gui 未提供时程序默认 false，但 Codex 仍须在设计前确认用户的显示选择，不能用程序默认值代替确认。
- 路径找不到时告知用户。
- 正式仿真前补齐工艺库相关值。
- 用户尚未指定工艺库时，请其确定，并说明需要包含可使用的 proc 文件。
- 多工艺配置可以分别保存，运行时将选定配置复制为 deploy.json。
- 用户在发起设计任务时必须说明是否要看到界面，未说明时开始设计前先确认。show_gui=false 表示使用脚本创建的 Xvfb 虚拟显示，true 表示显示到实际桌面，必须是 JSON 布尔值，不写成字符串。
- 同一电路从生成、EMX、完整 PA 电路验证到所有优化结束，show_gui 必须保持不变；不能通过中途关闭再重开切换模式。仅在开始新的电路设计前重新选择。
- gui_display 是 show_gui=true 时使用的 X 显示，可选，默认优先采用环境 DISPLAY，否则使用 :0；必须具备对应桌面的访问权限。show_gui=false 时自动分配虚拟显示，不使用 gui_display，也不需要外套 xvfb-run。
- 会话自动加载与 emx_addr 同一安装根目录下的 virtuoso_ui/emxinterface/emxskill/emxconfig.il。确认该图形 EMX 接口存在；RFIC.py 和 RFIC.il 必须成套部署。
- 可选 lib_path、symbol_lib、symbol_lib_path 分别指定工作库路径、符号库名及路径。默认工作库为 virtuoso_dir/lib_name；符号库默认 rfic_codex_symbol，优先取项目内同名目录，否则取 virtuoso_dir 下同名目录。

## 2 填写 layertrans.csv

确定工艺库后，读取该工艺库的 .layermap 文件，更新 setup_file_path 指向的 layertrans.csv。

| 物理层 | layermap 中应读取的内容 | CSV 对应字段 |
| --- | --- | --- |
| 最顶层金属，例如 AP | drawing 的 stream number、datatype | M3_drawing_stream、M3_drawing_datatype |
| 次顶层金属，例如 M8 | drawing 的 stream number、datatype | M2_drawing_stream、M2_drawing_datatype |
| 第三顶层金属，例如 M7 | drawing 的 stream number、datatype | M1_drawing_stream、M1_drawing_datatype |
| M2 与 M3 之间的打孔层 | 对应 stream number、datatype | VIA2 的相应字段 |
| M1 与 M2 之间的打孔层 | 对应 stream number、datatype | VIA1 的相应字段 |

在 M1_name、M2_name、M3_name 中填写这三层金属在实际工艺库中的名称。

每个工艺节点使用对应的 layertrans.csv。多个工艺节点分别创建 CSV，使用时将 setup_file_path 指向相应文件。填写后查阅 proc 文件进行核对，layermap 与 proc 冲突时告知用户。

## 3 运行文件与传参格式

在 RFIC.py 同目录创建 run.py，导入 RFIC 并定义调用所需变量。下面保留运行文件头示例，空字符串须在实际调用前填写。

```python
import RFIC

cell_name = ""
transformer_in_name = ""
transformer_out_name = ""
R = ""
L = ""
PA_generation_code = ""
transformer_in_generation_code = ""
transformer_out_generation_code = ""
s4p_path_in = ""
s4p_path_out = ""
```

cell_name 由 Codex 命名。不同设计任务名称不能重复，同一任务进行时保持名称不变。

generate_schematic 的 value 传整数，其余函数参数都以字符串形式传入。电容、电感、电阻字符串保留数量级后缀，去掉物理单位名称。

load_pull_parametric_simulation() 的两个扫描点数是例外，必须传 Python 整数且每轴至少 2 点；load_pull_simulation() 的可选 sweep_pin 传 Python 布尔值。无参数关闭函数无需传入字符串。其余原有参数的字符串格式不变。

| 物理数值 | 传入字符串 |
| --- | --- |
| 10 pF | "10p" |
| 1 nH | "1n" |
| 50 ohm | "50" |
| 1 kohm | "1k" |

p、n、k 属于数量级，必须保留。不传 "10pF"、"1nH" 或 "50ohm"。

仅允许创建或修改 run.py 来组织调用和设置参数，不修改其他程序脚本，也不得通过 run.py 间接改写。JSON 配置和层映射 CSV 按本文件填写。

## 4 函数接口

### 4.1 工作库与符号库

```python
create_lib()
register_symbolLib()
```

- create_lib() 创建绑定工艺库的工作库，绑定关系由 deploy.json 给出。每新增一种工艺库时调用，否则不能正常仿真。
- register_symbolLib() 注册符号库，仅在尚未注册时调用。

### 4.2 导入原理图与版图

```python
generate_schematic(value, generation_code, transformer_name)
```

| value | 导入内容 | generation_code | transformer_name |
| --- | --- | --- | --- |
| 3 | 匹配网络版图 | 版图生成代码 | 版图名称 |
| 4 | 有源原理图 | 原理图生成代码 | 任意字符串，此分支无实际作用 |

该函数使用 Wizard 表单完成导入。整个流程在 deploy.json 选定的同一图形会话中执行：show_gui=false 时不显示到用户桌面，true 时可见。函数返回后保持 Virtuoso 常驻，不自行退出。

### 4.3 EMX 提取

```python
start_emx(transformer_name, Freq_low, Freq_up)
```

transformer_name 指定版图，Freq_low、Freq_up 为 EMX 频率下限和上限。函数返回提取所得 s4p 文件路径。

频率参数只传 GHz 的数字部分字符串，例如 3～150 GHz 传 "3"、"150"，不带 G 或 GHz。范围必须覆盖后续仿真实际使用的频率；当前 HB 配置 maxharms=5，选择范围时检查所需谐波覆盖，避免上限不足而外推。SP 扫描和 HB 谐波的覆盖都需核对，不能只覆盖工作基波。更宽范围不是默认越大越好，应按实际分析要求选择并记录。

每次版图更新后都要调用，包括首次导入版图时。

函数在常驻 Virtuoso 中打开版图和 EMX 表单，提交仿真并等待实际完成；成功后等待约 5 秒再关闭 EMX 及对应版图窗口，Virtuoso 进程继续保留。

### 4.4 复制核心与生成完整 PA 电路测试台

```python
copy_schematic(cell_name)
generate_testbench(cell_name)
```

copy_schematic() 将 Wizard 导入的初始原理图复制到工作库内名为 cell_name 的原理图。

generate_testbench() 在该原理图中生成完整 PA 电路仿真所需输入、输出匹配网络。

### 4.5 完整 PA 电路仿真


```python
start_ADE_simulation(
    cell_name, generation_code, R, L,
    Cp_in, Cs_in, Cp_out, Cs_out,
    s4p_path_in, s4p_path_out
)
```

| 参数 | 含义 |
| --- | --- |
| cell_name | 原理图名称 |
| generation_code | 原理图生成代码 |
| R、L | 为模拟抽头添加的交流隔离电阻、电感，根据工作频率选择合适值 |
| Cp_in、Cs_in | 输入网络初级、次级补偿电容，初始取网站结果，优化后传当前候选值 |
| Cp_out、Cs_out | 输出网络初级、次级补偿电容，初始取网站结果，优化后传当前候选值 |
| s4p_path_in、s4p_path_out | 输入、输出网络 EMX 提取路径，即相应 start_emx() 返回值 |

结果输出到项目的 output/RFIC_<原理图名称>/RFIC_<原理图名称>.txt。

### 4.6 输入阻抗测量


```python
measure_Zin(cell_name)
Zin_ADE_simulation(
    cell_name, generation_code, R, L, ZLoad_real, ZLoad_imag
)
```

measure_Zin() 创建用于测输入阻抗的原理图。

Zin_ADE_simulation() 在当前确定的输出负载阻抗 ZLoad 下测量输入阻抗。ZLoad_real、ZLoad_imag 是负载的实部、虚部，其余参数含义与完整 PA 电路一致。负载的选择见 optimization.md。

结果输出到项目的 output/RFIC_<原理图名称>/RFIC_<原理图名称>_Zin.txt。

### 4.7 负载牵引

```python
load_pull(cell_name)
load_pull_simulation(
    cell_name, generation_code, R, L, pin,
    ZLoad_real, ZLoad_imag, Cp_in, Cs_in, s4p_path_in,
    sweep_pin=False
)
```

load_pull() 创建负载牵引原理图。

| 参数 | 含义 |
| --- | --- |
| ZLoad_real、ZLoad_imag | 当前试探负载的实部、虚部 |
| s4p_path_in | 测得输入阻抗后，在网站重新设计输入匹配网络，再经 EMX 提取得到的 s4p 路径 |
| pin | 负载牵引前完整 PA 电路仿真得到的 1 dB 压缩点输入功率 |
| 其余参数 | 与完整 PA 电路仿真一致 |

默认 sweep_pin=False 时，一次调用只产生一个负载点的数据。改变 ZLoad 并多次调用完成负载牵引，每行包含实部、虚部、Pout、Gain、Iq、Idd、DE 共七列；不包含完整 PA 电路报告中的 S11/S22、Kf/B1f，不能凭该报告单独完成稳定性验收。

结果输出到项目的 output/RFIC_<原理图名称>/RFIC_<原理图名称>_load_pull.txt。写模式为追加，多次调用不会覆盖已有负载牵引结果。

sweep_pin=False 为固定 Pin 的普通负载牵引，返回报告路径，并保留 ADE 以供后续调用；常规 load-pull 必须使用该模式。sweep_pin=True 是在固定负载下单独扫描 Pin 的诊断模式，不是负载实部/虚部扫描，不能误用于代替固定压缩点 Pin 的 load-pull。该模式固定 -30～30 dBm、步长 2 dB，输出 RFIC_<原理图名称>_load_pull_pin.txt，完成后关闭本次 ADE 窗口，返回报告路径。

### 4.8 二维负载参数扫描

```python
load_pull_parametric_simulation(
    cell_name, generation_code, R, L, pin,
    ZLoad_real_min, ZLoad_real_max, ZLoad_real_points,
    ZLoad_imag_min, ZLoad_imag_max, ZLoad_imag_points,
    Cp_in, Cs_in, s4p_path_in
)
```

先调用 load_pull(cell_name) 建立测试台，再调用本函数。pin 固定为该候选完整 PA 电路测得的 1 dB 压缩点输入功率；不扫描 Pin。实部、虚部采用 ADE Parametric Analysis 嵌套等间隔扫描，共 real_points×imag_points 点。

| 参数 | 要求 |
| --- | --- |
| ZLoad_real_min、ZLoad_real_max | 有限数值，0 < min < max |
| ZLoad_imag_min、ZLoad_imag_max | 有限数值，min < max，允许负值 |
| ZLoad_real_points、ZLoad_imag_points | Python 整数，每轴至少 2 点，不传字符串或布尔值 |
| pin | 有限数值，沿用固定输入功率 |
| 其余参数 | 与单点 load_pull_simulation() 一致 |

粗扫和细扫分别改变两轴范围与点数调用，不修改底层脚本。总点数超过 100 时可能出现确认窗口，脚本自动确认。结果覆盖写入 output/RFIC_<原理图名称>/RFIC_<原理图名称>_load_pull_sweep.txt，返回路径；每行是实部、虚部、Pout、Gain、Iq、Idd、DE，共七列。新扫描前保存上一批结果；完成后关闭本次 ADE 和原理图窗口，不关闭常驻 Virtuoso。

### 4.9 统一关闭会话

```python
close_virtuoso()
```

在本次设计任务结束或确定终止时调用，等待本工程常驻 Virtuoso 实际退出，并停止本脚本创建的 Xvfb；可视化模式不会关闭实际桌面的显示服务。不得在同一电路的每轮函数调用后反复关闭重启。

## 5 调用顺序

| 任务或触发条件 | 顺序 |
| --- | --- |
| 初次运行、尚未注册符号库 | register_symbolLib() |
| 更换为之前未使用过的工艺库 | create_lib() |
| 导入原理图或版图 | generate_schematic() |
| 版图首次导入或更新 | start_emx()，取得新的 s4p |
| 生成完整原理图 | copy_schematic() |
| 完整 PA 电路仿真 | generate_testbench() → start_ADE_simulation() |
| 测输入阻抗 | measure_Zin() → Zin_ADE_simulation() |
| 负载牵引 | load_pull() → 多次 load_pull_simulation() |
| 二维负载粗扫或细扫 | load_pull() → load_pull_parametric_simulation() |
| 本次设计完成或终止 | close_virtuoso() |

## 6 仿真数据与执行限制

先做匹配版图 EMX，再构建完整 PA 电路。读取 output 对应文件夹中的原始数据，计算电路指标，报告给用户并判断是否达标。

若 EMX 提示 label 不靠近边缘，允许通过 run.py 组织所需操作，调整边缘以解决报错。不得改变版图拓扑结构。

要求覆盖频带时，改变传给函数的原理图生成代码中的工作频率，调用函数检查不同频率下的性能，具体字段见 optimization.md。

当前函数不提供输入功率扫描点或步长参数。使用现有扫描数据分析压缩点，不能修改其他脚本或生成的 OCEAN 脚本来加密采样。已有结果不足以确定指标时，说明精度或覆盖限制。

完整 PA 电路仿真使用 ADE Parametric Analysis，固定 Pin=-30～30 dBm、步长 2 dB，共 31 点。完整 PA 电路文本报告为 Pin、Pout、Gain、Iq、Idd、DE、S11、S22、Kf、B1f 十列。Kf/B1f 及 S11/S22 也作为 ADE outputs 提供。单次 Zin 和普通 load-pull 使用单点 ADE，不自动扫描 Pin。

## 7 测试台状态、结果覆盖与失败恢复

- measure_Zin() 和 load_pull() 会修改指定 cell 的测试台，不是只读取完整 PA 电路。返回完整 PA 电路验证前，通过 copy_schematic(cell_name) 恢复核心，再用 generate_testbench(cell_name) 构建完整 PA 电路，不能在 Zin 或 load-pull 测试台上直接调用完整 PA 电路仿真并将其当成完整电路结果。
- start_ADE_simulation() 和 Zin_ADE_simulation() 会重新写入各自报告；再次调用前保存需要保留的有效原始数据及完整参数关联。
- load_pull() 建立测试台时会初始化报告，已有同名报告可能被清空。每批负载点扫描只在建立测试台时调用，不为每个点重复调用；新批次开始前保存旧批次。
- load_pull_simulation() 追加单个负载点。续跑前核对已完成点所属的生成代码、频率、固定 Pin、电容和输入 S4P 版本；仅补失败或未完成点，防止重复追加或混合不同批次。
- start_emx() 成功时返回 S4P 路径，失败或超时抛出异常；同一路径可能残留旧 S4P。检查状态、文件是否由本次更新、是否可读取，以及频率范围和端口是否符合要求，不能只检查路径存在。
- 返回约定：create_lib()、register_symbolLib()、generate_schematic()、copy_schematic()、generate_testbench()、measure_Zin()、load_pull() 成功返回 0；start_ADE_simulation()、Zin_ADE_simulation() 和 close_virtuoso() 成功返回 None；start_emx() 和两种 load-pull 仿真函数成功返回结果路径。失败以异常报告，不能对所有函数统一用返回值等于 0 判断成功。打印完成也不替代结果验证：检查报告更新、有效行列、数值完整性及是否对应本次参数。
- 在 run.py 中对确认失败的仿真作有限次数重试，只补失败点，不重跑有效点。连续失败后检查进程、日志、测试台及依赖，不无限重试。网站仍一次只提交一个任务，未确认原任务状态时不能重复提交。
- 重试前确认前一仿真已结束，避免同一 cell、报告或共享生成脚本被并发覆盖。中断产生的部分报告不能当成完整有效结果。

## 8 匹配指标的读取口径

读取 S11/S22 时先确认表达式、单位和频率范围。ymax(mag(spm('sp 1 1))) 和 ymax(mag(spm('sp 2 2))) 给出相应 SP 扫描范围内的最大线性幅度，不是直接以 dB 给出的工作频带内匹配值。

幅度 dB 使用 20×log10(|Sij|)，不是 10×log10(|Sij|)；-10 dB 对应幅度约 0.316。全 SP 扫描范围最大值不能冒充用户工作频带内最大值。确认实际 SP 频点覆盖及采样密度，插值得到带内值不代表增加了原始 SP 仿真点。

完整 PA 电路报告中的 Kf、B1f 是 ymin 表达式得到的最小值，当前 SP 范围固定为 1～80 GHz；不能将它们描述成仅工作频带内的最小值。S11/S22、Kf/B1f 文本值按两位小数写出，接近 Kf=1 或 B1f=0 等严格阈值时可能无法据此判定，需使用可得原始结果复核或说明精度不足，不能把四舍五入后的边界值当作严格通过。

按现有函数和可用原始数据读取所需频率或频带的结果，不为额外扫描修改受限的底层或生成脚本；数据不足时说明限制。S11/S22 是匹配诊断依据，不能单独决定改尺寸还是改网络；结合性能变化与有源参数—匹配闭环判断，见 optimization.md。

## 9 常驻会话与窗口管理

首次业务调用自动启动 Virtuoso，加载 RFIC.il 并开始命令轮询；后续函数通过同一会话执行，Python 等待命令完成而不是等待进程退出。同一工作副本只串行提交任务，不同时运行多个 run.py，也不手工覆盖 pcell 下的会话状态文件。

create_lib()、register_symbolLib() 及原理图、ADE 等通过 _submit_skill() 的调用会自动启动会话。start_emx() 也通过此机制提交，但显示依赖的 EMX 接口必须已经正确安装。以下内部扫描机制用于理解接口，不要求 run.py 直接调用私有函数：

| 对外调用 | 内部执行 | 扫描或分析 |
| --- | --- | --- |
| start_ADE_simulation() | _run_ade_parametric() | 固定 31 点 Pin 扫描 |
| load_pull_parametric_simulation() | _run_ade_parametric() | 固定 Pin 的二维负载网格 |
| load_pull_simulation(sweep_pin=True) | _run_ade_parametric() | 固定负载的 Pin 诊断扫描 |
| load_pull_simulation(sweep_pin=False) | _run_ocean_visible() | 固定 Pin、固定负载的单次仿真 |
| Zin_ADE_simulation() | _run_ocean_visible() | 单次 Zin 测量，内部执行配置的 SP 频率分析 |

_run_ade_parametric() 的名字不表示已提供任意参数的通用对外扫描接口：配置准备、结果提取和报告校验包含 Pin 或负载扫描的专用逻辑。当前电容、尺寸和偏置优化通过 run.py 分次改变一个参数、重复调用现有业务函数实现；每个完整 PA 电路候选的内部 Pin 扫描仍使用 ADE Parametric Analysis。不能自行传入任意扫描轴并假定受支持，也不能在固定一个 Pin 扫电容后就声称取得每组电容的 OP1dB。

start_ADE_simulation() 在 ADE 中执行 Pin 参数扫描，Zin_ADE_simulation() 执行单点分析。两者成功后保留结果窗口约 5 秒，再关闭本次 ADE、图形和原理图，Virtuoso 本身不退出。普通 load_pull_simulation() 保留 ADE，二维 load_pull_parametric_simulation() 或 sweep_pin=True 的诊断完成后关闭本次窗口。内部 _run_ocean_visible()、_run_ade_parametric()、_close_ade_windows() 无需由 run.py 替代业务函数直接调用。

完整设计结束或确定终止时才调用 close_virtuoso()。若 run.py 包含完整任务，可将最终关闭放入 finally；若任务分多次 run.py 执行，中间步骤不要统一关会话，最后一步或中止处理再关闭。例如：

```python
import RFIC

try:
    RFIC.create_lib()
    RFIC.register_symbolLib()
    # 在这里按前述接口执行本次完整设计、仿真及优化。
finally:
    RFIC.close_virtuoso()
```

发生错误时记录日志、异常及有效数据。虚拟模式下“窗口保留供检查”也仍在虚拟显示里，不代表会显示到实际桌面；不得因此在同一设计内修改 show_gui。需要结束任务时统一关闭，不能只杀掉显示服务而让仿真或数据库写入继续运行。close_virtuoso() 超时或报错时，先检查本工程进程及保存/确认状态，不宣称已关闭，也不批量关闭其他用户进程。

