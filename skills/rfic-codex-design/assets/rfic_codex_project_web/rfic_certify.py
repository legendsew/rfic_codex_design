import requests
import json
import time
from pathlib import Path
from getpass import getpass
import hashlib
import os

os.chdir(os.path.dirname(os.path.abspath(__file__)))
LOGIN_URL = f"https://service.icprophet.com/icprophet/user/login"
TOKEN_FILE = Path(".\\json\\token.json")
USRID_FILE = Path(".\\json\\usrid.json")

def save_token(token):
    TOKEN_FILE.write_text(
        json.dumps(
            {"token": token},
            ensure_ascii=False,
            indent=2
        ),
        encoding="utf-8"
    )

def load_token():
    if not TOKEN_FILE.exists():
        return None

    try:
        data = json.loads(
            TOKEN_FILE.read_text(encoding="utf-8")
        )

        return data.get("token")

    except Exception:
        return None

def login():
    user_name = input("账号: ").strip()
    password = getpass("密码: ")

    password_hash = hashlib.md5(
        password.encode("utf-8")
    ).hexdigest()

    payload = {
        "user_name": user_name,
        "login_type": "password",
        "login_source": "user",
        "password": password_hash,
        "user_id": ""
    }

    response = requests.post(
        LOGIN_URL,
        json=payload,
        timeout=30
    )

    response.raise_for_status()

    data = response.json()

    if data.get("code") != 0:
        raise RuntimeError(
            f"登录失败: {data.get('message', '未知错误')}"
        )

    token = data.get("result", {}).get("token")

    save_token(token)

    print("登录成功")

    return token

def create_session(token):
    session = requests.Session()

    session.headers.update({
        "Accept": "application/json, text/plain, */*",
        "Content-Type": "application/json;charset=UTF-8",
        "User-Token": token,
    })

    return session

def get_session():
    token = load_token()

    if token:
        print("使用已有 token。")
    else:
        print("本地没有 token，需要登录。")
        token = login()

    return create_session(token)

def save_usrid(usrid):
    USRID_FILE.write_text(
        json.dumps(
            {"usrid": usrid},
            ensure_ascii=False,
            indent=2
        ),
        encoding="utf-8"
    )

def get_usrid():
    response = session.post(
        "https://service.icprophet.com/icprophet/user/info",
        json={"user_id":""},
        timeout=30
        )
    response.raise_for_status()
    data = response.json()
    if data.get("code") != 0:
        print("Token 可能已失效：", data.get("message"))
        return None

    result = data.get("result")

    if not result:
        print("未获取到用户信息，Token 可能已失效")
        return None

    usrid = result.get("eid")

    if not usrid:
        print("返回结果中没有 eid")
        return None

    save_usrid(usrid)

    return usrid

session = get_session()
if get_usrid() == None:
    print("需重新登录")
    TOKEN_FILE.unlink()
    session = get_session()