import os
import json
import threading
import tempfile
import shutil
import requests

API_URL = "http://2.26.142.85:8000"
VERSION = "1.0.0"


def check_update(callback=None):
    def _worker():
        try:
            r = requests.get(f"{API_URL}/version", timeout=10)
            data = r.json()
            remote_ver = data.get("version", "0.0.0")
            url = data.get("url", "")
            changelog = data.get("changelog", "")
            if _compare(remote_ver, VERSION) > 0:
                if callback:
                    callback(remote_ver, url, changelog)
        except Exception:
            pass

    t = threading.Thread(target=_worker, daemon=True)
    t.start()


def download_and_install(url, progress_callback=None, done_callback=None):
    def _worker():
        try:
            tmp_dir = tempfile.mkdtemp()
            tmp_file = os.path.join(tmp_dir, "FTHTradeCopier.exe")
            r = requests.get(url, stream=True, timeout=30)
            total = int(r.headers.get("content-length", 0))
            downloaded = 0
            with open(tmp_file, "wb") as f:
                for chunk in r.iter_content(8192):
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total and progress_callback:
                        progress_callback(downloaded, total)
            if downloaded < 1024:
                if done_callback:
                    done_callback(False, "Download too small")
                return
            updater_path = os.path.join(tmp_dir, "updater.bat")
            exe_path = os.path.abspath(sys.argv[0] if getattr(sys, "frozen", False) else __file__)
            exe_dir = os.path.dirname(exe_path)
            bat = (
                "@echo off\n"
                "echo Updating FTH Trade Copier...\n"
                "timeout /t 3 /nobreak >nul\n"
                f'copy /y "{tmp_file}" "{exe_path}"\n'
                f'start "" "{exe_path}"\n'
                'del "%~f0"\n'
            )
            with open(updater_path, "w") as f:
                f.write(bat)
            import subprocess
            subprocess.Popen(
                ['cmd', '/c', updater_path],
                cwd=exe_dir,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            if done_callback:
                done_callback(True, None)
            import sys
            sys.exit(0)
        except Exception as e:
            if done_callback:
                done_callback(False, str(e))

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


import sys
