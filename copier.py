"""
MT5 Local Copy Trader — логика копирования сделок
"""

import os
import json
import time
import threading
import ctypes
from ctypes import wintypes
from datetime import datetime, date
from typing import Callable, Dict, Any, Optional

import sys as _sys
if 'MetaTrader5' in _sys.modules:
    mt5 = _sys.modules['MetaTrader5']
else:
    try:
        import MetaTrader5 as mt5
    except Exception:
        mt5 = None

try:
    import psutil
except ImportError:
    psutil = None


# ─────────────────────────────────────────────────────────────
#  Вспомогательные функции
# ─────────────────────────────────────────────────────────────

def is_terminal_running(path: str) -> bool:
    if psutil is None:
        return True
    norm_path = os.path.normcase(os.path.abspath(path))
    for proc in psutil.process_iter(['exe']):
        try:
            exe = proc.info.get('exe')
            if exe and os.path.normcase(exe) == norm_path:
                return True
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass
    return False


def activate_terminal(path: str) -> bool:
    if psutil is None:
        return False
    norm_path = os.path.normcase(os.path.abspath(path))
    pids = []
    for proc in psutil.process_iter(['exe', 'pid']):
        try:
            exe = proc.info.get('exe')
            if exe and os.path.normcase(exe) == norm_path:
                pids.append(proc.info['pid'])
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass
    if not pids:
        return False

    user32 = ctypes.windll.user32
    EnumWindows = user32.EnumWindows
    GetWindowThreadProcessId = user32.GetWindowThreadProcessId
    IsWindowVisible = user32.IsWindowVisible
    SetForegroundWindow = user32.SetForegroundWindow
    ShowWindow = user32.ShowWindow
    SW_RESTORE = 9

    WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    result = [False]

    def enum_cb(hwnd, _):
        pid = wintypes.DWORD()
        GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if pid.value in pids and IsWindowVisible(hwnd):
            ShowWindow(hwnd, SW_RESTORE)
            SetForegroundWindow(hwnd)
            result[0] = True
            return False
        return True

    EnumWindows(WNDENUMPROC(enum_cb), 0)
    return result[0]


