import json
import time
from pathlib import Path
import os

os.chdir(os.path.dirname(os.path.abspath(__file__)))
USRID_FILE = Path(".\\json\\usrid.json")
PA_OPT_FILE = Path(".\\json\\pa_opt.json")
PNG_DIR = Path(".\\png")
PNG_DIR.mkdir(parents=True, exist_ok=True)
GDS_DIR = Path(".\\gds")
GDS_DIR.mkdir(parents=True,exist_ok=True)


with USRID_FILE.open("r", encoding="utf-8") as f:
    data = json.load(f)
    usrid = data["usrid"]

# 依据工艺和电源电压决定attribute id
PA_ATTRIBUTE_ID = {
    "65nm": {
        "1.1": "local_mYUJc1g4MXi62ol2_ki5T",
        "1.2": "local_0HuEWYVN7aWumkwL8ghCT",
        "1.3": "local_zwaiM9eNxOw861nIU-4BA",
    },

    "40nm": {
        "1.0": "local_aW-no1y6oPFOuWmQ7hiQd",
        "1.1": "local_RsV8QKR8Fl7W9uQUgvTxd",
        "1.2": "local_XM4AcuFznK8aPrsfmJYx0",
    },

    "28nm": {
        "0.9": "local_jGqj3d-wIlx3eUQAauQsy",
        "1.0": "local_s9dF2H4QOYNnpdGf5z9c3",
        "1.1": "local_k-RpLqYmMV86VRMP4eSyn",
    }
}

def get_balance(session):
    response = session.post(
        "https://service.icprophet.com/icprophet/user/info",
        json = {"user_id": ""},
        timeout = 30
        )
    response.raise_for_status()
    data = response.json()
    balance = data["result"]["balance"]
    return balance

def PA_design(
    session,
    Tech,
    Vdda,
    Frequency,
    Gain_low,
    Gain_up,
    OP1dB_low,
    DE_P1dB_w,
    Iq_w,
    NFmin_w,
    V_over
):
    try:
        service_attribute_id = PA_ATTRIBUTE_ID[Tech][str(Vdda)]
    except KeyError:
        raise ValueError("不支持的参数组合")
    service_param = {
        "PA": "CSPA",
        "Tech": Tech,
        "Vdda": str(Vdda),
        "Frequency": Frequency,
        "Gain_low": Gain_low,
        "Gain_up": Gain_up,
        "OP1dB_low": OP1dB_low,
        "DE_P1dB_w": DE_P1dB_w,
        "Iq_w": Iq_w,
        "NFmin_w": NFmin_w,
        "V_over": str(V_over),
        "AMAM": "",
        "AMPM": "",
        "ILin": "",
        "ILout": ""
    }

    payload = {
        "service_id":
            "a47a0c4ae89e427eb7d7b9643e96ab97",

        "service_attribute_id":
            service_attribute_id,

        "order_type":
            "design",

        "service_type":
            "DataSearch",

        "service_param":
            json.dumps(service_param, ensure_ascii=False),

        "user_id":
            usrid
    }

# 提交设计
    response = session.post(
        "https://service.icprophet.com/icprophet/order/add",
        json=payload,
        timeout=60
    )

    response.raise_for_status()

    result = response.json()

    if result.get("code") != 0:
        raise RuntimeError(
            f"PA设计提交失败: {result.get('message')}"
        )

    order_id = result.get("result")

    if not order_id:
        raise RuntimeError("没有获取到 order_id")
