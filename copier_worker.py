"""
copier_worker — процессы-воркеры для копирования сделок.

Архитектура:
- master_worker: один процесс. Держит постоянное mt5.initialize(master_path),
  опрашивает positions/orders и шлёт diff-события в out_q.
- slave_worker: один процесс на слейв. Держит постоянное mt5.initialize(path),
  читает события из in_q и исполняет ордера.

Все события — простые dict, передаваемые через multiprocessing.Queue.
state.json ведётся в главном процессе (см. copier.CopyTrader).
"""

from __future__ import annotations

import os
import time
from datetime import datetime, date
from typing import Any, Dict, Optional

# MT5 импортируется внутри воркеров (в каждом процессе — своё подключение).


# ─────────────────────────────────────────────────────────────
#  Типы событий (передаются через Queue)
# ─────────────────────────────────────────────────────────────
# master → main:
#   {"type": "snapshot", "tickets": set[str]}              — стартовый снимок (один раз)
#   {"type": "master_state", "balance": float, "equity": float, "login": int, "trade_allowed": bool}
#   {"type": "position_new", "pos": {...}}                 — новая позиция у мастера
#   {"type": "position_closed", "ticket": str}             — позиция закрылась
#   {"type": "position_modified", "ticket": str, "sl": float, "tp": float, "volume": float, "price_open": float, "type": int, "symbol": str}
#   {"type": "order_new", "order": {...}}
#   {"type": "order_gone", "ticket": str, "became_position": bool}
#   {"type": "log", "msg": str}
#
# main → slave (через in_q каждого слейва):
#   {"type": "open_position", "master_pos": {...}, "balance_hint": float}
#   {"type": "close_position", "master_ticket": str, "slave_ticket": int}
#   {"type": "modify_position", "master_ticket": str, "slave_ticket": int, "master": {...}}
#   {"type": "partial_close", "master_ticket": str, "slave_ticket": int, "ratio": float}
#   {"type": "place_order", "master_order": {...}}
#   {"type": "cancel_order", "master_ticket": str, "slave_ticket": int}
#   {"type": "config_update", "slave": {...}}              — обновлённый slave_cfg
#   {"type": "stop"}
#
# slave → main:
#   {"type": "slave_state", "sid": str, "balance": float, "equity": float, "login": int, "currency": str, "trade_allowed": bool, "status": str}
#   {"type": "position_opened", "sid": str, "master_ticket": str, "slave_ticket": int, "ok": bool, "trade_info": {...}}
#   {"type": "position_closed_ack", "sid": str, "master_ticket": str, "slave_ticket": int, "ok": bool}
#   {"type": "order_placed", "sid": str, "master_ticket": str, "slave_ticket": int, "ok": bool}
#   {"type": "order_cancelled_ack", "sid": str, "master_ticket": str, "slave_ticket": int, "ok": bool}
#   {"type": "log", "sid": str, "msg": str}
#   {"type": "trade_event", "info": {...}}                 — для GUI таблицы сделок


def _now_str() -> str:
    return datetime.now().strftime("%H:%M:%S")


def _pos_to_dict(p) -> Dict[str, Any]:
    """Сериализация MT5 position в dict для кросс-процессной передачи."""
    return {
        "ticket": str(p.ticket),
        "symbol": p.symbol,
        "type": int(p.type),
        "volume": float(p.volume),
        "price_open": float(p.price_open),
        "sl": float(p.sl),
        "tp": float(p.tp),
        "comment": getattr(p, "comment", "") or "",
    }


def _order_to_dict(o) -> Dict[str, Any]:
    return {
        "ticket": str(o.ticket),
        "symbol": o.symbol,
        "type": int(o.type),
        "volume_initial": float(o.volume_initial),
        "price_open": float(o.price_open),
        "sl": float(o.sl),
        "tp": float(o.tp),
        "comment": getattr(o, "comment", "") or "",
    }


# ─────────────────────────────────────────────────────────────
#  MASTER WORKER
# ─────────────────────────────────────────────────────────────

