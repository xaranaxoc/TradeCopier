"""
Smoke test for gui.py — verifies that App and all dialogs instantiate
without crashing under Xvfb, that critical attributes exist, and that
key refresh methods are callable. Intended to catch CTk migration
regressions like "window not appearing", missing attributes, or broken
.config() calls on widgets we migrated.

Usage (Linux/CI):
    xvfb-run -a python tests/smoke_gui.py

The test stubs out MetaTrader5, pystray, ctypes.windll (Windows-only),
license, and updater modules, and disables actual MT5 polling and
license dialogs so it can run headless on Linux.
"""

from __future__ import annotations

import os
import sys
import types

# Make repo root importable when running as `python tests/smoke_gui.py`.
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

# ── Stub Windows-only / external modules before importing gui ─────────


def _install_stubs() -> None:
    # MetaTrader5: any attribute lookup returns a no-op callable that
    # returns None — gui only checks `_MT5_OK`, but stub anyway.
    mt5 = types.ModuleType("MetaTrader5")
    mt5.initialize = lambda *a, **kw: False
    mt5.shutdown = lambda *a, **kw: None
    mt5.symbols_get = lambda *a, **kw: []
    mt5.symbol_info = lambda *a, **kw: None
    mt5.symbol_info_tick = lambda *a, **kw: None
    mt5.account_info = lambda *a, **kw: None
    mt5.terminal_info = lambda *a, **kw: None
    mt5.symbol_select = lambda *a, **kw: True
    mt5.TRADE_ACTION_DEAL = 1
    mt5.ORDER_TYPE_BUY = 0
    mt5.ORDER_TIME_GTC = 0
    mt5.TRADE_RETCODE_DONE = 10009
    mt5.SYMBOL_TRADE_MODE_FULL = 4
    sys.modules["MetaTrader5"] = mt5

    # ctypes.windll lookups (FindWindowW etc) — stub so import doesn't blow up.
    import ctypes
    if not hasattr(ctypes, "windll") or sys.platform != "win32":
        class _WinDLL:
            def __getattr__(self, name):
                class _Lib:
                    def __getattr__(self, fname):
                        return lambda *a, **kw: 0
                return _Lib()
        ctypes.windll = _WinDLL()

    # pystray / PIL — optional, gui guards with try/except.
    if "pystray" not in sys.modules:
        sys.modules["pystray"] = types.ModuleType("pystray")

    # license / updater stubs (gui imports as `license as lic_mod` etc.)
    lic = types.ModuleType("license")
    lic.load_license = lambda: {"token": "smoke-test-token"}
    lic.check_token = lambda token: (True, "ok", {})
    lic.request_code = lambda tg_id: (True, "sent")
    lic.verify_code = lambda tg_id, code: (True, {"token": "x"})
    sys.modules["license"] = lic

    upd = types.ModuleType("updater")
    upd.VERSION = "1.0.0"
    upd.check_update = lambda callback=None, no_update=None: None
    sys.modules["updater"] = upd


_install_stubs()

# Force window-system to whatever DISPLAY xvfb-run set up.
os.environ.setdefault("DISPLAY", ":99")


# ── Import gui ────────────────────────────────────────────────────────

import gui  # noqa: E402

# Make sure the activation flow doesn't pop a dialog: license is valid in
# the stub, so _schedule_license_check should be a no-op except scheduling
# the next check.


def _no_op(*a, **kw):
    return None


# Disable timers that would otherwise keep the loop alive forever.
gui.App._schedule_check = _no_op  # type: ignore[assignment]
gui.App._schedule_license_check = _no_op  # type: ignore[assignment]
gui.App._check_update = _no_op  # type: ignore[assignment]
gui.App._start_tray = _no_op  # type: ignore[assignment]
gui.App._update_master_info_silent = _no_op  # type: ignore[assignment]


# Avoid trying to read a non-existent .ico under Xvfb / Linux.
gui.ICON_DEFAULT = "/nonexistent.ico"
gui.ICON_CYAN = "/nonexistent.ico"


# ── Test helpers ──────────────────────────────────────────────────────