# 等待设计结果
    PA_data = None
    last_message = ""

    for attempt in range(150):

        output = session.post(
            "https://service.icprophet.com/icprophet/order/result/design",
            json={
                "order_id": order_id,
                "user_id": usrid
            },
            timeout=60
        )

        output.raise_for_status()
        PA_data = output.json()

        # 获取接口返回状态
        code = PA_data.get("code")
        message = str(PA_data.get("message", "")).strip()

        if code == 0:

            csv_list = (
                PA_data.get("result") or {}
            ).get("csv") or []

            # 检查 result1.csv 和 result2.csv
            csv_dict = {
                item.get("name"): item.get("data", [])
                for item in csv_list
            }

            data1 = csv_dict.get("result1.csv", [])
            data2 = csv_dict.get("result2.csv", [])

            if data1 and data2:
                print("PA 设计结果获取成功！")
                break

            last_message = "CSV 已返回，但数据尚未完整"

        else:

            last_message = message

            # 暂无 CSV 文件属于等待状态
            if "暂无CSV文件" not in message:
                raise RuntimeError(
                    f"获取PA设计结果失败: {message}"
                )

        print(
            f"等待 PA 设计结果... "
            f"({attempt + 1}/150) {last_message}"
        )

        time.sleep(2)

    else:
        raise TimeoutError(
            f"等待 PA 设计结果超时（约5分钟），"
            f"最后状态：{last_message}"
        )

    # =========================
    # 提取设计结果
    # =========================

    PA_result_ideal = data1[0]
    PA_result_w_loss = data2[0]


    print("理想结果：")
    print(PA_result_ideal)

    print("考虑损耗后的结果：")
    print(PA_result_w_loss)

# 确认是否采用设计
    choice = input(
        "输入 Y 继续获取设计参数，其他输入终止："
    ).strip().upper()

    if choice != "Y":
        return None

# 5. 获取生成代码
    show_code = session.post(
        "https://service.icprophet.com/icprophet/order/download/add",
        json={
            "order_id": order_id,
            "table_name": "result3.csv",
            "user_id": usrid
        },
        timeout=30
    )

    show_code.raise_for_status()

    PA_code = show_code.json()

    if PA_code.get("code") != 0:
        raise RuntimeError(
            f"获取设计参数失败: "
            f"{PA_code.get('message')}"
        )

    generation_code = PA_code["result"]["data"][0]

# 保存结果

    PA_OPT_FILE.write_text(
        json.dumps(
            {
                "PA_result_in_ideal":
                    PA_result_ideal,

                "PA_result_with_loss":
                    PA_result_w_loss,

                "generation_code":
                    generation_code
            },
            ensure_ascii=False,
            indent=2
        ),
        encoding="utf-8"
    )

    return 0