def load_state(state_file: str) -> Dict:
    if os.path.exists(state_file):
        try:
            with open(state_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            if "positions" not in data:
                data["positions"] = {}
            if "orders" not in data:
                data["orders"] = {}
            if "daily_trades" not in data:
                data["daily_trades"] = {}
            if "daily_loss_balance" not in data:
                data["daily_loss_balance"] = {}
            return data
        except Exception:
            pass
    return {"positions": {}, "orders": {}, "daily_trades": {}}


def save_state(state_file: str, state: Dict) -> None:
    try:
        with open(state_file, 'w', encoding='utf-8') as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


_RATE_CACHE: Dict[str, tuple] = {}
_RATE_CACHE_TTL = 30.0


def _get_currency_rate(from_curr: str, to_curr: str) -> float:
    if mt5 is None or not from_curr or not to_curr:
        return 1.0
    if from_curr == to_curr:
        return 1.0
    key = f"{from_curr}_{to_curr}"
    now = time.time()
    if key in _RATE_CACHE:
        val, ts = _RATE_CACHE[key]
        if now - ts < _RATE_CACHE_TTL:
            return val
    candidates = [from_curr + to_curr, to_curr + from_curr]
    for pair in candidates:
        info = mt5.symbol_info(pair)
        if info is not None:
            mt5.symbol_select(pair, True)
            tick = mt5.symbol_info_tick(pair)
            if tick and tick.bid > 0:
                mid = (tick.bid + tick.ask) / 2
                if pair == to_curr + from_curr:
                    val = 1.0 / mid
                else:
                    val = mid
                _RATE_CACHE[key] = (val, now)
                return val
    all_symbols = mt5.symbols_get()
    if all_symbols:
        from_upper = from_curr.upper()
        to_upper = to_curr.upper()
        for s in all_symbols:
            name_upper = s.name.upper()
            if name_upper.startswith(from_upper) and to_upper in name_upper[len(from_upper):]:
                mt5.symbol_select(s.name, True)
                tick = mt5.symbol_info_tick(s.name)
                if tick and tick.bid > 0:
                    mid = (tick.bid + tick.ask) / 2
                    _RATE_CACHE[key] = (mid, now)
                    return mid
            if name_upper.startswith(to_upper) and from_upper in name_upper[len(to_upper):]:
                mt5.symbol_select(s.name, True)
                tick = mt5.symbol_info_tick(s.name)
                if tick and tick.bid > 0:
                    mid = (tick.bid + tick.ask) / 2
                    val = 1.0 / mid
                    _RATE_CACHE[key] = (val, now)
                    return val
    if from_curr != "USD" and to_curr != "USD":
        r1 = _get_currency_rate(from_curr, "USD")
        r2 = _get_currency_rate("USD", to_curr)
        if r1 > 0 and r2 > 0:
            val = r1 * r2
            _RATE_CACHE[key] = (val, now)
            return val
    return 1.0


def calculate_lot(symbol_info, sl_distance: float,
                   risk_type: str, risk_value: float,
                   balance: float, deposit_curr: str = "") -> float:
    if sl_distance <= 0:
        return 0.0

    tick_size = symbol_info.trade_tick_size
    contract_size = symbol_info.trade_contract_size or 0.0

    tick_value = 0.0
    rate = 1.0
    profit_curr = getattr(symbol_info, 'currency_profit', '') or ''

    if contract_size > 0 and tick_size > 0:
        raw_tick_value = contract_size * tick_size
        if profit_curr and deposit_curr and profit_curr != deposit_curr:
            rate = _get_currency_rate(profit_curr, deposit_curr)
            tick_value = raw_tick_value * rate
        else:
            tick_value = raw_tick_value

    if tick_value <= 0:
        tick_value_profit = abs(symbol_info.trade_tick_value or 0.0)
        tick_value_loss = abs(symbol_info.trade_tick_value_loss or 0.0)
        tick_value = max(tick_value_profit, tick_value_loss)

    if tick_size <= 0 or tick_value <= 0:
        return 0.0

    sl_ticks = sl_distance / tick_size

    if risk_type == "percent":
        risk_amount = balance * risk_value / 100.0
    else:
        risk_amount = risk_value

    if sl_ticks <= 0:
        return 0.0

    lot = risk_amount / (sl_ticks * tick_value)

    volume_step = symbol_info.volume_step
    if volume_step > 0:
        lot = round(lot / volume_step) * volume_step

    lot = max(symbol_info.volume_min, min(symbol_info.volume_max, lot))
    return round(lot, 8)


def resolve_symbol(name: str) -> Optional[str]:
    if mt5 is None:
        return name
    info = mt5.symbol_info(name)
    if info is not None:
        return name
    all_symbols = mt5.symbols_get()
    if all_symbols:
        name_upper = name.upper()
        for s in all_symbols:
            if s.name.upper() == name_upper:
                return s.name
    return None


def get_filling_mode(symbol_info) -> int:
    if mt5 is None:
        return 0
    filling = symbol_info.filling_mode
    if filling & 2:
        return mt5.ORDER_FILLING_FOK
    if filling & 1:
        return mt5.ORDER_FILLING_IOC
    return mt5.ORDER_FILLING_RETURN


_FILLING_CACHE: Dict[str, int] = {}


def try_send_order(request: Dict, log_fn=None) -> object:
    symbol = request.get("symbol", "")
    cached_filling = _FILLING_CACHE.get(symbol)
    if cached_filling is not None:
        request["type_filling"] = cached_filling
    result = mt5.order_send(request)
    if result is not None and result.retcode == 10030:
        original_filling = request.get("type_filling", 0)
        filling_names = {
            mt5.ORDER_FILLING_FOK: "FOK",
            mt5.ORDER_FILLING_IOC: "IOC",
            mt5.ORDER_FILLING_RETURN: "RETURN",
        }
        if log_fn:
            log_fn(
                f"⚠️ retcode=10030 с filling={filling_names.get(original_filling, original_filling)}, "
                f"пробуем другие"
            )
        for alt_filling in [mt5.ORDER_FILLING_FOK,
                            mt5.ORDER_FILLING_IOC,
                            mt5.ORDER_FILLING_RETURN]:
            if alt_filling == original_filling:
                continue
            request["type_filling"] = alt_filling
            result = mt5.order_send(request)
            if log_fn:
                log_fn(
                    f"🔄 filling={filling_names.get(alt_filling, alt_filling)} → "
                    f"retcode={result.retcode if result else -1}"
                )
            if result is not None and result.retcode != 10030:
                if symbol:
                    _FILLING_CACHE[symbol] = alt_filling
                return result
        request["type_filling"] = original_filling
    if result is not None and result.retcode != 10030 and symbol:
        _FILLING_CACHE[symbol] = request.get("type_filling", 0)
    return result


def normalize_price(price: float, digits: int) -> float:
    return round(price, digits)


def opposite_order_type(order_type: int) -> int:
    if mt5 is None:
        return 0
    if order_type == mt5.ORDER_TYPE_BUY:
        return mt5.ORDER_TYPE_SELL
    if order_type == mt5.ORDER_TYPE_SELL:
        return mt5.ORDER_TYPE_BUY
    return order_type


def order_type_name(order_type: int) -> str:
    if mt5 is None:
        return str(order_type)
    names = {
        mt5.ORDER_TYPE_BUY: "BUY",
        mt5.ORDER_TYPE_SELL: "SELL",
        mt5.ORDER_TYPE_BUY_LIMIT: "BUY_LIMIT",
        mt5.ORDER_TYPE_SELL_LIMIT: "SELL_LIMIT",
        mt5.ORDER_TYPE_BUY_STOP: "BUY_STOP",
        mt5.ORDER_TYPE_SELL_STOP: "SELL_STOP",
    }
    return names.get(order_type, str(order_type))


PENDING_ORDER_TYPES = None


def get_pending_types():
    global PENDING_ORDER_TYPES
    if PENDING_ORDER_TYPES is None and mt5 is not None:
        PENDING_ORDER_TYPES = {
            mt5.ORDER_TYPE_BUY_LIMIT,
            mt5.ORDER_TYPE_SELL_LIMIT,
            mt5.ORDER_TYPE_BUY_STOP,
            mt5.ORDER_TYPE_SELL_STOP,
        }
    return PENDING_ORDER_TYPES or set()


# ─────────────────────────────────────────────────────────────
#  Основной класс копитрейдера (multiprocess фасад)
# ─────────────────────────────────────────────────────────────
import multiprocessing as _mp
import queue as _queue


class CopyTrader:
    """
    Фасад над multiprocess-воркерами.

    Архитектура:
    - master_worker (процесс): держит подключение к мастеру, шлёт diff-события.
    - slave_worker (процесс per slave): держит подключение, исполняет команды.
    - orchestrator (поток в main process): принимает события мастера и слейвов,
      ведёт state.json, рассылает команды слейвам, реализует защиты.
    - reader (поток в main process): читает log/status/trade события, зовёт колбэки GUI.
    """

    def __init__(
        self,
        config: Dict,
        state_file: str,
        log_callback: Callable[[str], None],
        status_callback: Callable[[str, str, float, float, float, float], None],
        trade_callback: Optional[Callable[[Dict], None]] = None,
        config_file: str = "",
    ):
        self.config = config
        self.config_file = config_file
        self.state_file = state_file
        self.log_cb = log_callback
        self.status_cb = status_callback
        self.trade_cb = trade_callback

        self._lock = threading.Lock()
        self._state_dirty: bool = False

        # Pause flags по слейвам (для защит)
        self._drawdown_paused: Dict[str, bool] = {}
        self._trades_paused: Dict[str, bool] = {}
        self._daily_loss_paused: Dict[str, bool] = {}

        # Кэши legacy (не используются в новом цикле, но оставлены для совместимости
        # с тестами/одноразовыми операциями)
        self._rate_cache: Dict[str, tuple] = {}
        self._filling_cache: Dict[str, int] = {}
        self._symbol_cache: Dict[str, Optional[str]] = {}

        self.state = load_state(state_file)

        # ── multiprocess infra ──
        self._mp_ctx = None  # type: Optional[Any]
        self._master_proc: Optional[Any] = None
        self._slave_procs: Dict[str, Any] = {}  # sid -> Process
        self._slave_cfg_by_sid: Dict[str, Dict] = {}
        self._master_event_q = None
        self._master_control_q = None
        self._slave_in_qs: Dict[str, Any] = {}      # sid -> Queue (main → slave)
        self._slave_out_q = None                     # общая очередь slave → main
        self._slave_control_qs: Dict[str, Any] = {}
        self._orchestrator_thread: Optional[threading.Thread] = None
        self._reader_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._config_mtime: float = 0.0

        # Снапшот тикетов мастера на старте — НЕ копировать уже открытые позиции
        self._start_position_tickets: set = set()
        self._start_order_tickets: set = set()
        self._snapshot_received = False

        # last known master state
        self._master_balance: float = 0.0
        self._master_equity: float = 0.0

        # last known volumes (для partial close detection)
        self._master_volumes: Dict[str, float] = {}

        # last known slave states
        self._slave_states: Dict[str, Dict] = {}

    # ── Статический helper ────────────────────────────────────

    @staticmethod
    def _sym_lookup(d: Dict[str, Any], key: str) -> Optional[Any]:
        key_upper = key.upper()
        for k, v in d.items():
            if k.upper() == key_upper:
                return v
        return None

    # ── Логирование / статусы ────────────────────────────────

    def _log(self, msg: str):
        ts = datetime.now().strftime("%H:%M:%S")
        try:
            self.log_cb(f"[{ts}] {msg}")
        except Exception:
            pass

    def _status(self, terminal_id: str, status: str,
                 balance: float = 0, equity: float = 0,
                 daily_loss: float = 0, daily_loss_limit: float = 0):
        try:
            self.status_cb(terminal_id, status, balance, equity, daily_loss, daily_loss_limit)
        except Exception:
            pass

    def _trade_event(self, info: Dict):
        if self.trade_cb:
            try:
                self.trade_cb(info)
            except Exception:
                pass

    # ── Reload config (stop/start pattern) ───────────────────

    def _reload_config(self):
        if not self.config_file:
            return
        try:
            mtime = os.path.getmtime(self.config_file)
            if mtime == self._config_mtime:
                return
            self._config_mtime = mtime
            with open(self.config_file, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            if "profiles" in cfg:
                idx = cfg.get("active_profile", 0)
                profiles = cfg.get("profiles", [])
                if idx < len(profiles):
                    p = profiles[idx]
                    cfg["master"] = p.get("master", {})
                    cfg["slaves"] = p.get("slaves", [])
            with self._lock:
                old_master = self.config.get("master", {}).get("path", "")
                self.config = cfg
                if not self.config.get("master"):
                    self.config["master"] = {}
                if not self.config.get("master", {}).get("path"):
                    self.config["master"]["path"] = old_master
            # Шлём обновлённый конфиг слейвам (горячий апдейт symbol_map/risk и т.п.)
            slaves = self.config.get("slaves", [])
            for s in slaves:
                sid = s.get("id", s.get("name", ""))
                if sid in self._slave_in_qs:
                    try:
                        self._slave_in_qs[sid].put_nowait({"type": "config_update", "slave": s})
                        self._slave_cfg_by_sid[sid] = s
                    except Exception:
                        pass
        except Exception:
            pass

    # ── Daily counters ───────────────────────────────────────

    def _increment_daily_trade(self, sid: str):
        today_str = date.today().isoformat()
        daily: Dict = self.state.setdefault("daily_trades", {})
        if daily.get("_date") != today_str:
            daily.clear()
            daily["_date"] = today_str
        daily[sid] = daily.get(sid, 0) + 1
        self._state_dirty = True

    # ── Публичный интерфейс ──────────────────────────────────

    def start(self):
        if self._orchestrator_thread and self._orchestrator_thread.is_alive():
            return
        if mt5 is None:
            self._log("❌ MetaTrader5 не установлен")
            return

        self._stop_event.clear()
        self._snapshot_received = False
        self._start_position_tickets = set()
        self._start_order_tickets = set()
        self._master_volumes = {}
        self._slave_states = {}

        # Используем 'spawn' контекст (по умолчанию на Windows)
        self._mp_ctx = _mp.get_context("spawn")

        master_path = self.config.get("master", {}).get("path", "")
        if not master_path:
            self._log("❌ MASTER: путь не задан")
            return

        poll_interval = float(self.config.get("poll_interval_seconds", 0.03))

        # ── Очереди ──
        self._master_event_q = self._mp_ctx.Queue()
        self._master_control_q = self._mp_ctx.Queue()
        self._slave_out_q = self._mp_ctx.Queue()
        self._slave_in_qs = {}
        self._slave_control_qs = {}
        self._slave_procs = {}
        self._slave_cfg_by_sid = {}

        # Сразу показать промежуточный статус мастера, чтобы UI не висел на
        # старом "не запущено" пока процесс стартует и mt5.initialize() работает.
        self._status("master", "🟡 запуск…")

        # ── Master process ──
        from copier_worker import master_worker, slave_worker
        self._master_proc = self._mp_ctx.Process(
            target=master_worker,
            args=(master_path, self._master_event_q, self._master_control_q, poll_interval),
            daemon=True,
        )
        self._master_proc.start()

        # ── Slave processes ──
        slaves = self.config.get("slaves", [])
        for s in slaves:
            if not s.get("enabled", True):
                continue
            sid = s.get("id", s.get("name", "?"))
            in_q = self._mp_ctx.Queue()
            ctl_q = self._mp_ctx.Queue()
            proc = self._mp_ctx.Process(
                target=slave_worker,
                args=(s, in_q, self._slave_out_q, ctl_q),
                daemon=True,
            )
            self._slave_in_qs[sid] = in_q
            self._slave_control_qs[sid] = ctl_q
            self._slave_procs[sid] = proc
            self._slave_cfg_by_sid[sid] = s
            proc.start()
            # Промежуточный статус — UI не будет висеть на старом значении
            # пока процесс стартует и mt5.initialize() работает.
            self._status(s.get("name", sid), "🟡 запуск…")

        # ── Orchestrator + reader threads ──
        self._orchestrator_thread = threading.Thread(
            target=self._orchestrator_loop, daemon=True
        )
        self._reader_thread = threading.Thread(
            target=self._slave_reader_loop, daemon=True
        )
        self._orchestrator_thread.start()
        self._reader_thread.start()

        self._log(f"🚀 Запущено: мастер + {len(self._slave_procs)} слейв(а/ов)")

    def stop(self):
        self._stop_event.set()

        # Шлём команды stop
        try:
            if self._master_control_q is not None:
                self._master_control_q.put_nowait({"type": "stop"})
        except Exception:
            pass
        for sid, ctl in self._slave_control_qs.items():
            try:
                ctl.put_nowait({"type": "stop"})
            except Exception:
                pass

        # Ждём процессы
        if self._master_proc is not None:
            self._master_proc.join(timeout=3.0)
            if self._master_proc.is_alive():
                try:
                    self._master_proc.terminate()
                except Exception:
                    pass
        for sid, proc in self._slave_procs.items():
            proc.join(timeout=3.0)
            if proc.is_alive():
                try:
                    proc.terminate()
                except Exception:
                    pass

        # Threads сами завершатся по _stop_event
        if self._orchestrator_thread is not None:
            self._orchestrator_thread.join(timeout=2.0)
        if self._reader_thread is not None:
            self._reader_thread.join(timeout=2.0)

        # Сохраняем state
        with self._lock:
            save_state(self.state_file, self.state)

        # Очистка ссылок
        self._master_proc = None
        self._slave_procs = {}
        self._slave_in_qs = {}
        self._slave_control_qs = {}
        self._master_event_q = None
        self._master_control_q = None
        self._slave_out_q = None
        self._orchestrator_thread = None
        self._reader_thread = None
        self._log("🛑 Копитрейдер остановлен")

    def is_running(self) -> bool:
        return (
            self._orchestrator_thread is not None
            and self._orchestrator_thread.is_alive()
        )

    # ── Reader thread: события от слейвов ────────────────────

    def _slave_reader_loop(self):
        while not self._stop_event.is_set():
            try:
                msg = self._slave_out_q.get(timeout=0.1)
            except Exception:
                continue
            if msg is None:
                continue
            t = msg.get("type")
            try:
                if t == "log":
                    self._log(msg["msg"])
                elif t == "slave_state":
                    self._handle_slave_state(msg)
                elif t == "slave_status_text":
                    sid = msg.get("sid", "")
                    sname = self._slave_cfg_by_sid.get(sid, {}).get("name", sid)
                    self._status(sname, msg.get("status", ""))
                elif t == "trade_event":
                    self._trade_event(msg["info"])
                elif t == "position_opened":
                    self._handle_position_opened(msg)
                elif t == "position_closed_ack":
                    self._handle_position_closed_ack(msg)
                elif t == "order_placed":
                    self._handle_order_placed(msg)
                elif t == "order_cancelled_ack":
                    pass  # ничего особенного
            except Exception as e:
                self._log(f"❌ reader: исключение {e}")

    def _handle_slave_state(self, msg: Dict):
        sid = msg["sid"]
        sname = self._slave_cfg_by_sid.get(sid, {}).get("name", sid)
        self._slave_states[sid] = msg
        balance = msg.get("balance", 0.0)
        equity = msg.get("equity", 0.0)
        status = msg.get("status", "")
        # Защиты
        slave_cfg = self._slave_cfg_by_sid.get(sid, {})

        # Drawdown
        max_dd = slave_cfg.get("max_drawdown", 0)
        dd_paused = False
        if max_dd > 0 and balance > 0:
            dd_pct = (balance - equity) / balance * 100
            if dd_pct >= max_dd:
                dd_paused = True
                if not self._drawdown_paused.get(sid):
                    self._log(f"🛑 [{sname}] Просадка {dd_pct:.1f}% >= {max_dd}% — копирование приостановлено")
                    self._drawdown_paused[sid] = True
                status = f"🔴 #{msg.get('login', '?')} просадка {dd_pct:.1f}%"
            else:
                if self._drawdown_paused.get(sid):
                    self._log(f"✅ [{sname}] Просадка {dd_pct:.1f}% < {max_dd}% — копирование возобновлено")
                    self._drawdown_paused[sid] = False

        # Daily trades limit
        max_trades = slave_cfg.get("max_trades_per_day", 0)
        trades_paused = False
        if max_trades > 0:
            today_str = date.today().isoformat()
            daily: Dict = self.state.setdefault("daily_trades", {})
            if daily.get("_date") != today_str:
                daily.clear()
                daily["_date"] = today_str
            today_count = daily.get(sid, 0)
            if today_count >= max_trades:
                trades_paused = True
                if not self._trades_paused.get(sid):
                    self._log(f"🛑 [{sname}] Лимит сделок {today_count}/{max_trades} — копирование приостановлено")
                    self._trades_paused[sid] = True
            else:
                if self._trades_paused.get(sid):
                    self._log(f"✅ [{sname}] Лимит сделок {today_count}/{max_trades} — копирование возобновлено")
                    self._trades_paused[sid] = False

        # Daily loss
        daily_loss_limit = slave_cfg.get("daily_loss_limit", 0)
        daily_loss = 0.0
        loss_paused = False
        if daily_loss_limit > 0 and balance > 0:
            today_str = date.today().isoformat()
            dl_state: Dict = self.state.setdefault("daily_loss_balance", {})
            if dl_state.get("_date") != today_str:
                if dl_state.get("_date"):
                    self._log(f"🔄 [{sname}] Новый день — сброс дневного убытка")
                    if self._daily_loss_paused.get(sid):
                        self._log(f"✅ [{sname}] Лимит убытка снят — копирование возобновлено")
                dl_state.clear()
                dl_state["_date"] = today_str
                self._daily_loss_paused.pop(sid, None)
            if sid not in dl_state:
                dl_state[sid] = balance
                self._state_dirty = True
            start_bal = dl_state.get(sid, balance)
            daily_loss = max(0.0, start_bal - equity)
            if daily_loss >= daily_loss_limit:
                loss_paused = True
                if not self._daily_loss_paused.get(sid):
                    self._log(f"🛑 [{sname}] Дневной убыток ${daily_loss:.2f} >= ${daily_loss_limit:.2f} — закрываем все позиции")
                    # Команда слейв-воркеру: закрыть всё
                    in_q = self._slave_in_qs.get(sid)
                    if in_q is not None:
                        try:
                            in_q.put_nowait({"type": "close_all"})
                        except Exception:
                            pass
                    self._daily_loss_paused[sid] = True
                status = f"🔴 #{msg.get('login', '?')} убыток ${daily_loss:.2f}"

        # Сохраним флаги для orchestrator
        self._slave_states[sid]["_dd_paused"] = dd_paused
        self._slave_states[sid]["_trades_paused"] = trades_paused
        self._slave_states[sid]["_loss_paused"] = loss_paused

        self._status(sname, status, balance, equity, daily_loss, daily_loss_limit)

    def _is_paused(self, sid: str) -> bool:
        st = self._slave_states.get(sid, {})
        return bool(st.get("_dd_paused") or st.get("_trades_paused") or st.get("_loss_paused"))

    def _handle_position_opened(self, msg: Dict):
        if not msg.get("ok"):
            return
        sid = msg["sid"]
        master_ticket = msg["master_ticket"]
        slave_ticket = msg["slave_ticket"]
        with self._lock:
            state_pos = self.state.setdefault("positions", {})
            if master_ticket not in state_pos:
                state_pos[master_ticket] = {}
            state_pos[master_ticket][sid] = slave_ticket
            self._state_dirty = True
            self._increment_daily_trade(sid)

    def _handle_position_closed_ack(self, msg: Dict):
        sid = msg["sid"]
        master_ticket = msg["master_ticket"]
        with self._lock:
            state_pos = self.state.setdefault("positions", {})
            if master_ticket in state_pos:
                state_pos[master_ticket].pop(sid, None)
                if not state_pos[master_ticket]:
                    state_pos.pop(master_ticket, None)
                self._state_dirty = True

    def _handle_order_placed(self, msg: Dict):
        if not msg.get("ok"):
            return
        sid = msg["sid"]
        master_ticket = msg["master_ticket"]
        slave_ticket = msg["slave_ticket"]
        with self._lock:
            state_ord = self.state.setdefault("orders", {})
            if master_ticket not in state_ord:
                state_ord[master_ticket] = {}
            state_ord[master_ticket][sid] = slave_ticket
            self._state_dirty = True
            self._increment_daily_trade(sid)

    # ── Orchestrator thread: события от мастера ──────────────

    def _orchestrator_loop(self):
        last_state_save = time.time()
        last_config_check = time.time()

        while not self._stop_event.is_set():
            # Periodic: state save + config reload
            now = time.time()
            if now - last_state_save >= 2.0:
                last_state_save = now
                if self._state_dirty:
                    with self._lock:
                        save_state(self.state_file, self.state)
                        self._state_dirty = False
            if now - last_config_check >= 5.0:
                last_config_check = now
                # горячий reload symbol_map / risk — без рестарта процессов
                self._reload_config()

            # События от мастера
            try:
                msg = self._master_event_q.get(timeout=0.05)
            except Exception:
                continue
            if msg is None:
                continue
            t = msg.get("type")
            try:
                if t == "snapshot":
                    self._handle_master_snapshot(msg)
                elif t == "master_state":
                    self._handle_master_state(msg)
                elif t == "master_status_text":
                    # промежуточные статусы от master_worker (запуск/ретраи/ошибки)
                    self._status("master", msg.get("status", ""))
                elif t == "position_new":
                    self._handle_master_position_new(msg["pos"])
                elif t == "position_closed":
                    self._handle_master_position_closed(msg["ticket"])
                elif t == "position_modified":
                    self._handle_master_position_modified(msg)
                elif t == "order_new":
                    self._handle_master_order_new(msg["order"])
                elif t == "order_gone":
                    self._handle_master_order_gone(msg)
                elif t == "log":
                    self._log(msg["msg"])
            except Exception as e:
                self._log(f"❌ orchestrator: исключение {e}")

    def _handle_master_snapshot(self, msg: Dict):
        self._start_position_tickets = set(msg.get("position_tickets", []))
        self._start_order_tickets = set(msg.get("order_tickets", []))
        self._snapshot_received = True
        self._log(
            f"📸 MASTER snapshot: {len(self._start_position_tickets)} позиций, "
            f"{len(self._start_order_tickets)} ордеров (не копируются)"
        )

    def _handle_master_state(self, msg: Dict):
        self._master_balance = msg.get("balance", 0.0)
        self._master_equity = msg.get("equity", 0.0)
        login = msg.get("login", 0)
        trade_allowed = msg.get("trade_allowed", True)
        if trade_allowed:
            status = f"🟢 #{login} ${self._master_balance:.2f}"
        else:
            status = f"⚠️ #{login} алготрейдинг ВЫКЛ (только чтение)"
        self._status("master", status, self._master_balance, self._master_equity)

    def _master_symbol_in_any_map(self, symbol: str) -> bool:
        """Хотя бы один включённый слейв имеет этот символ в маппинге?"""
        for sid, cfg in self._slave_cfg_by_sid.items():
            sm = cfg.get("symbol_map", {})
            if self._sym_lookup(sm, symbol) is not None:
                return True
        return False

    def _fanout(self, message: Dict, master_symbol: str):
        """Разослать команду всем включённым слейвам, у которых символ в маппинге и которые не на паузе."""
        for sid, cfg in self._slave_cfg_by_sid.items():
            if not cfg.get("enabled", True):
                continue
            sm = cfg.get("symbol_map", {})
            if self._sym_lookup(sm, master_symbol) is None:
                continue
            if self._is_paused(sid):
                continue
            in_q = self._slave_in_qs.get(sid)
            if in_q is None:
                continue
            try:
                in_q.put_nowait(message)
            except Exception:
                pass

    def _fanout_by_state(self, message_factory, master_ticket: str, state_key: str):
        """
        Разослать команду только тем слейвам, которые открыли копию этого master_ticket.
        state_key: 'positions' или 'orders'.
        message_factory(slave_ticket) -> dict
        """
        with self._lock:
            mapping = dict(self.state.get(state_key, {}).get(master_ticket, {}))
        for sid, slave_ticket in mapping.items():
            in_q = self._slave_in_qs.get(sid)
            if in_q is None:
                continue
            try:
                in_q.put_nowait(message_factory(slave_ticket))
            except Exception:
                pass

    def _handle_master_position_new(self, pos: Dict):
        ticket = pos["ticket"]
        # запоминаем объём для partial close detection
        self._master_volumes[ticket] = pos["volume"]

        # Не копировать стартовые позиции
        if ticket in self._start_position_tickets:
            return

        # Может быть это ордер, который сработал — проверим state.orders
        with self._lock:
            order_state = self.state.get("orders", {}).get(ticket)
        if order_state:
            # Ордер сработал → позиция уже открыта на слейвах от ордера.
            # Переносим в positions и удаляем из orders.
            with self._lock:
                state_pos = self.state.setdefault("positions", {})
                state_pos[ticket] = dict(order_state)
                self.state.get("orders", {}).pop(ticket, None)
                self._state_dirty = True
            self._log(f"✅ Ордер #{ticket} сработал → позиция")
            return

        # Уже скопирован?
        with self._lock:
            already = ticket in self.state.get("positions", {})
        if already:
            return

        # Fanout: open_position для каждого подходящего слейва
        self._fanout({"type": "open_position", "master_pos": pos}, pos["symbol"])

    def _handle_master_position_closed(self, ticket: str):
        self._master_volumes.pop(ticket, None)
        if ticket in self._start_position_tickets:
            self._start_position_tickets.discard(ticket)
            return
        # Fanout close по всем слейвам, у которых эта позиция открыта
        self._fanout_by_state(
            lambda st, mt=ticket: {"type": "close_position", "master_ticket": mt, "slave_ticket": st},
            ticket, "positions",
        )

    def _handle_master_position_modified(self, msg: Dict):
        ticket = msg["ticket"]
        new_volume = msg["volume"]
        old_volume = msg.get("old_volume", new_volume)

        # Partial close detection
        if old_volume > 0 and new_volume < old_volume - 1e-9:
            ratio = new_volume / old_volume
            self._fanout_by_state(
                lambda st, mt=ticket, r=ratio: {
                    "type": "partial_close", "master_ticket": mt,
                    "slave_ticket": st, "ratio": r,
                },
                ticket, "positions",
            )
            self._master_volumes[ticket] = new_volume
            return

        # SL/TP modification
        master_data = {
            "sl": msg["sl"],
            "tp": msg["tp"],
            "price_open": msg["price_open"],
            "type": msg["ptype"],
            "symbol": msg["symbol"],
        }
        self._fanout_by_state(
            lambda st, mt=ticket, md=master_data: {
                "type": "modify_position", "master_ticket": mt,
                "slave_ticket": st, "master": md,
            },
            ticket, "positions",
        )
        self._master_volumes[ticket] = new_volume

    def _handle_master_order_new(self, order: Dict):
        ticket = order["ticket"]
        # отложенный?
        pending_types = get_pending_types()
        if pending_types and order["type"] not in pending_types:
            return
        if ticket in self._start_order_tickets:
            return
        with self._lock:
            already = ticket in self.state.get("orders", {})
        if already:
            return
        self._fanout({"type": "place_order", "master_order": order}, order["symbol"])

    def _handle_master_order_gone(self, msg: Dict):
        ticket = msg["ticket"]
        became_position = msg.get("became_position", False)
        if ticket in self._start_order_tickets:
            self._start_order_tickets.discard(ticket)
            return
        if became_position:
            # Ордер сработал — будет обработан в _handle_master_position_new
            return
        # Ордер отменён — отменяем у слейвов
        self._fanout_by_state(
            lambda st, mt=ticket: {"type": "cancel_order", "master_ticket": mt, "slave_ticket": st},
            ticket, "orders",
        )
        # Удалить запись из orders
        with self._lock:
            self.state.get("orders", {}).pop(ticket, None)
            self._state_dirty = True

    # ── Синхронные операции (test_trade, close_all_positions) ──

    def test_trade(self, slave_cfg: Dict, full_config: Dict):
        """Тест копирования: пробует ВСЕ символы из маппинга, открывает BUY мин.лотом и сразу закрывает."""
        if mt5 is None:
            self._log("❌ MT5 не установлен")
            return
        sid = slave_cfg.get("id", "?")
        sname = slave_cfg.get("name", sid)
        slave_path = slave_cfg.get("path", "")
        symbol_map: Dict[str, str] = slave_cfg.get("symbol_map", {})

        if not slave_path:
            self._log(f"⚠️ [{sname}] Путь не задан")
            return
        if not is_terminal_running(slave_path):
            self._log(f"⚠️ [{sname}] Терминал не запущен")
            return
        if not symbol_map:
            self._log(f"⚠️ [{sname}] Нет символов в маппинге")
            return

        ok = mt5.initialize(path=slave_path)
        if not ok:
            self._log(f"⚠️ [{sname}] Ошибка подключения")
            return

        try:
            ti = mt5.terminal_info()
            if ti and not ti.trade_allowed:
                self._log(f"⚠️ [{sname}] Алготрейдинг ВЫКЛ — включите в терминале!")
                return

            acc = mt5.account_info()
            if acc is None:
                self._log(f"⚠️ [{sname}] Нет данных аккаунта")
                return

            self._log(f"📊 [{sname}] Аккаунт #{acc.login} ${acc.balance:.2f}")

            for master_sym, raw_slave_sym in symbol_map.items():
                slave_sym = resolve_symbol(raw_slave_sym)
                if slave_sym is None:
                    self._log(f"⚠️ [{sname}] Символ {raw_slave_sym} не найден, пробуем следующий")
                    continue
                if slave_sym != raw_slave_sym:
                    self._log(f"ℹ️ [{sname}] {raw_slave_sym} → {slave_sym}")

                if not mt5.symbol_select(slave_sym, True):
                    self._log(f"⚠️ [{sname}] Не удалось добавить {slave_sym} в Market Watch, пробуем следующий")
                    continue

                sym_info = mt5.symbol_info(slave_sym)
                if sym_info is None:
                    self._log(f"⚠️ [{sname}] symbol_info вернул None для {slave_sym}, пробуем следующий")
                    continue

                if sym_info.trade_mode != mt5.SYMBOL_TRADE_MODE_FULL:
                    self._log(
                        f"⚠️ [{sname}] {slave_sym} trade_mode={sym_info.trade_mode} "
                        f"(не FULL), пробуем следующий"
                    )
                    continue

                lot = sym_info.volume_min
                tick = mt5.symbol_info_tick(slave_sym)
                if tick is None:
                    self._log(f"⚠️ [{sname}] Нет тика для {slave_sym}, пробуем следующий")
                    continue

                filling = get_filling_mode(sym_info)
                self._log(
                    f"📊 [{sname}] {slave_sym} vol_min={lot} filling={filling} "
                    f"filling_flags={sym_info.filling_mode} "
                    f"tick_val={sym_info.trade_tick_value} "
                    f"tick_sz={sym_info.trade_tick_size}"
                )

                price = normalize_price(tick.ask, sym_info.digits)
                self._log(f"📤 [{sname}] Открываем BUY {slave_sym} lot={lot} price={price}")

                request = {
                    "action": mt5.TRADE_ACTION_DEAL,
                    "symbol": slave_sym,
                    "volume": lot,
                    "type": mt5.ORDER_TYPE_BUY,
                    "price": price,
                    "comment": "CT_TEST",
                    "type_time": mt5.ORDER_TIME_GTC,
                    "type_filling": filling,
                }

                result = try_send_order(request, self._log)
                if result is None or result.retcode != mt5.TRADE_RETCODE_DONE:
                    retcode = result.retcode if result else -1
                    comment = result.comment if result else ""
                    self._log(
                        f"❌ [{sname}] Тест FAILED: retcode={retcode} {comment}"
                    )
                    self._trade_event({
                        "time": datetime.now().strftime("%H:%M:%S"),
                        "slave": sname, "symbol": slave_sym,
                        "direction": "BUY", "lot": lot,
                        "master_ticket": "TEST", "slave_ticket": "—",
                        "success": False, "status": f"❌ retcode={retcode} {comment}",
                    })
                    continue

                ticket = result.order
                self._log(f"✅ [{sname}] Тест BUY OK → #{ticket}, закрываем...")
                self._trade_event({
                    "time": datetime.now().strftime("%H:%M:%S"),
                    "slave": sname, "symbol": slave_sym,
                    "direction": "BUY", "lot": lot,
                    "master_ticket": "TEST", "slave_ticket": str(ticket),
                    "success": True, "status": f"✅ TEST BUY #{ticket}",
                })

                time.sleep(1)

                pos = None
                all_pos = mt5.positions_get(symbol=slave_sym)
                if all_pos:
                    for p in all_pos:
                        if p.comment == "CT_TEST":
                            pos = p
                            break
                if pos is None:
                    self._log(f"ℹ️ [{sname}] Позиция не найдена — возможно уже закрыта")
                    return

                close_type = opposite_order_type(pos.type)
                close_tick = mt5.symbol_info_tick(pos.symbol)
                if close_tick is None:
                    self._log(f"⚠️ [{sname}] Нет тика для закрытия #{pos.ticket}")
                    return
                close_price = normalize_price(close_tick.bid, sym_info.digits)

                close_req = {
                    "action": mt5.TRADE_ACTION_DEAL,
                    "symbol": pos.symbol,
                    "volume": pos.volume,
                    "type": close_type,
                    "position": pos.ticket,
                    "price": close_price,
                    "comment": "CT_TEST_CLOSE",
                    "type_time": mt5.ORDER_TIME_GTC,
                    "type_filling": filling,
                }
                close_result = try_send_order(close_req, self._log)
                if close_result and close_result.retcode == mt5.TRADE_RETCODE_DONE:
                    self._log(f"✅ [{sname}] Тест закрыт #{pos.ticket} — копирование работает!")
                else:
                    rc = close_result.retcode if close_result else -1
                    cmt = close_result.comment if close_result else ""
                    self._log(f"⚠️ [{sname}] BUY открыт, закрытие retcode={rc} {cmt} — закройте вручную #{pos.ticket}")
                return

            self._log(f"❌ [{sname}] Ни один символ из маппинга не подошёл для теста")
        finally:
            mt5.shutdown()

    def close_all_positions(self, terminal_path: str, label: str = ""):
        """Закрывает все открытые позиции на аккаунте терминала."""
        if mt5 is None:
            self._log("❌ MT5 не установлен")
            return
        if not terminal_path:
            self._log(f"⚠️ [{label}] Путь не задан")
            return
        if not is_terminal_running(terminal_path):
            self._log(f"⚠️ [{label}] Терминал не запущен")
            return

        ok = mt5.initialize(path=terminal_path)
        if not ok:
            self._log(f"⚠️ [{label}] Ошибка подключения")
            return

        try:
            positions = mt5.positions_get()
            if not positions:
                self._log(f"ℹ️ [{label}] Нет открытых позиций")
                return

            self._log(f"🔴 [{label}] Закрываем {len(positions)} позиций...")
            closed = 0
            for pos in positions:
                tick = mt5.symbol_info_tick(pos.symbol)
                if tick is None:
                    self._log(f"⚠️ [{label}] Нет тика для {pos.symbol}")
                    continue
                sym_info = mt5.symbol_info(pos.symbol)
                filling = get_filling_mode(sym_info) if sym_info else mt5.ORDER_FILLING_IOC
                close_type = opposite_order_type(pos.type)
                price = tick.bid if close_type == mt5.ORDER_TYPE_SELL else tick.ask
                if sym_info:
                    price = normalize_price(price, sym_info.digits)
                request = {
                    "action": mt5.TRADE_ACTION_DEAL,
                    "symbol": pos.symbol,
                    "volume": pos.volume,
                    "type": close_type,
                    "position": pos.ticket,
                    "price": price,
                    "comment": "CT_CLOSE_ALL",
                    "type_time": mt5.ORDER_TIME_GTC,
                    "type_filling": filling,
                }
                result = try_send_order(request, self._log)
                if result and result.retcode == mt5.TRADE_RETCODE_DONE:
                    closed += 1
                else:
                    rc = result.retcode if result else -1
                    self._log(f"❌ [{label}] Ошибка закрытия #{pos.ticket} {pos.symbol} retcode={rc}")
            self._log(f"✅ [{label}] Закрыто {closed}/{len(positions)} позиций")
        finally:
            mt5.shutdown()

