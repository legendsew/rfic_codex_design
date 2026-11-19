# 首次运行检查

首次在电脑上使用本技能，或用户要求配置环境时，按本文件执行。完成基础部署后，再按 [use_of_func.md](use_of_func.md) 配置具体工艺与函数调用。

## 1 检查主机和虚拟机的 Python

分别在实际运行任务的 Windows 主机与 Linux 虚拟机上检查解释器和 pip。

```text
python --version
python -m pip --version
```

Linux 也可使用 python3，但安装包和执行脚本必须使用同一个解释器。

- 主机检查 requests 能被实际解释器导入。
- 虚拟机的 RFIC.py 本身只使用标准库。读取数据或绘图时检查 numpy、matplotlib。
- 缺包时，在对应项目目录运行 python -m pip install -r requirements.txt，安装后复查导入及 python -m pip check。
- 优先使用可写的虚拟环境，避免改动系统 Python。安装前确认网络和权限。
- 不通过直接导入带登录或文件写入副作用的项目模块来检查环境。

## 2 连接虚拟机

提醒用户打开虚拟机，辅助完成虚拟机密钥配置和 SSH 设置，再通过 SSH 连接虚拟机。与虚拟机有关的环境检查在连接后执行。

## 3 部署 Cadence 工作副本

找到该工程实际启动 Virtuoso 的工作目录，即 .cdsinit 与 cds.lib 所在目录。将 assets/rfic_codex_project 整个复制为该目录的直接子目录。

例如启动目录是 /home/example，则部署位置为 /home/example/rfic_codex_project。

- virtuoso_dir 填 /home/example。
- project_name 填 rfic_codex_project。

部署配置参照随附的 deploy.example.json。主机与虚拟机使用各自的工作副本。

## 4 安装 RFIC-GPT_Wizard

检查虚拟机是否已经安装 Wizard。未安装时使用 rfic_codex_project 目录内随附的 RFIC-GPT_Wizard_v1.251126_CN.zip。

1. 在 Linux 系统内将安装包解压到当前目录，不在 Windows 中解压，避免解压错误。
2. 进入解压得到的 RFIC-GPT Wizard 文件夹，运行 install.sh。
3. 按提示先后输入虚拟机 cds.lib 与 .cdsinit 的文件路径。
4. 最后一步选择 y，完成安装。

## 5 收集并填写配置

扫描虚拟机文件夹以寻找 deploy.json 所需路径前，告知用户并征得同意。具体字段和 layertrans.csv 的填写方法见 [use_of_func.md](use_of_func.md)。

核对以下内容。

- virtuoso_dir 中的 cds.lib 与初始化设置。
- tech、mos_name、model_path、model_type 与实际 PDK、模型文件和有效模型段一致。
- lib_name 是独立设计工作库。
- setup_file_path 指向正确的 Wizard 层映射。
- emx_addr、emx_work_addr、proc_file_addr 对应该环境的工具、工作目录和工艺文件。
- 示例配置中的路径需按实际环境填写。

初次配置时，用户尚未指定工艺库，可以暂不填写相关字段。其余路径必须确定，找不到的路径告知用户。正式仿真前补齐工艺相关字段。

多个工艺库可分别保存配置，例如 deploy.tsmcN65.json。执行相应工艺任务前，将选定配置复制为 deploy.json。

## 6 检查 Cadence 和图形会话

在已加载 Cadence 环境的终端验证 virtuoso、strmout、ocean 和 EMX 可用。

Wizard 依赖当前表单，需要可用图形会话。SSH 没有 DISPLAY 时，先确认桌面或虚拟显示方案。按本技能要求在虚拟桌面上运行，不在用户实际桌面展示导入操作。

只通过已有配置和 run.py 调用适配环境。若部署路径与脚本要求不兼容，报告具体问题，不修改其他程序脚本。

## 7 注册符号库

检查 Virtuoso 中是否注册 rfic_codex_symbol。尚未注册时调用 RFIC.py 的 register_symbolLib()。

该库定义了电路仿真需要的 symbol，未注册会导致原理图无法正确绘制。新增工艺工作库的创建方法见 use_of_func.md。

## 脚本修改边界

仅创建或修改 run.py 来调用现有函数。param.json、deploy.json 和 layertrans.csv 按任务填写。不得修改其他程序脚本。

