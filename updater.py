import threading
import requests

API_URL = "http://2.26.142.85:8000"
VERSION = "1.1.0"


def check_update(callback=None):
    def _worker():
        try:
            r = requests.get(f"{API_URL}/version", timeout=10)
            data = r.json()
            remote_ver = data.get("version", "0.0.0")
            changelog = data.get("changelog", "")
            if _compare(remote_ver, VERSION) > 0:
                if callback:
                    callback(remote_ver, changelog)
        except Exception:
            pass

    t = threading.Thread(target=_worker, daemon=True)
    t.start()


def _compare(v1, v2):
    a = [int(x) for x in v1.split(".")]
    b = [int(x) for x in v2.split(".")]
    for i in range(max(len(a), len(b))):
        ai = a[i] if i < len(a) else 0
        bi = b[i] if i < len(b) else 0
        if ai > bi:
            return 1
        if ai < bi:
            return -1
    return 0
