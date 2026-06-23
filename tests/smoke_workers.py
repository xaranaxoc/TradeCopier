"""Smoke test: запуск воркеров в отдельных процессах.

Не требует реального MT5-терминала: воркер с пустым/невалидным путём
должен сообщить об ошибке через очередь и корректно завершиться.
"""

import multiprocessing as mp
import os
import sys
import time

# Allow running from tests/ folder: add project root to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Force UTF-8 stdout so emoji in log messages don't crash Windows cp1251 console
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass


def run_master_smoke():
    from copier_worker import master_worker
    ctx = mp.get_context("spawn")
    out_q = ctx.Queue()
    ctl_q = ctx.Queue()
    # Невалидный путь → воркер сразу шлёт error и выходит
    proc = ctx.Process(target=master_worker, args=("", out_q, ctl_q, 0.05), daemon=True)
    proc.start()
    proc.join(timeout=5.0)
    assert not proc.is_alive(), "master_worker не завершился с пустым путём"
    msgs = []
    while True:
        try:
            msgs.append(out_q.get_nowait())
        except Exception:
            break
    assert any(m.get("type") == "log" for m in msgs), f"нет log сообщений: {msgs}"
    print("OK master_worker smoke. Messages:", msgs)


def run_slave_smoke():
    from copier_worker import slave_worker
    ctx = mp.get_context("spawn")
    in_q = ctx.Queue()
    out_q = ctx.Queue()
    ctl_q = ctx.Queue()
    cfg = {"id": "s1", "name": "smoke-slave", "path": ""}
    proc = ctx.Process(target=slave_worker, args=(cfg, in_q, out_q, ctl_q), daemon=True)
    proc.start()
    proc.join(timeout=5.0)
    assert not proc.is_alive(), "slave_worker не завершился с пустым путём"
    msgs = []
    while True:
        try:
            msgs.append(out_q.get_nowait())
        except Exception:
            break
    assert any(m.get("type") == "log" for m in msgs), f"нет log сообщений: {msgs}"
    print("OK slave_worker smoke. Messages:", msgs)


def run_copytrader_lifecycle_smoke():
    """CopyTrader.start()/stop() с пустым master path должен корректно отработать."""
    from copier import CopyTrader

    logs = []
    statuses = []

    def on_log(m):
        logs.append(m)

    def on_status(*a, **kw):
        statuses.append((a, kw))

    cfg = {"master": {"path": ""}, "slaves": []}
    ct = CopyTrader(
        config=cfg,
        state_file="_smoke_state.json",
        log_callback=on_log,
        status_callback=on_status,
    )
    ct.start()
    time.sleep(1.0)
    running_during = ct.is_running()
    ct.stop()
    print("OK CopyTrader lifecycle. running_during=", running_during,
          "logs_count=", len(logs))


if __name__ == "__main__":
    mp.freeze_support()
    print("--- master_worker smoke ---")
    run_master_smoke()
    print("--- slave_worker smoke ---")
    run_slave_smoke()
    print("--- CopyTrader lifecycle smoke ---")
    run_copytrader_lifecycle_smoke()
    print("ALL OK")