EXPECTED_APP_ATTRS = [
    # Master panel labels (.config()'d by _update_master_info_silent)
    "lbl_master_login", "lbl_master_bal", "lbl_master_eq", "lbl_master_pnl",
    # KPI cards (KPICard widgets, set_value()'d by _refresh_dashboard)
    "_kpi_cards",
    # Slaves
    "lbl_slave_count", "_table_frame", "_paned", "_next_row",
    # Bottom notebook + status bar
    "notebook", "trades_table", "log_text", "lbl_stats", "_status_pill",
    # Slave section card-header
    "_slaves_header",
    # Top-bar buttons
    "btn_info", "btn_start", "btn_stop",
    # State containers
    "_slaves", "_rows",
]


def _check_attrs(app: "gui.App") -> None:
    missing = [name for name in EXPECTED_APP_ATTRS if not hasattr(app, name)]
    assert not missing, f"App missing attributes: {missing}"
    # _kpi_cards must have all four KPI keys.
    for key in ("kpi_bal", "kpi_eq", "kpi_pnl", "kpi_conn"):
        assert key in app._kpi_cards, f"_kpi_cards missing key: {key}"


def _exercise_refresh(app: "gui.App") -> None:
    """Trigger the .config() heavy code paths to catch CTk shim regressions."""
    app._refresh_dashboard()
    app._update_slave_count()
    # toggle info button (changes btn_info bg/fg)
    app._toggle_info()
    app._toggle_info()
    # log a line (touches log_text.config and trades_table)
    app._log("smoke-test: hello", "info")
    app._log("smoke-test: ok ✅", "ok")


def _exercise_account_row(app: "gui.App") -> None:
    """Add a fake slave so AccountRow widgets get built. Catches CTk-shim
    regressions in the slave-row grid (bg_frame/accent_strip, labels,
    canvas dot, action buttons, .config() calls on the labels)."""
    fake_slave = {
        "id": "smoke-1", "name": "Smoke", "path": "C:\\fake\\terminal64.exe",
        "enabled": True, "symbol_map": {"EURUSD": "EURUSD.r"},
        "risk_type": "percent", "risk_value": 1.5,
        "max_trades_per_day": 3, "daily_loss_limit": 100.0, "default_lot": 0.01,
    }
    app._slaves.append(fake_slave)
    noop = lambda *a, **kw: None
    row = gui.AccountRow(
        app._table_frame, app._next_row, fake_slave,
        on_edit=noop, on_delete=noop, on_toggle=noop,
        on_test=noop, on_open=noop, on_close_all=noop,
    )
    app._next_row += 1
    app._rows.append(row)
    app._update_slave_count()
    # exercise the .config() paths on the row's labels (these go through
    # ctk_compat.Label.configure -> CTkLabel.configure).
    row.lbl_balance.config(text="$1234.56")
    row.lbl_pnl.config(text="+$12", fg=gui.GREEN)
    row.lbl_equity.config(text="$1230.00", fg=gui.FG_DIM)


def _exercise_dialogs(app: "gui.App") -> None:
    # SlaveDialog: avoid MT5 calls by stubbing _load_symbols.
    gui.SlaveDialog._load_symbols = lambda self: None  # type: ignore[assignment]
    dlg = gui.SlaveDialog(app)
    assert dlg.winfo_exists()
    dlg.destroy()
    # SymbolPickerDialog
    pick = gui.SymbolPickerDialog(app, ["EURUSD", "USDJPY", "XAUUSD"], "Test")
    assert pick.winfo_exists()
    pick.destroy()
    # SettingsDialog
    settings = gui.SettingsDialog(app)
    assert settings.winfo_exists()
    settings.destroy()


def main() -> int:
    app = gui.App()
    app.update_idletasks()
    try:
        _check_attrs(app)
        _exercise_refresh(app)
        _exercise_account_row(app)
        _exercise_dialogs(app)
        print("OK: gui smoke test passed")
        return 0
    except Exception as exc:  # pragma: no cover
        import traceback
        traceback.print_exc()
        print(f"FAIL: {exc}")
        return 1
    finally:
        try:
            app.destroy()
        except Exception:
            pass


if __name__ == "__main__":
    raise SystemExit(main())