def master_worker(master_path: str, out_q, control_q, poll_interval: float = 0.03):
    """
    Опрашивает мастер-терминал и шлёт diff-события в out_q.

    out_q: multiprocessing.Queue — события для main process.
    control_q: multiprocessing.Queue — команды от main ('stop').
    """
    try:
        import MetaTrader5 as mt5
    except Exception as e:
        try:
            out_q.put({"type": "log", "msg": f"❌ MASTER: не удалось импортировать MetaTrader5: {e}"})
        except Exception:
            pass
        return

    if not master_path:
        out_q.put({"type": "log", "msg": "❌ MASTER: путь не задан"})
        out_q.put({"type": "master_status_text", "status": "🔴 путь не задан"})
        return

    # Постоянное подключение с ретраями — терминал может только что
    # запуститься (см. _spawn_terminals_minimized в GUI) и быть ещё не готов.
    out_q.put({"type": "master_status_text", "status": "🟡 подключение…"})
    connected = False
    attempts = 0
    while not connected:
        # Проверяем команду stop между попытками
        try:
            cmd = control_q.get_nowait()
            if cmd and cmd.get("type") == "stop":
                return
        except Exception:
            pass
        if mt5.initialize(path=master_path):
            connected = True
            break
        attempts += 1
        if attempts == 1 or attempts % 10 == 0:
            out_q.put({"type": "log",
                       "msg": f"⏳ MASTER: терминал не готов (попытка {attempts})"})
            out_q.put({"type": "master_status_text",
                       "status": f"🟡 ожидание терминала… ({attempts})"})
        time.sleep(0.5)

    out_q.put({"type": "log", "msg": "🟢 MASTER: подключение установлено"})

    prev_pos: Dict[str, Dict[str, Any]] = {}
    prev_ord: Dict[str, Dict[str, Any]] = {}
    snapshot_sent = False
    last_state_push = 0.0
    state_push_interval = 0.5  # раз в полсекунды шлём account state (для UI)

    try:
        while True:
            # ── приём команд ──
            try:
                while True:
                    cmd = control_q.get_nowait()
                    if cmd and cmd.get("type") == "stop":
                        out_q.put({"type": "log", "msg": "🛑 MASTER: stop"})
                        return
            except Exception:
                pass

            t0 = time.time()

            try:
                positions = mt5.positions_get() or []
                orders = mt5.orders_get() or []
            except Exception as e:
                out_q.put({"type": "log", "msg": f"❌ MASTER: ошибка чтения: {e}"})
                time.sleep(0.5)
                continue

            # стартовый снимок — один раз
            if not snapshot_sent:
                snapshot_sent = True
                out_q.put({
                    "type": "snapshot",
                    "position_tickets": [str(p.ticket) for p in positions],
                    "order_tickets": [str(o.ticket) for o in orders],
                })
                # инициализируем prev_* стартовым состоянием
                prev_pos = {str(p.ticket): _pos_to_dict(p) for p in positions}
                prev_ord = {str(o.ticket): _order_to_dict(o) for o in orders}
                # дальше — diff
                # account state push сразу
                acc = mt5.account_info()
                ti = mt5.terminal_info()
                if acc is not None:
                    out_q.put({
                        "type": "master_state",
                        "balance": float(acc.balance),
                        "equity": float(acc.equity),
                        "login": int(acc.login),
                        "trade_allowed": bool(ti.trade_allowed) if ti else True,
                    })
                last_state_push = t0
                time.sleep(poll_interval)
                continue

            # ── позиции: diff ──
            cur_pos = {str(p.ticket): _pos_to_dict(p) for p in positions}

            # новые
            for tk, pd in cur_pos.items():
                if tk not in prev_pos:
                    out_q.put({"type": "position_new", "pos": pd})

            # закрытые
            for tk in prev_pos.keys():
                if tk not in cur_pos:
                    out_q.put({"type": "position_closed", "ticket": tk})

            # модифицированные (SL/TP/volume)
            for tk, pd in cur_pos.items():
                old = prev_pos.get(tk)
                if not old:
                    continue
                if (old["sl"] != pd["sl"] or old["tp"] != pd["tp"]
                        or abs(old["volume"] - pd["volume"]) > 1e-9):
                    out_q.put({
                        "type": "position_modified",
                        "ticket": tk,
                        "sl": pd["sl"],
                        "tp": pd["tp"],
                        "volume": pd["volume"],
                        "old_volume": old["volume"],
                        "price_open": pd["price_open"],
                        "ptype": pd["type"],
                        "symbol": pd["symbol"],
                    })

            prev_pos = cur_pos

            # ── ордера: diff ──
            cur_ord = {str(o.ticket): _order_to_dict(o) for o in orders}

            for tk, od in cur_ord.items():
                if tk not in prev_ord:
                    out_q.put({"type": "order_new", "order": od})

            for tk in prev_ord.keys():
                if tk not in cur_ord:
                    # ордер исчез — сработал или отменён.
                    # main process сам поймёт: если в cur_pos появилась позиция
                    # с тем же ticket — значит сработал.
                    became_position = tk in cur_pos
                    out_q.put({
                        "type": "order_gone",
                        "ticket": tk,
                        "became_position": became_position,
                    })

            prev_ord = cur_ord

            # ── master account state (для UI) ──
            if t0 - last_state_push >= state_push_interval:
                acc = mt5.account_info()
                ti = mt5.terminal_info()
                if acc is not None:
                    out_q.put({
                        "type": "master_state",
                        "balance": float(acc.balance),
                        "equity": float(acc.equity),
                        "login": int(acc.login),
                        "trade_allowed": bool(ti.trade_allowed) if ti else True,
                    })
                last_state_push = t0

            # ── poll ──
            elapsed = time.time() - t0
            sleep_for = poll_interval - elapsed
            if sleep_for > 0:
                time.sleep(sleep_for)
    finally:
        try:
            mt5.shutdown()
        except Exception:
            pass


# ─────────────────────────────────────────────────────────────
#  SLAVE WORKER
# ─────────────────────────────────────────────────────────────

