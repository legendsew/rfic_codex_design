import rfic_certify as certi
import rfic_web_func as func
from pathlib import Path
import json
import os

os.chdir(os.path.dirname(os.path.abspath(__file__)))

PARAM_FILE = Path(".\\json\\param.json")

def load_design_param():

    with PARAM_FILE.open("r", encoding="utf-8") as f:
        data = json.load(f)

    task = data["task"]
    params = data["params"]

    if not isinstance(params, dict):
        raise ValueError("params 必须是 JSON 对象")

    return task, params

REQUIRED_PARAMS = {
    "PA": [
        "Tech", "Vdda", "Frequency",
        "Gain_low", "Gain_up", "OP1dB_low",
        "DE_P1dB_w", "Iq_w", "NFmin_w", "V_over"
    ],

    "MatchingCircuit": [
        "freq_value", "freq_scope",
        "Z_L_real", "Z_L_imag",
        "Z_opt_real", "Z_opt_imag",
        "S11", "IL", "tech",
        "layer_p_thickness",
        "layer_s_thickness",
        "input_type"
    ]
}

def validate_params(task, params):

    if task not in REQUIRED_PARAMS:
        raise ValueError(f"未知任务类型: {task}")

    missing = [
        key for key in REQUIRED_PARAMS[task]
        if key not in params
    ]

    if missing:
        raise ValueError(f"缺少必要参数: {missing}")

def main():
    # 获取设计任务
    task, params = load_design_param()

    validate_params(task,params)

    # 获取 Session
    session = certi.session
    #查询余额
    balance = func.get_balance(session)
    if balance < 100 :
        print("余额不足")
        return 1

    # 根据任务类型调用函数
    if task == "PA":

        print("开始执行 PA 设计...")

        result = func.PA_design(
            session,
            **params
        )

    elif task == "MatchingCircuit":

        print("开始执行匹配网络设计...")

        result = func.MatchingCircuit_design(
            session,
            **params
        )

    else:
        raise ValueError(f"不支持的设计任务: {task}")

    if result == 0:
        print("设计任务执行成功！")

    elif result is None:
        print("设计任务已取消。")

    else:
        print(f"设计任务返回: {result}")


if __name__ == "__main__":
    main()