MatchingCircuit_ATTRIBUTE_ID = {
    ("28nm", "3.5", "0.85", "DIFF_DIFF"):
        "local_HKTvWJ-tycmY2gN5hXlIz",
    ("28nm", "3.5", "0.85", "DIFF_SINGLE"):
        "local_4Mc7nMwDszhdcTDbnrOLz",
    ("28nm", "3.5", "0.85", "SINGLE_DIFF"):
        "local_I10ggNLzmNNaCkBmyAAoJ",
    ("28nm", "3.5", "0.85", "SINGLE_SINGLE"):
        "local_JSbB0O6qIfWERJ5Q_e5Ya",

    ("28nm", "3.5", "2.8", "DIFF_DIFF"):
        "local_RJebo0qgBZoacFFYnkaRt",
    ("28nm", "3.5", "2.8", "DIFF_SINGLE"):
        "local_WfrQ8UP5QDXNS0E2HrJkU",
    ("28nm", "3.5", "2.8", "SINGLE_DIFF"):
        "local_FKvXmKjfHaQevowmOqZWn",
    ("28nm", "3.5", "2.8", "SINGLE_SINGLE"):
        "local_PGkPGxjAehU-oAVVeseaA",

    ("28nm", "3.5", "3.5", "DIFF_DIFF"):
        "local_F_wUEuT1Tf4Ln_MtNYmWN",
    ("28nm", "3.5", "3.5", "DIFF_SINGLE"):
        "local_OELs1mio4FtSObP3MObkW",
    ("28nm", "3.5", "3.5", "SINGLE_DIFF"):
        "local_wbd9qUUYmxYPGOKfUCWW1",
    ("28nm", "3.5", "3.5", "SINGLE_SINGLE"):
        "local_uS8xEJ5-Kab2z_QS9hoQb",

    # ==================== 40nm ====================
    ("40nm", "3.4", "0.9", "DIFF_DIFF"):
        "local_EpjKoJQvIwpKvsl8xDrbo",
    ("40nm", "3.4", "0.9", "DIFF_SINGLE"):
        "local_6jann7kxSoDGBoaUGrKZO",
    ("40nm", "3.4", "0.9", "SINGLE_DIFF"):
        "local_pZJeE1mbZ885HfdoLvJ8k",

    ("40nm", "3.4", "2.9", "DIFF_DIFF"):
        "local_UcDEg0_1ntac08wtiPWMm",
    ("40nm", "3.4", "2.9", "DIFF_SINGLE"):
        "local_07ZZJ0GW-NgeLcHcIvfL7",
    ("40nm", "3.4", "2.9", "SINGLE_DIFF"):
        "local_0_owwHsDKkYRSoSdyCJle",

    ("40nm", "3.4", "3.4", "DIFF_DIFF"):
        "local_NXt1MWrKP_IB12F3UlRW2",
    ("40nm", "3.4", "3.4", "DIFF_SINGLE"):
        "local_gZAzVPlI39oysclGulgf9",
    ("40nm", "3.4", "3.4", "SINGLE_DIFF"):
        "local_QCTHjEyqKUCT-CC4PkBIx",

    ("40nm", "3.5", "0.85", "DIFF_DIFF"):
        "local_pqB7e-MTBcERWr99mW1bB",
    ("40nm", "3.5", "0.85", "DIFF_SINGLE"):
        "local__CYk650Ham8A3xeQ4hNkb",
    ("40nm", "3.5", "0.85", "SINGLE_DIFF"):
        "local_QLpGLTqqsgVdASeAqpDFB",
    ("40nm", "3.5", "0.85", "SINGLE_SINGLE"):
        "local_fu-4OxDE-QXC1tf65wbI4",

    ("40nm", "3.5", "3", "DIFF_DIFF"):
        "local_cNu1DtYu3-bMP5mwAy0GC",
    ("40nm", "3.5", "3", "DIFF_SINGLE"):
        "local_h6vhhB3mru8IPY_70uUdy",
    ("40nm", "3.5", "3", "SINGLE_DIFF"):
        "local_OBFclU3GnXdjqiDbsU-nt",
    ("40nm", "3.5", "3", "SINGLE_SINGLE"):
        "local_pHMB7EZNWnlJ5FqNrjvLp",

    ("40nm", "3.5", "3.5", "DIFF_DIFF"):
        "local_3mjgpLAnVeSSUTOBCeAQD",
    ("40nm", "3.5", "3.5", "DIFF_SINGLE"):
        "local_mPrS8afwoV0_zj_ANxSIB",
    ("40nm", "3.5", "3.5", "SINGLE_DIFF"):
        "local_DfZE7PU_RRplnYuD0fiZL",
    ("40nm", "3.5", "3.5", "SINGLE_SINGLE"):
        "local_gI12CFks13emqJ8_cz2Ya",

    # ==================== 65nm ====================
    ("65nm", "3.4", "0.9", "DIFF_DIFF"):
        "local_fRoHGZm2D8--liR8rIWow",
    ("65nm", "3.4", "0.9", "DIFF_SINGLE"):
        "local_e6ySgd2OLJaTysLHXfwxz",
    ("65nm", "3.4", "0.9", "SINGLE_DIFF"):
        "local_qdHERtAMe2JP1VUAVhNWb",
    ("65nm", "3.4", "0.9", "SINGLE_SINGLE"):
        "local_GWT6PSoh7vWVeBm6Eo0O5",

    ("65nm", "3.4", "1.45", "DIFF_DIFF"):
        "local_Bz1rJ5L1e2kj10I16VgNU",
    ("65nm", "3.4", "1.45", "DIFF_SINGLE"):
        "local_3vUSn4O4HPXL2n6-GboPy",
    ("65nm", "3.4", "1.45", "SINGLE_DIFF"):
        "local_Yae04X4H4nCdpt1tzJvRb",
    ("65nm", "3.4", "1.45", "SINGLE_SINGLE"):
        "local_ID-NieHwGP-yB4XiDPOyB",

    ("65nm", "3.4", "2.8", "DIFF_DIFF"):
        "local_4mqvL4cWGRVst8HlW0rms",
    ("65nm", "3.4", "2.8", "DIFF_SINGLE"):
        "local_jsIhNkmHOFXyxulwb6Ua8",
    ("65nm", "3.4", "2.8", "SINGLE_DIFF"):
        "local_dNoErMo-sSNSJsc3d5Z-x",
    ("65nm", "3.4", "2.8", "SINGLE_SINGLE"):
        "local_QE71Wte-TBHfXKNWPdnjf",

    ("65nm", "3.4", "3.4", "DIFF_DIFF"):
        "local_4YrFzLHXEA7gxBIaRKv54",
    ("65nm", "3.4", "3.4", "DIFF_SINGLE"):
        "local_xsR-62BjnyTg414ePzGOD",
    ("65nm", "3.4", "3.4", "SINGLE_DIFF"):
        "local_eszC3qBBEAW_E2Ms4Jt7t",
    ("65nm", "3.4", "3.4", "SINGLE_SINGLE"):
        "local_uoOSWN5lYZUpLsGVd12Ig",
    }