def slave_worker(slave_cfg: Dict[str, Any], in_q, out_q, control_q,
                 state_push_interval: float = 0.5):
    """
    Один процесс на слейв. Слушает in_q и исполняет команды.
    Параллельно шлёт account state в out_q раз в 0.5 сек.
    """
    try:
        import MetaTrader5 as mt5
    except Exception as e:
        try:
            out_q.put({"type": "log", "sid": slave_cfg.get("id", "?"),
                       "msg": f"❌ SLAVE: не удалось импортировать MetaTrader5: {e}"})
        except Exception:
            pass
        return

    sid = slave_cfg.get("id", "?")
    sname = slave_cfg.get("name", sid)
    slave_path = slave_cfg.get("path", "")

    if not slave_path:
        out_q.put({"type": "log", "sid": sid, "msg": f"❌ [{sname}] путь не задан"})
        out_q.put({"type": "slave_status_text", "sid": sid, "status": "🔴 путь не задан"})
        return

    # Подключение с ретраями: терминал мог только что запуститься
    # (см. _spawn_terminals_minimized в GUI) и быть ещё не готов.
    out_q.put({"type": "slave_status_text", "sid": sid, "status": "🟡 подключение…"})
    connected = False
    attempts = 0
    while not connected:
        try:
            cmd = control_q.get_nowait()
            if cmd and cmd.get("type") == "stop":
                return
        except Exception:
            pass
        if mt5.initialize(path=slave_path):
            connected = True
            break
        attempts += 1
        if attempts == 1 or attempts % 10 == 0:
            out_q.put({"type": "log", "sid": sid,
                       "msg": f"⏳ [{sname}] терминал не готов (попытка {attempts})"})
            out_q.put({"type": "slave_status_text", "sid": sid,
                       "status": f"🟡 ожидание терминала… ({attempts})"})
        time.sleep(0.5)

    out_q.put({"type": "log", "sid": sid, "msg": f"🟢 [{sname}] подключение установлено"})

    # ── per-worker кэши и состояние ──
    cfg = dict(slave_cfg)
    rate_cache: Dict[str, tuple] = {}
    rate_ttl = 30.0
    filling_cache: Dict[str, int] = {}
    symbol_resolve_cache: Dict[str, Optional[str]] = {}
    sym_info_cache: Dict[str, Any] = {}
    sym_info_cache_ts: Dict[str, float] = {}
    SYM_INFO_TTL = 5.0  # символы меняются редко, кэш на 5 секунд

    last_state_push = 0.0

    # ── helpers (внутри воркера: используют локальный mt5) ──

    def log(msg: str):
        out_q.put({"type": "log", "sid": sid, "msg": msg})

    def sym_lookup(d: Dict[str, Any], key: str) -> Optional[Any]:
        key_upper = key.upper()
        for k, v in d.items():
            if k.upper() == key_upper:
                return v
        return None

    def resolve_symbol(name: str) -> Optional[str]:
        if name in symbol_resolve_cache:
            return symbol_resolve_cache[name]
        info = mt5.symbol_info(name)
        if info is not None:
            symbol_resolve_cache[name] = name
            return name
        # тяжёлый путь — только при кэш-промахе
        all_symbols = mt5.symbols_get()
        result = None
        if all_symbols:
            name_upper = name.upper()
            for s in all_symbols:
                if s.name.upper() == name_upper:
                    result = s.name
                    break
        symbol_resolve_cache[name] = result
        return result

    def get_sym_info(symbol: str):
        now = time.time()
        ts = sym_info_cache_ts.get(symbol, 0)
        if symbol in sym_info_cache and (now - ts) < SYM_INFO_TTL:
            return sym_info_cache[symbol]
        info = mt5.symbol_info(symbol)
        sym_info_cache[symbol] = info
        sym_info_cache_ts[symbol] = now
        return info

    def get_filling_mode(symbol_info) -> int:
        if symbol_info is None:
            return mt5.ORDER_FILLING_IOC
        filling = symbol_info.filling_mode
        if filling & 2:
            return mt5.ORDER_FILLING_FOK
        if filling & 1:
            return mt5.ORDER_FILLING_IOC
        return mt5.ORDER_FILLING_RETURN

    def normalize_price(price: float, digits: int) -> float:
        return round(price, digits)

    def opposite_order_type(t: int) -> int:
        if t == mt5.ORDER_TYPE_BUY:
            return mt5.ORDER_TYPE_SELL
        if t == mt5.ORDER_TYPE_SELL:
            return mt5.ORDER_TYPE_BUY
        return t

    def order_type_name(t: int) -> str:
        names = {
            mt5.ORDER_TYPE_BUY: "BUY",
            mt5.ORDER_TYPE_SELL: "SELL",
            mt5.ORDER_TYPE_BUY_LIMIT: "BUY_LIMIT",
            mt5.ORDER_TYPE_SELL_LIMIT: "SELL_LIMIT",
            mt5.ORDER_TYPE_BUY_STOP: "BUY_STOP",
            mt5.ORDER_TYPE_SELL_STOP: "SELL_STOP",
        }
        return names.get(t, str(t))

    def get_currency_rate(from_curr: str, to_curr: str) -> float:
        """Return FX rate to convert 1 unit of from_curr → to_curr.

        Returns 1.0 only when currencies match.  Returns 0.0 when the
        rate cannot be resolved — callers MUST treat 0.0 as "unknown",
        not as a valid rate.  Returning 1.0 as a silent fallback used
        to mask broker-suffix issues (e.g. USDJPYrfd on AMarkets) and
        produced wildly incorrect lot sizes for JPY-quoted symbols.
        """
        if not from_curr or not to_curr:
            return 0.0
        if from_curr == to_curr:
            return 1.0
        key = f"{from_curr}_{to_curr}"
        now = time.time()
        if key in rate_cache:
            val, ts = rate_cache[key]
            if now - ts < rate_ttl:
                return val
        # 1) exact pair name (no broker suffix)
        for pair in (from_curr + to_curr, to_curr + from_curr):
            info = mt5.symbol_info(pair)
            if info is None:
                continue
            mt5.symbol_select(pair, True)
            tick = mt5.symbol_info_tick(pair)
            if tick and tick.bid > 0:
                mid = (tick.bid + tick.ask) / 2
                val = (1.0 / mid) if pair == to_curr + from_curr else mid
                rate_cache[key] = (val, now)
                return val
        # 2) scan all symbols for any pair carrying both currencies
        #    (handles broker suffixes like USDJPY.r, USDJPYrfd, USDJPYm)
        all_symbols = mt5.symbols_get() or ()
        from_upper = from_curr.upper()
        to_upper = to_curr.upper()
        for s in all_symbols:
            name_upper = s.name.upper()
            if name_upper.startswith(from_upper) and to_upper in name_upper[len(from_upper):]:
                mt5.symbol_select(s.name, True)
                tick = mt5.symbol_info_tick(s.name)
                if tick and tick.bid > 0:
                    mid = (tick.bid + tick.ask) / 2
                    rate_cache[key] = (mid, now)
                    return mid
            if name_upper.startswith(to_upper) and from_upper in name_upper[len(to_upper):]:
                mt5.symbol_select(s.name, True)
                tick = mt5.symbol_info_tick(s.name)
                if tick and tick.bid > 0:
                    mid = (tick.bid + tick.ask) / 2
                    val = 1.0 / mid
                    rate_cache[key] = (val, now)
                    return val
        # 3) cross via USD (e.g. JPY→EUR = JPY→USD × USD→EUR)
        if from_curr != "USD" and to_curr != "USD":
            r1 = get_currency_rate(from_curr, "USD")
            r2 = get_currency_rate("USD", to_curr)
            if r1 > 0 and r2 > 0:
                val = r1 * r2
                rate_cache[key] = (val, now)
                return val
        return 0.0

    def calculate_lot(sym_info, sl_distance: float, risk_type: str,
                      risk_value: float, balance: float, deposit_curr: str) -> float:
        lot, _diag = calculate_lot_with_diag(
            sym_info, sl_distance, risk_type, risk_value, balance, deposit_curr,
        )
        return lot

    def calculate_lot_with_diag(sym_info, sl_distance: float, risk_type: str,
                                risk_value: float, balance: float,
                                deposit_curr: str):
        """Same as calculate_lot but also returns a diagnostic dict for
        logging.  Lets do_open_position explain WHY a lot ended up tiny."""
        diag: Dict[str, Any] = {
            "sl_distance": sl_distance,
            "tick_size": 0.0, "tick_value": 0.0,
            "tvp": 0.0, "tvl": 0.0,
            "raw_tick_value": 0.0, "fx_rate": 1.0,
            "profit_curr": "", "deposit_curr": deposit_curr,
            "sl_ticks": 0.0, "risk_amount": 0.0,
            "raw_lot": 0.0, "clamped_lot": 0.0,
            "vol_min": 0.0, "vol_max": 0.0, "vol_step": 0.0,
            "reason": "",
        }
        if sl_distance <= 0:
            diag["reason"] = "sl_distance<=0"
            return 0.0, diag
        tick_size = sym_info.trade_tick_size
        diag["tick_size"] = tick_size
        diag["vol_min"] = sym_info.volume_min
        diag["vol_max"] = sym_info.volume_max
        diag["vol_step"] = sym_info.volume_step
        tvp = abs(sym_info.trade_tick_value or 0.0)
        tvl = abs(sym_info.trade_tick_value_loss or 0.0)
        diag["tvp"], diag["tvl"] = tvp, tvl
        contract_size = sym_info.trade_contract_size or 0.0
        profit_curr = getattr(sym_info, 'currency_profit', '') or ''
        diag["profit_curr"] = profit_curr
        # Compute tick_value in deposit currency.
        #
        # contract_size × tick_size is the per-tick P/L of 1 lot,
        # expressed in the symbol's PROFIT currency — this identity
        # holds on every MT5 broker we have seen (forex, indices, CFDs).
        # MT5's trade_tick_value field, in theory, should already be in
        # the deposit currency, but on several brokers (e.g. AMarkets
        # JP225Cash, JPY-quoted) it is silently returned in profit
        # currency.  Relying on it caused Nikkei225 lots to clamp to
        # vol_min because risk was computed against JPY-sized ticks
        # while the balance was in USD (~150x too small lot).
        #
        # The safe approach used by the original copier: always derive
        # raw_tick_value ourselves, then convert profit→deposit via FX.
        # Works for any exotic profit currency (JPY, HKD, MXN, ZAR, …)
        # as long as the broker quotes a pair containing both legs.
        raw_tick_value = contract_size * tick_size if (contract_size > 0 and tick_size > 0) else 0.0
        diag["raw_tick_value"] = raw_tick_value
        tick_value = 0.0
        if raw_tick_value > 0:
            if profit_curr and deposit_curr and profit_curr != deposit_curr:
                rate = get_currency_rate(profit_curr, deposit_curr)
                diag["fx_rate"] = rate
                if rate > 0:
                    tick_value = raw_tick_value * rate
                else:
                    # Refuse to guess: returning 0 forces the caller to
                    # fall back to default_lot or skip, instead of
                    # silently using profit-currency value (which gave
                    # the 150x undersized Nikkei225 lots).
                    diag["reason"] = (
                        f"fx_rate {profit_curr}->{deposit_curr} not found; "
                        f"add the pair to Market Watch"
                    )
                    return 0.0, diag
            else:
                tick_value = raw_tick_value
        # Last-resort fallback: if we could not derive raw_tick_value
        # (some odd instrument without contract_size), fall back to
        # MT5's reported tick value.  Same-currency case only — for
        # cross-currency we already returned above.
        if tick_value <= 0:
            tick_value = max(tvp, tvl)
        diag["tick_value"] = tick_value
        if tick_size <= 0 or tick_value <= 0:
            diag["reason"] = f"tick_size={tick_size} tick_value={tick_value}"
            return 0.0, diag
        sl_ticks = sl_distance / tick_size
        diag["sl_ticks"] = sl_ticks
        if risk_type == "percent":
            risk_amount = balance * risk_value / 100.0
        else:
            risk_amount = risk_value
        diag["risk_amount"] = risk_amount
        if sl_ticks <= 0:
            diag["reason"] = "sl_ticks<=0"
            return 0.0, diag
        raw_lot = risk_amount / (sl_ticks * tick_value)
        diag["raw_lot"] = raw_lot
        vol_step = sym_info.volume_step
        lot = raw_lot
        if vol_step > 0:
            lot = round(lot / vol_step) * vol_step
        lot = max(sym_info.volume_min, min(sym_info.volume_max, lot))
        diag["clamped_lot"] = lot
        return round(lot, 8), diag

    def try_send(request: Dict) -> Any:
        symbol = request.get("symbol", "")
        cached = filling_cache.get(symbol)
        if cached is not None:
            request["type_filling"] = cached
        result = mt5.order_send(request)
        if result is not None and result.retcode == 10030:
            original = request.get("type_filling", 0)
            for alt in [mt5.ORDER_FILLING_FOK, mt5.ORDER_FILLING_IOC, mt5.ORDER_FILLING_RETURN]:
                if alt == original:
                    continue
                request["type_filling"] = alt
                result = mt5.order_send(request)
                if result is not None and result.retcode != 10030:
                    if symbol:
                        filling_cache[symbol] = alt
                    return result
            request["type_filling"] = original
        if result is not None and result.retcode != 10030 and symbol:
            filling_cache[symbol] = request.get("type_filling", 0)
        return result

    # ── helpers: бизнес-логика ──

    def get_balance() -> float:
        acc = mt5.account_info()
        return float(acc.balance) if acc else 0.0

    def get_deposit_curr() -> str:
        acc = mt5.account_info()
        return (acc.currency if acc else "") or ""

    def do_open_position(master_pos: Dict[str, Any]) -> None:
        symbol_map = cfg.get("symbol_map", {})
        raw_symbol = sym_lookup(symbol_map, master_pos["symbol"])
        if not raw_symbol:
            log(f"⚠️ [{sname}] символ мастера {master_pos['symbol']} не в маппинге")
            out_q.put({"type": "position_opened", "sid": sid,
                       "master_ticket": master_pos["ticket"], "slave_ticket": 0, "ok": False})
            return

        slave_symbol = resolve_symbol(raw_symbol)
        if slave_symbol is None:
            log(f"⚠️ [{sname}] символ {raw_symbol} не найден")
            out_q.put({"type": "position_opened", "sid": sid,
                       "master_ticket": master_pos["ticket"], "slave_ticket": 0, "ok": False})
            return

        mt5.symbol_select(slave_symbol, True)
        sym_info = get_sym_info(slave_symbol)
        if sym_info is None or sym_info.trade_mode != mt5.SYMBOL_TRADE_MODE_FULL:
            log(f"⚠️ [{sname}] {slave_symbol} недоступен для торговли")
            out_q.put({"type": "position_opened", "sid": sid,
                       "master_ticket": master_pos["ticket"], "slave_ticket": 0, "ok": False})
            return

        tick = mt5.symbol_info_tick(slave_symbol)
        if tick is None:
            log(f"⚠️ [{sname}] нет тика для {slave_symbol}")
            out_q.put({"type": "position_opened", "sid": sid,
                       "master_ticket": master_pos["ticket"], "slave_ticket": 0, "ok": False})
            return

        mtype = master_pos["type"]
        if mtype == mt5.ORDER_TYPE_BUY:
            price = tick.ask
            otype = mt5.ORDER_TYPE_BUY
        else:
            price = tick.bid
            otype = mt5.ORDER_TYPE_SELL

        digits = sym_info.digits
        price = normalize_price(price, digits)
        balance = get_balance()
        deposit_curr = get_deposit_curr()

        # расчёт лота
        m_sl = master_pos["sl"]
        m_open = master_pos["price_open"]
        if m_sl != 0.0 and m_open != 0.0:
            sl_pct = abs(m_open - m_sl) / m_open
            sl_distance = price * sl_pct
            lot = calculate_lot(
                sym_info, sl_distance,
                cfg.get("risk_type", "percent"),
                cfg.get("risk_value", 1.0),
                balance, deposit_curr,
            )
            if lot <= 0:
                lot = cfg.get("default_lot", 0.01)
                log(f"⚠️ [{sname}] расчёт=0, default={lot}")
        else:
            lot = cfg.get("default_lot", 0.01)

        if cfg.get("min_lot_mode", False):
            lot = sym_info.volume_min

        sl = 0.0
        tp = 0.0
        if m_sl != 0.0 and m_open != 0.0:
            sl_pct = abs(m_open - m_sl) / m_open
            if otype == mt5.ORDER_TYPE_BUY:
                sl = normalize_price(price * (1 - sl_pct), digits)
            else:
                sl = normalize_price(price * (1 + sl_pct), digits)
        m_tp = master_pos["tp"]
        if m_tp != 0.0 and m_open != 0.0:
            tp_pct = abs(m_open - m_tp) / m_open
            if otype == mt5.ORDER_TYPE_BUY:
                tp = normalize_price(price * (1 + tp_pct), digits)
            else:
                tp = normalize_price(price * (1 - tp_pct), digits)

        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": slave_symbol,
            "volume": lot,
            "type": otype,
            "price": price,
            "sl": sl,
            "tp": tp,
            "comment": f"CT_{master_pos['ticket']}",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": get_filling_mode(sym_info),
        }
        result = try_send(request)
        if result is None or result.retcode != mt5.TRADE_RETCODE_DONE:
            rc = result.retcode if result else -1
            cmt = result.comment if result else ""
            log(f"❌ [{sname}] ошибка открытия {slave_symbol} {order_type_name(otype)} "
                f"lot={lot:.2f} retcode={rc} {cmt}")
            out_q.put({
                "type": "trade_event",
                "info": {
                    "time": _now_str(), "slave": sname, "symbol": slave_symbol,
                    "direction": order_type_name(otype), "lot": lot,
                    "master_ticket": master_pos["ticket"], "slave_ticket": "—",
                    "success": False, "status": f"❌ retcode={rc} {cmt}",
                },
            })
            out_q.put({"type": "position_opened", "sid": sid,
                       "master_ticket": master_pos["ticket"], "slave_ticket": 0, "ok": False})
            return

        ticket = int(result.order)
        log(f"✅ [{sname}] {slave_symbol} {order_type_name(otype)} lot={lot:.2f} → #{ticket} "
            f"(мастер #{master_pos['ticket']})")
        out_q.put({
            "type": "trade_event",
            "info": {
                "time": _now_str(), "slave": sname, "symbol": slave_symbol,
                "direction": order_type_name(otype), "lot": lot,
                "master_ticket": master_pos["ticket"], "slave_ticket": str(ticket),
                "success": True, "status": f"✅ Открыт #{ticket}",
            },
        })
        out_q.put({"type": "position_opened", "sid": sid,
                   "master_ticket": master_pos["ticket"], "slave_ticket": ticket, "ok": True})

    def do_close_position(master_ticket: str, slave_ticket: int) -> None:
        positions = mt5.positions_get(ticket=slave_ticket)
        if not positions:
            out_q.put({"type": "position_closed_ack", "sid": sid,
                       "master_ticket": master_ticket, "slave_ticket": slave_ticket, "ok": True})
            return
        pos = positions[0]
        tick = mt5.symbol_info_tick(pos.symbol)
        if tick is None:
            out_q.put({"type": "position_closed_ack", "sid": sid,
                       "master_ticket": master_ticket, "slave_ticket": slave_ticket, "ok": False})
            return
        close_type = opposite_order_type(pos.type)
        price = tick.bid if close_type == mt5.ORDER_TYPE_SELL else tick.ask
        sym_info = get_sym_info(pos.symbol)
        filling = get_filling_mode(sym_info)
        if sym_info:
            price = normalize_price(price, sym_info.digits)
        req = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": pos.symbol,
            "volume": pos.volume,
            "type": close_type,
            "position": slave_ticket,
            "price": price,
            "comment": f"CT_close_{master_ticket}",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": filling,
        }
        result = try_send(req)
        ok = result is not None and result.retcode == mt5.TRADE_RETCODE_DONE
        if ok:
            log(f"✅ [{sname}] закрыта позиция #{slave_ticket} (мастер #{master_ticket})")
        else:
            rc = result.retcode if result else -1
            cmt = result.comment if result else ""
            log(f"❌ [{sname}] ошибка закрытия #{slave_ticket} retcode={rc} {cmt}")
        out_q.put({"type": "position_closed_ack", "sid": sid,
                   "master_ticket": master_ticket, "slave_ticket": slave_ticket, "ok": ok})

    def do_modify_position(master_ticket: str, slave_ticket: int, master: Dict[str, Any]) -> None:
        positions = mt5.positions_get(ticket=slave_ticket)
        if not positions:
            return
        slave_pos = positions[0]
        sym_info = get_sym_info(slave_pos.symbol)
        if sym_info is None:
            return
        digits = sym_info.digits

        new_sl = 0.0
        new_tp = 0.0
        m_sl = master["sl"]
        m_tp = master["tp"]
        m_open = master["price_open"]
        m_type = master["type"]

        if m_sl != 0.0 and m_open != 0.0:
            sl_pct = abs(m_open - m_sl) / m_open
            if m_type == 0:  # BUY
                new_sl = normalize_price(slave_pos.price_open * (1 - sl_pct), digits)
            else:
                new_sl = normalize_price(slave_pos.price_open * (1 + sl_pct), digits)
        if m_tp != 0.0 and m_open != 0.0:
            tp_pct = abs(m_open - m_tp) / m_open
            if m_type == 0:
                new_tp = normalize_price(slave_pos.price_open * (1 + tp_pct), digits)
            else:
                new_tp = normalize_price(slave_pos.price_open * (1 - tp_pct), digits)

        # сравнение, чтобы не слать лишний modify
        tick_size = sym_info.trade_tick_size or 1e-9
        if (abs(new_sl - slave_pos.sl) < tick_size and abs(new_tp - slave_pos.tp) < tick_size):
            return

        req = {
            "action": mt5.TRADE_ACTION_SLTP,
            "symbol": slave_pos.symbol,
            "position": slave_ticket,
            "volume": slave_pos.volume,
            "sl": new_sl,
            "tp": new_tp,
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": get_filling_mode(sym_info),
        }
        result = try_send(req)
        if result and result.retcode == mt5.TRADE_RETCODE_DONE:
            log(f"📝 [{sname}] SL/TP обновлены #{slave_ticket} "
                f"SL={new_sl:.{digits}f} TP={new_tp:.{digits}f}")
        else:
            rc = result.retcode if result else -1
            log(f"⚠️ [{sname}] ошибка модификации SL/TP #{slave_ticket} retcode={rc}")

    def do_partial_close(master_ticket: str, slave_ticket: int, ratio: float) -> None:
        """ratio = новый_объём_мастера / старый_объём_мастера (0 < ratio < 1)."""
        positions = mt5.positions_get(ticket=slave_ticket)
        if not positions:
            return
        slave_pos = positions[0]
        sym_info = get_sym_info(slave_pos.symbol)
        if sym_info is None:
            return
        vol_step = sym_info.volume_step
        close_vol = slave_pos.volume * (1 - ratio)
        if vol_step > 0:
            close_vol = round(close_vol / vol_step) * vol_step
        close_vol = max(sym_info.volume_min, close_vol)
        remaining = slave_pos.volume - close_vol
        if remaining < sym_info.volume_min:
            close_vol = slave_pos.volume

        if close_vol < sym_info.volume_min:
            return

        tick = mt5.symbol_info_tick(slave_pos.symbol)
        if tick is None:
            return
        close_type = opposite_order_type(slave_pos.type)
        price = tick.bid if close_type == mt5.ORDER_TYPE_SELL else tick.ask
        price = normalize_price(price, sym_info.digits)
        req = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": slave_pos.symbol,
            "volume": close_vol,
            "type": close_type,
            "position": slave_ticket,
            "price": price,
            "comment": f"CT_pclose_{master_ticket}",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": get_filling_mode(sym_info),
        }
        result = try_send(req)
        if result and result.retcode == mt5.TRADE_RETCODE_DONE:
            log(f"✅ [{sname}] частичное закрытие #{slave_ticket} vol={close_vol:.2f}")
        else:
            rc = result.retcode if result else -1
            log(f"❌ [{sname}] ошибка частичного закрытия #{slave_ticket} retcode={rc}")

    def do_place_order(master_order: Dict[str, Any]) -> None:
        symbol_map = cfg.get("symbol_map", {})
        raw_symbol = sym_lookup(symbol_map, master_order["symbol"])
        if not raw_symbol:
            log(f"⚠️ [{sname}] символ мастера {master_order['symbol']} не в маппинге")
            out_q.put({"type": "order_placed", "sid": sid,
                       "master_ticket": master_order["ticket"], "slave_ticket": 0, "ok": False})
            return
        slave_symbol = resolve_symbol(raw_symbol)
        if slave_symbol is None:
            out_q.put({"type": "order_placed", "sid": sid,
                       "master_ticket": master_order["ticket"], "slave_ticket": 0, "ok": False})
            return
        mt5.symbol_select(slave_symbol, True)
        sym_info = get_sym_info(slave_symbol)
        if sym_info is None or sym_info.trade_mode != mt5.SYMBOL_TRADE_MODE_FULL:
            out_q.put({"type": "order_placed", "sid": sid,
                       "master_ticket": master_order["ticket"], "slave_ticket": 0, "ok": False})
            return

        same_symbol = (slave_symbol == master_order["symbol"])
        balance = get_balance()
        deposit_curr = get_deposit_curr()
        m_sl = master_order["sl"]
        m_open = master_order["price_open"]
        if m_sl != 0.0 and m_open != 0.0 and same_symbol:
            sl_pct = abs(m_open - m_sl) / m_open
            sl_distance = m_open * sl_pct
            lot = calculate_lot(sym_info, sl_distance,
                                cfg.get("risk_type", "percent"),
                                cfg.get("risk_value", 1.0),
                                balance, deposit_curr)
            if lot <= 0:
                lot = cfg.get("default_lot", 0.01)
        else:
            lot = cfg.get("default_lot", 0.01)
        if cfg.get("min_lot_mode", False):
            lot = sym_info.volume_min

        digits = sym_info.digits
        price = normalize_price(m_open, digits)
        sl = normalize_price(m_sl, digits) if (m_sl != 0.0 and same_symbol) else 0.0
        tp = normalize_price(master_order["tp"], digits) if (master_order["tp"] != 0.0 and same_symbol) else 0.0

        req = {
            "action": mt5.TRADE_ACTION_PENDING,
            "symbol": slave_symbol,
            "volume": lot,
            "type": master_order["type"],
            "price": price,
            "sl": sl,
            "tp": tp,
            "comment": f"CT_{master_order['ticket']}",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": get_filling_mode(sym_info),
        }
        result = try_send(req)
        if result is None or result.retcode != mt5.TRADE_RETCODE_DONE:
            rc = result.retcode if result else -1
            cmt = result.comment if result else ""
            log(f"❌ [{sname}] ошибка ордера {slave_symbol} {order_type_name(master_order['type'])} "
                f"retcode={rc} {cmt}")
            out_q.put({"type": "order_placed", "sid": sid,
                       "master_ticket": master_order["ticket"], "slave_ticket": 0, "ok": False})
            return
        ticket = int(result.order)
        log(f"✅ [{sname}] ордер {slave_symbol} {order_type_name(master_order['type'])} "
            f"lot={lot:.2f} price={price} → #{ticket}")
        out_q.put({"type": "order_placed", "sid": sid,
                   "master_ticket": master_order["ticket"], "slave_ticket": ticket, "ok": True})

    def do_close_all() -> None:
        positions = mt5.positions_get() or []
        if not positions:
            return
        closed = 0
        for pos in positions:
            tick = mt5.symbol_info_tick(pos.symbol)
            if tick is None:
                continue
            sym_info = get_sym_info(pos.symbol)
            filling = get_filling_mode(sym_info)
            close_type = opposite_order_type(pos.type)
            price = tick.bid if close_type == mt5.ORDER_TYPE_SELL else tick.ask
            if sym_info:
                price = normalize_price(price, sym_info.digits)
            req = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": pos.symbol,
                "volume": pos.volume,
                "type": close_type,
                "position": pos.ticket,
                "price": price,
                "comment": "CT_DAILY_LIMIT",
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": filling,
            }
            result = try_send(req)
            if result and result.retcode == mt5.TRADE_RETCODE_DONE:
                closed += 1
        log(f"🔴 [{sname}] закрыто {closed}/{len(positions)} позиций (лимит убытка)")

    def do_cancel_order(master_ticket: str, slave_ticket: int) -> None:
        req = {
            "action": mt5.TRADE_ACTION_REMOVE,
            "order": slave_ticket,
            "comment": f"CT_cancel_{master_ticket}",
        }
        result = try_send(req)
        ok = result is not None and result.retcode == mt5.TRADE_RETCODE_DONE
        if ok:
            log(f"✅ [{sname}] отменён ордер #{slave_ticket} (мастер #{master_ticket})")
        else:
            rc = result.retcode if result else -1
            log(f"❌ [{sname}] ошибка отмены ордера #{slave_ticket} retcode={rc}")
        out_q.put({"type": "order_cancelled_ack", "sid": sid,
                   "master_ticket": master_ticket, "slave_ticket": slave_ticket, "ok": ok})

    def push_state():
        nonlocal last_state_push
        now = time.time()
        if now - last_state_push < state_push_interval:
            return
        last_state_push = now
        acc = mt5.account_info()
        ti = mt5.terminal_info()
        if acc is None:
            out_q.put({"type": "slave_state", "sid": sid, "balance": 0.0, "equity": 0.0,
                       "login": 0, "currency": "", "trade_allowed": False,
                       "status": "🔴 нет аккаунта"})
            return
        trade_allowed = bool(ti.trade_allowed) if ti else True
        if not trade_allowed:
            status = f"🔴 #{acc.login} алготрейдинг ВЫКЛ"
        else:
            status = f"🟢 #{acc.login} ${acc.balance:.2f}"
        out_q.put({
            "type": "slave_state", "sid": sid,
            "balance": float(acc.balance),
            "equity": float(acc.equity),
            "login": int(acc.login),
            "currency": acc.currency or "",
            "trade_allowed": trade_allowed,
            "status": status,
        })

    # ── основной цикл ──
    try:
        push_state()
        while True:
            # control
            try:
                while True:
                    cmd = control_q.get_nowait()
                    if cmd and cmd.get("type") == "stop":
                        log(f"🛑 [{sname}] stop")
                        return
            except Exception:
                pass

            # команды
            processed = False
            try:
                # блокирующее ожидание с малым таймаутом
                msg = in_q.get(timeout=0.05)
                processed = True
            except Exception:
                msg = None

            if msg is not None:
                t = msg.get("type")
                try:
                    if t == "open_position":
                        do_open_position(msg["master_pos"])
                    elif t == "close_position":
                        do_close_position(msg["master_ticket"], msg["slave_ticket"])
                    elif t == "modify_position":
                        do_modify_position(msg["master_ticket"], msg["slave_ticket"], msg["master"])
                    elif t == "partial_close":
                        do_partial_close(msg["master_ticket"], msg["slave_ticket"], msg["ratio"])
                    elif t == "place_order":
                        do_place_order(msg["master_order"])
                    elif t == "cancel_order":
                        do_cancel_order(msg["master_ticket"], msg["slave_ticket"])
                    elif t == "close_all":
                        do_close_all()
                    elif t == "config_update":
                        cfg.clear()
                        cfg.update(msg["slave"])
                    elif t == "stop":
                        log(f"🛑 [{sname}] stop")
                        return
                except Exception as e:
                    log(f"❌ [{sname}] исключение при обработке {t}: {e}")

            # периодический push state (даже без команд)
            push_state()

            if not processed:
                # короткая пауза, если очередь пустая
                time.sleep(0.01)
    finally:
        try:
            mt5.shutdown()
        except Exception:
            pass
