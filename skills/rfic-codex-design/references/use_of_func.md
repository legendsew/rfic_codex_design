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
  "model_type": "ADE 模型段名称，查阅工艺库文件，例如 tt.lib"
}
```

配置必须正确，否则函数不能正常工作。

- 首次配置时可暂不填写与工艺库相关的值，其余值必须确定。
- 路径找不到时告知用户。
- 正式仿真前补齐工艺库相关值。
- 用户尚未指定工艺库时，请其确定，并说明需要包含可使用的 proc 文件。
- 多工艺配置可以分别保存，运行时将选定配置复制为 deploy.json。

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

该函数是本流程中唯一依赖图形界面的函数，使用 Wizard 表单完成导入。调用时使用虚拟桌面，不展示在用户实际的虚拟机桌面上。

### 4.3 EMX 提取

```python
start_emx(transformer_name, Freq_low, Freq_up)
```

transformer_name 指定版图，Freq_low、Freq_up 为 EMX 频率下限和上限。函数返回提取所得 s4p 文件路径。

每次版图更新后都要调用，包括首次导入版图时。

### 4.4 复制核心与生成整机测试台

```python
copy_schematic(cell_name)
generate_testbench(cell_name)
```

copy_schematic() 将 Wizard 导入的初始原理图复制到工作库内名为 cell_name 的原理图。

generate_testbench() 在该原理图中生成整机仿真所需输入、输出匹配网络。

### 4.5 整机仿真

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
| Cp_in、Cs_in | 输入网络初级、次级补偿电容，取网站结果 |
| Cp_out、Cs_out | 输出网络初级、次级补偿电容，取网站结果 |
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

Zin_ADE_simulation() 在当前确定的输出负载阻抗 ZLoad 下测量输入阻抗。ZLoad_real、ZLoad_imag 是负载的实部、虚部，其余参数含义与整机一致。负载的选择见 optimization.md。

结果输出到项目的 output/RFIC_<原理图名称>/RFIC_<原理图名称>_Zin.txt。

### 4.7 负载牵引

```python
load_pull(cell_name)
load_pull_simulation(
    cell_name, generation_code, R, L, pin,
    ZLoad_real, ZLoad_imag, Cp_in, Cs_in, s4p_path_in
)
```

load_pull() 创建负载牵引原理图。

| 参数 | 含义 |
| --- | --- |
| ZLoad_real、ZLoad_imag | 当前试探负载的实部、虚部 |
| s4p_path_in | 测得输入阻抗后，在网站重新设计输入匹配网络，再经 EMX 提取得到的 s4p 路径 |
| pin | 负载牵引前整机仿真得到的 1 dB 压缩点输入功率 |
| 其余参数 | 与整机仿真一致 |

一次调用只产生一个负载点的数据。改变 ZLoad 并多次调用完成负载牵引，输出指标与整机一致。

结果输出到项目的 output/RFIC_<原理图名称>/RFIC_<原理图名称>_load_pull.txt。写模式为追加，多次调用不会覆盖已有负载牵引结果。

## 5 调用顺序

| 任务或触发条件 | 顺序 |
| --- | --- |
| 初次运行、尚未注册符号库 | register_symbolLib() |
| 更换为之前未使用过的工艺库 | create_lib() |
| 导入原理图或版图 | generate_schematic() |
| 版图首次导入或更新 | start_emx()，取得新的 s4p |
| 生成完整原理图 | copy_schematic() |
| 整机仿真 | generate_testbench() → start_ADE_simulation() |
| 测输入阻抗 | measure_Zin() → Zin_ADE_simulation() |
| 负载牵引 | load_pull() → 多次 load_pull_simulation() |

## 6 仿真数据与执行限制

先做匹配版图 EMX，再构建整机。读取 output 对应文件夹中的原始数据，计算电路指标，报告给用户并判断是否达标。

若 EMX 提示 label 不靠近边缘，允许通过 run.py 组织所需操作，调整边缘以解决报错。不得改变版图拓扑结构。

要求覆盖频带时，改变传给函数的原理图生成代码中的工作频率，调用函数检查不同频率下的性能，具体字段见 optimization.md。

当前函数不提供输入功率扫描点或步长参数。使用现有扫描数据分析压缩点，不能修改其他脚本或生成的 OCEAN 脚本来加密采样。已有结果不足以确定指标时，说明精度或覆盖限制。

