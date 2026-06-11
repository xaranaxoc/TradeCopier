import os
import json
import requests

APP_DATA_DIR = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "MT5CopyTrader")
LICENSE_FILE = os.path.join(APP_DATA_DIR, "license.json")

API_URL = "http://2.26.142.85:8000"
CHECK_INTERVAL = 600


def load_license():
    if not os.path.exists(LICENSE_FILE):
        return None
    try:
        with open(LICENSE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def save_license(data):
    os.makedirs(APP_DATA_DIR, exist_ok=True)
    with open(LICENSE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def request_code(tg_id: int):
    try:
        r = requests.post(f"{API_URL}/activate/request",
                          json={"tg_id": tg_id}, timeout=10)
        if r.status_code == 200:
            return True, r.json().get("message", "code_sent")
        try:
            detail = r.json().get("detail", r.text)
        except Exception:
            detail = r.text
        return False, detail
    except requests.RequestException as e:
        return False, str(e)


def verify_code(tg_id: int, code: str):
    try:
        r = requests.post(f"{API_URL}/activate/confirm",
                          json={"tg_id": tg_id, "code": code}, timeout=10)
        data = r.json()
        if r.status_code == 200 and data.get("ok"):
            save_license({"tg_id": tg_id, "token": data["token"]})
            return True, data["token"]
        if data.get("error") == "device_limit":
            return False, f"device_limit:{data.get('max', 2)}"
        try:
            detail = r.json().get("detail", r.text)
        except Exception:
            detail = r.text
        return False, detail
    except requests.RequestException as e:
        return False, str(e)


def check_token(token: str):
    try:
        r = requests.post(f"{API_URL}/activate/check",
                          json={"token": token}, timeout=10)
        data = r.json()
        return data.get("valid", False), data.get("reason", ""), data.get("tier", "")
    except requests.RequestException:
        return False, "connection_error", ""


def is_licensed():
    lic = load_license()
    if not lic or not lic.get("token"):
        return False
    valid, reason, tier = check_token(lic["token"])
    if not valid:
        if reason == "connection_error":
            return True
        return False
    return True
