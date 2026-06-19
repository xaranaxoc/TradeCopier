import os
import json
import base64
import hashlib
import subprocess
import requests
from datetime import datetime, timedelta

APP_DATA_DIR = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "MT5CopyTrader")
LICENSE_FILE = os.path.join(APP_DATA_DIR, "license.json")

API_URL = "http://2.26.142.85:8000"
CHECK_INTERVAL = 600

OFFLINE_GRACE_DAYS = 7

_ED25519_PUBKEY_BYTES = bytes.fromhex(
    "f3abad1161f70677df2fa2315016d2ae2c990340b2f2e0dca1c565835b11249f"
)


def _get_device_id() -> str:
    guid = "unknown"
    try:
        import winreg
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Cryptography")
        guid = winreg.QueryValueEx(key, "MachineGuid")[0]
        winreg.CloseKey(key)
    except Exception:
        pass
    vol = "unknown"
    try:
        result = subprocess.run(["vol", "C:"], capture_output=True, text=True, shell=True, timeout=5)
        lines = result.stdout.strip().split("\n")
        for line in lines:
            if "Serial" in line:
                vol = line.strip().split()[-1]
                break
    except Exception:
        pass
    return hashlib.sha256(f"{guid}:{vol}".encode()).hexdigest()


def _verify_sig(data: dict) -> bool:
    sig_b64 = data.pop("sig", None)
    if not sig_b64:
        return False
    payload = json.dumps(data, sort_keys=True).encode()
    try:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
        pubkey = Ed25519PublicKey.from_public_bytes(_ED25519_PUBKEY_BYTES)
        pubkey.verify(base64.b64decode(sig_b64), payload)
        return True
    except Exception:
        return False


def load_license():
    if not os.path.exists(LICENSE_FILE):
        return None
    try:
        with open(LICENSE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def save_license(data):
    try:
        os.makedirs(APP_DATA_DIR, exist_ok=True)
        with open(LICENSE_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def request_code(tg_id: int):
    device_id = _get_device_id()
    try:
        r = requests.post(f"{API_URL}/activate/request",
                          json={"tg_id": tg_id, "device_id": device_id}, timeout=10)
        if r.status_code == 200:
            data = r.json()
            if not _verify_sig(data):
                return False, "signature_invalid"
            return True, data.get("message", "code_sent")
        try:
            detail = r.json().get("detail", r.text)
        except Exception:
            detail = r.text
        return False, detail
    except (requests.RequestException, json.JSONDecodeError) as e:
        return False, str(e)


def verify_code(tg_id: int, code: str):
    device_id = _get_device_id()
    try:
        r = requests.post(f"{API_URL}/activate/confirm",
                          json={"tg_id": tg_id, "code": code, "device_id": device_id}, timeout=10)
        data = r.json()
        if not _verify_sig(data):
            return False, "signature_invalid"
        if r.status_code == 200 and data.get("ok"):
            save_license({
                "tg_id": tg_id,
                "token": data["token"],
                "last_ok_check": datetime.utcnow().isoformat(),
            })
            return True, data["token"]
        if data.get("error") == "device_limit":
            return False, f"device_limit:{data.get('max', 2)}"
        try:
            detail = r.json().get("detail", r.text)
        except Exception:
            detail = r.text
        return False, detail
    except (requests.RequestException, json.JSONDecodeError) as e:
        return False, str(e)


def check_token(token: str):
    device_id = _get_device_id()
    try:
        r = requests.post(f"{API_URL}/activate/check",
                          json={"token": token, "device_id": device_id}, timeout=10)
        data = r.json()
        if not _verify_sig(data):
            return False, "signature_invalid", ""
        return data.get("valid", False), data.get("reason", ""), data.get("tier", "")
    except (requests.RequestException, json.JSONDecodeError):
        return False, "connection_error", ""


def is_licensed():
    lic = load_license()
    if not lic or not lic.get("token"):
        return False
    valid, reason, tier = check_token(lic["token"])
    if valid:
        lic["last_ok_check"] = datetime.utcnow().isoformat()
        save_license(lic)
        return True
    if reason == "connection_error":
        last_str = lic.get("last_ok_check")
        if last_str:
            try:
                last = datetime.fromisoformat(last_str)
                if datetime.utcnow() - last < timedelta(days=OFFLINE_GRACE_DAYS):
                    return True
            except Exception:
                pass
        return False
    return False