def MatchingCircuit_design(
    session,
    freq_value,
    freq_scope,
    Z_L_real,
    Z_L_imag,
    Z_opt_real,
    Z_opt_imag,
    S11,
    IL,
    tech,
    layer_p_thickness,
    layer_s_thickness,
    input_type,
):
    key = (
        str(tech),
        str(layer_p_thickness),
        str(layer_s_thickness),
        str(input_type)
    )
    if key not in MatchingCircuit_ATTRIBUTE_ID:
            raise ValueError(
                f"不支持的 MatchingCircuit 参数组合: {key}"
            )
    # 1. 组装设计参数

    service_param = {
        "freq_value": freq_value,
        "freq_scope": freq_scope,
        "Z_L_real": Z_L_real,
        "Z_L_imag": Z_L_imag,
        "Z_opt_real": Z_opt_real,
        "Z_opt_imag": Z_opt_imag,
        "S11": S11,
        "IL": IL,
        "tech": tech,
        "layer_p_thickness": layer_p_thickness,
        "layer_s_thickness": layer_s_thickness,
        "input": input_type,
        "L_max": "",
        "W_max": ""
    }

    payload = {
        "order_type": "design",
        "service_attribute_id": MatchingCircuit_ATTRIBUTE_ID[key],
        "service_id": "497745720d674b728177fe4fa03a9995",
        "service_param": json.dumps(
            service_param,
            ensure_ascii=False
        ),
        "service_type": "MatchingCircuit",
        "user_id": usrid
    }

    # =========================
    # 2. 提交设计
    # =========================

    response = session.post(
        "https://service.icprophet.com/icprophet/order/add",
        json=payload,
        timeout=60
    )

    response.raise_for_status()
    result = response.json()

    if result.get("code") != 0:
        raise RuntimeError(
            f"变压器设计提交失败: {result.get('message')}"
        )

    order_id = result["result"]

    print(f"设计提交成功，Order ID: {order_id}")

    # =========================
    # 3. 轮询获取设计结果
    # =========================
    MatchingCircuit_data = None
    last_message = ""

    for attempt in range(150):

        output = session.post(
            "https://service.icprophet.com/icprophet/order/result/design",
            json={
                "order_id": order_id,
                "user_id": usrid
            },
            timeout=60
        )

        output.raise_for_status()
        MatchingCircuit_data = output.json()

        code = MatchingCircuit_data.get("code")
        message = str(
            MatchingCircuit_data.get("message", "")
        ).strip()

        # -------------------------
        # 情况 1：接口返回成功
        # -------------------------
        if code == 0:

            result_data = MatchingCircuit_data.get("result") or {}

            csv_list = result_data.get("csv") or []
            tab_list = result_data.get("tab_list") or []

            # 查找 result.csv
            csv_item = next(
                (
                    item for item in csv_list
                    if item.get("name") == "result.csv"
                ),
                None
            )

            csv_rows = (
                csv_item.get("data", [])
                if csv_item else []
            )

            # 查找 Smith.png
            Smith_url = next(
                (
                    item.get("url")
                    for item in tab_list
                    if item.get("name") == "Smith.png"
                    and item.get("url")
                ),
                None
            )

            # 查找 IL.png
            IL_url = next(
                (
                    item.get("url")
                    for item in tab_list
                    if item.get("name") == "IL.png"
                    and item.get("url")
                ),
                None
            )

            # 所有结果都准备好
            if csv_rows and Smith_url and IL_url:
                print("设计结果获取成功！")
                break

            last_message = "结果尚未完整生成"

        # -------------------------
        # 情况 2：还没有 CSV
        # -------------------------
        elif "暂无CSV文件" in message:

            last_message = message

        # -------------------------
        # 情况 3：真正的错误
        # -------------------------
        else:
            raise RuntimeError(
                f"获取设计结果失败: {message}"
            )

        print(
            f"等待设计结果... "
            f"({attempt + 1}/150) "
            f"{last_message}"
        )

        time.sleep(2)

    else:
        raise TimeoutError(
            "等待 MatchingCircuit 设计结果超时（约5分钟），"
            f"最后状态：{last_message}"
        )


    # =========================
    # 4. 提取 Cp、Cs
    # =========================

    csv_result = csv_rows[0]

    Cp = float(csv_result["Cp(fF)"])
    Cs = float(csv_result["Cs(fF)"])
    print(Cp)
    print(Cs)

    # =========================
    # 5. 下载 Smith、IL 图片
    # =========================

    if input_type == "SINGLE_DIFF":
        dirname = "Transformer_in"

    elif input_type == "DIFF_SINGLE":
        dirname = "Transformer_out"

    png_dir = PNG_DIR / dirname
    png_dir.mkdir(parents=True,exist_ok=True)

    smith_response = session.get(
        Smith_url,
        timeout=30
    )
    smith_response.raise_for_status()

    (png_dir / "Smith.png").write_bytes(
        smith_response.content
    )

    IL_response = session.get(
        IL_url,
        timeout=30
    )
    IL_response.raise_for_status()

    (png_dir / "IL.png").write_bytes(
        IL_response.content
    )

    # =========================
    # 6. 用户确认
    # =========================

    choice = input(
        "输入 Y 继续获取设计参数，其他输入终止："
    ).strip().upper()

    if choice != "Y":
        return None

    # =========================
    # 8. 请求 GDS 下载
    # =========================

    download_GDS = session.post(
        "https://service.icprophet.com/icprophet/order/download/add",
        json={
            "download_name": "Transformer_all.zip",
            "order_id": order_id,
            "user_id": usrid
        },
        timeout=60
    )

    download_GDS.raise_for_status()
    download_data = download_GDS.json()
    print("GDS download response:")
    print(json.dumps(download_data, indent=2, ensure_ascii=False))

    if download_data.get("code") != 0:
        raise RuntimeError(
            f"GDS下载请求失败: "
            f"{download_data.get('message')}"
        )

    GDS_url = download_data["result"]["url"]
    GDS_name = download_data["result"]["name"]

    # =========================
    # 9. 下载 GDS 文件
    # =========================

    gds_dir = GDS_DIR / dirname
    gds_dir.mkdir(parents=True,exist_ok=True)

    GDS_response = session.get(
        GDS_url,
        timeout=60
    )
    GDS_response.raise_for_status()

    (gds_dir / GDS_name).write_bytes(
        GDS_response.content
    )

    print(f"GDS 文件已保存: {GDS_name}")

    return 0
