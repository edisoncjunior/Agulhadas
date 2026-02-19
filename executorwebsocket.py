# executor.py (corrigido) versão funcional em 14/02/2026
# Recebe sinal (Grupo CopiaAgulhada) com arquivo coletor, depois decodifica com arquivo parser
# Arquivo config traz todas as configurações (Telegram + Binance + estrategias)
# Suporta simulação (DRY_RUN) e USE_BINANCE=False
# Filtra Simbolos/moedas por nome e por valor
# Bloqueia ALERTAS no mesmo candle
"""
Executor de ordens Binance (Futures) - Estratégia:
- Ordens 15min são MARKET
- Ordens 1h e 4h são LIMT com preço baseado em MM8
- Contabiliza posições abertas + ordens LIMIT pendentes (modo HEDGE) -> Calcula Preco e Qtd (stepSize / tickSize) -> Cria Ordem
- Monitora a abertura da Ordem -> Cria TP Parcial
- Monitora criação de TP Parcial -> Cria Trailing STOP (TS) e -> Cria BREAK EVEN (coloca SL no preço de entrada)

"""

import math
import time
import requests
import threading
import websocket
import json

from datetime import datetime
from collections import defaultdict
from structured_logger import log_event
from config import (
    binance_client,
    MAX_USDT,
    LEVERAGE,
    MAX_PRECO_PERMITIDO,
    MAX_POSICOES_ABERTAS,
    MAX_LONGS,
    MAX_SHORTS,
    MARGIN_TYPE,
    DRY_RUN,
    USE_BINANCE,
    TRAILING_CALLBACK_RATE,
    TRAILING_ACTIVATION_PERCENT,
    TP_PARCIAL_PERCENT,
    TP_PARCIAL_QTY,
    SYMBOL_FILTERS
)

# ==========================================================
# 📡 CONTROLE DE POSIÇÕES EM MONITORAMENTO (EVENTOS)
# ==========================================================
executed_signals = {}
estado_posicoes = {}
estado_ordens = {}
ordens_mm8 = {}

# ==========================================================
# 🔐 LOCK POR SYMBOL (evita execução concorrente)
# ==========================================================
symbol_locks = defaultdict(threading.Lock)

# ==========================================================
# 📦 CACHE RUNTIME DE FILTROS (evita chamadas repetidas)
# ==========================================================
_runtime_filters = {}

def get_symbol_filters(symbol):
    """
    Retorna (tick_size, step_size)
    Prioridade:
    1. config.SYMBOL_FILTERS
    2. cache runtime
    3. Binance (fallback único)
    """

    # 1️⃣ CONFIG
    if symbol in SYMBOL_FILTERS:
        tick = float(SYMBOL_FILTERS[symbol]["TICK_SIZE"])
        step = float(SYMBOL_FILTERS[symbol]["STEP_SIZE"])
        return tick, step

    # 2️⃣ CACHE
    if symbol in _runtime_filters:
        return _runtime_filters[symbol]

    # 3️⃣ BINANCE
    info = binance_client.futures_exchange_info()

    for s in info["symbols"]:
        if s["symbol"] == symbol:
            tick = None
            step = None

            for f in s["filters"]:
                if f["filterType"] == "PRICE_FILTER":
                    tick = float(f["tickSize"])
                if f["filterType"] == "LOT_SIZE":
                    step = float(f["stepSize"])

            if tick and step:
                _runtime_filters[symbol] = (tick, step)
                return tick, step

    raise Exception(f"Filtros não encontrados para {symbol}")

# ==========================================================
# 📡 WEBSOCKET USER DATA STREAM
# ==========================================================
def iniciar_user_stream():
    try:
        resp = binance_client.futures_stream_get_listen_key()

        # compatível com qualquer versão da lib
        listen_key = resp["listenKey"] if isinstance(resp, dict) else resp

        print(f"[WS] listenKey obtido")

        threading.Thread(
            target=renovar_listen_key,
            args=(listen_key,),
            daemon=True
        ).start()

        threading.Thread(
            target=rodar_ws,
            args=(listen_key,),
            daemon=True
        ).start()

    except Exception as e:
        print(f"[ERRO] WebSocket: {e}")

def iniciar_listener_ws():
    threading.Thread(
        target=iniciar_user_stream,
        daemon=True
    ).start()

def rodar_ws(listen_key):
    url = f"wss://fstream.binance.com/ws/{listen_key}"

    ws = websocket.WebSocketApp(
        url,
        on_message=on_message,
        on_error=lambda ws, err: print("[WS ERRO]", err),
        on_close=lambda ws: print("[WS] fechado"),
    )

    while True:
        try:
            ws.run_forever()
        except Exception as e:
            print("Reconectando WS", e)

        print("[WS] Reconectando em 5s...")
        time.sleep(5)


# ==========================================================
# 🔢 Atualização de posição pelo WebSocket
# ==========================================================
def atualizar_posicoes(account_data):

    for pos in account_data["P"]:
        symbol = pos["s"]
        side = pos["ps"]
        qty = float(pos["pa"])
        entry = float(pos["ep"])

        chave = f"{symbol}_{side}"

        # posição fechada
        if qty == 0:
            estado_posicoes.pop(chave, None)
            continue

        estado_anterior = estado_posicoes.get(chave)

        # posição nova detectada
        if not estado_anterior:
            print(f"[EVENTO] Nova posição confirmada {symbol} {entry}")

            enviar_tp_parcial(symbol, side, abs(qty), entry)

            estado_posicoes[chave] = {
                "qty": abs(qty),
                "entry": entry,
                "tp_enviado": True,
                "trailing_enviado": False
            }
            # LOG
            log_event(
                event_type="TP_SENT",
                symbol=symbol,
                side=side,
                price=avg_price,
                qty=executed_qty
            )


        else:
            # apenas atualizar dados
            estado_posicoes[chave]["qty"] = abs(qty)
            estado_posicoes[chave]["entry"] = entry

# ==========================================================
# 🔢 Tratamento de ordens (sem consultar posição)
# ==========================================================
def tratar_ordem(order_data):

    symbol = order_data["s"]
    side = order_data["ps"]
    status = order_data["X"]
    avg_price = float(order_data.get("ap", 0))
    executed_qty = float(order_data.get("z", 0))
    order_id = order_data["i"]

    chave = f"{symbol}_{side}"

    # Entrada executada
    if status == "FILLED" and chave not in estado_posicoes:
        with symbol_locks[symbol]:
            print(f"[EVENTO] Entrada executada {symbol}")

            # remover do controle MM8
            for k in list(ordens_mm8.keys()):
                if k.startswith(f"{symbol}_{side}_"):
                    ordens_mm8.pop(k, None)

            # LOG
            log_event(
                event_type="ORDER_FILLED",
                symbol=symbol,
                side=side,
                price=avg_price,
                qty=executed_qty,
                order_id=order_data["i"],
                status=status
            )

            estado_posicoes[chave] = {
                "qty": abs(executed_qty),
                "entry": avg_price,
                "tp_enviado": True,
                "trailing_enviado": False
            }

            # Enviar TP parcial
            enviar_tp_parcial(symbol, side, executed_qty, avg_price)
            # LOG
            log_event(
                event_type="TP_SENT",
                symbol=symbol,
                side=side,
                price=avg_price,
                qty=executed_qty
            )

    # Parcial executado
    elif status == "PARTIALLY_FILLED":
        pos = estado_posicoes.get(chave)

        if not pos:
            return
        # LOG
        log_event(
            event_type="PARTIALLY_FILLED",
            symbol=symbol,
            side=side,
            price=avg_price,
            qty=executed_qty,
            status=status
        )

        if not pos.get("trailing_enviado"):
            print(f"[EVENTO] Parcial executada {symbol}")
            mover_stop_para_lucro(symbol, side, pos["entry"], pos["qty"])
            enviar_trailing_stop(symbol, side, pos["entry"], pos["qty"])
            # LOG
            log_event(
                event_type="TRAILING_SENT",
                symbol=symbol,
                side=side
            )

            pos["trailing_enviado"] = True

# ==========================================================
# 🔢 Listener principal
# ==========================================================
def on_message(ws, message):

    data = json.loads(message)

    evento = data.get("e")

    if evento == "ACCOUNT_UPDATE":
        atualizar_posicoes(data["a"])

    elif evento == "ORDER_TRADE_UPDATE":
        tratar_ordem(data["o"])

# ==========================================================
# 🔢 Sincronizar estado
# ==========================================================
def sincronizar_estado_inicial():
    positions = binance_client.futures_position_information()

    for p in positions:
        qty = float(p["positionAmt"])
        if qty == 0:
            continue

        symbol = p["symbol"]
        entry = float(p["entryPrice"])
        side = "LONG" if qty > 0 else "SHORT"

        estado_posicoes[f"{symbol}_{side}"] = {
            "qty": abs(qty),
            "entry": entry,
            "tp_enviado": True,
            "trailing_enviado": False
        }
# ==========================================================
# 🔢 Sincronizar MM8
# ==========================================================
def sincronizar_ordens_mm8():
    open_orders = binance_client.futures_get_open_orders()

    for o in open_orders:
        if o["type"] == "LIMIT" and not o.get("reduceOnly"):
            symbol = o["symbol"]
            side = o["positionSide"]

            # você precisa saber timeframe (ver nota abaixo)

# ==========================================================
# 🔢 NORMALIZAÇÃO
# ==========================================================
def get_precision(value): # V1
    s = f"{value:.10f}".rstrip("0")
    return len(s.split(".")[1]) if "." in s else 0

def normalize_qty(qty, step):
    precision = get_precision(step)
    qty = math.floor(qty / step) * step
    return float(f"{qty:.{precision}f}")

def normalize_price(price, tick):
    precision = get_precision(tick)
    price = math.floor(price / tick) * tick
    return float(f"{price:.{precision}f}")

# ==========================================================
# 💰 QUANTIDADE
# ==========================================================
def calcular_quantidade(symbol, price):
    notional = MAX_USDT * LEVERAGE
    qty_bruta = notional / price
    tick, step = get_symbol_filters(symbol)
    qty = normalize_qty(qty_bruta, step)
#    print(f"[QTY] Notional={notional:.4f} Qty={qty:.4f}")
    return qty

# ==========================================================
# 💲 PREÇO ATUAL
# ==========================================================
def preco_atual(symbol):
    return float(binance_client.futures_mark_price(symbol=symbol)["markPrice"])

# ==========================================================
# PREÇO PERMITIDO
# ==========================================================
def preco_permitido(symbol):
    try:
        price = preco_atual(symbol)
        if price <= MAX_PRECO_PERMITIDO:
#            print(f"[OK] Preço permitido {symbol}: {price}")
            return True, price
        print(f"[SKIP] {symbol} ignorado — preço alto: {price}")
        return False, price
    except Exception as e:
        print(f"[ERROR] Falha ao consultar preço de {symbol}: {e}")
        return False, None

# ==========================================================
# 📊 MM8
# ==========================================================
TF_MAP = {
    "15m": binance_client.KLINE_INTERVAL_15MINUTE,
    "1h": binance_client.KLINE_INTERVAL_1HOUR,
    "4h": binance_client.KLINE_INTERVAL_4HOUR
}

def calcular_mm8(symbol, timeframe):
    klines = binance_client.futures_klines(
        symbol=symbol,
        interval=TF_MAP[timeframe],
        limit=9
    )

    closes = [float(k[4]) for k in klines]
    mm8 = sum(closes[-8:]) / 8

    tick, _ = get_symbol_filters(symbol)
    mm8n = normalize_price(mm8, tick)

    return mm8n

# ==========================================================
# ⚙ CONFIGURAÇÕES BINANCE
# ==========================================================
def set_leverage(symbol):
    try:
        binance_client.futures_change_leverage(symbol=symbol, leverage=LEVERAGE)
    except Exception:
        pass

def set_margin_type(symbol):
    try:
        binance_client.futures_change_margin_type(symbol=symbol, marginType=MARGIN_TYPE)
    except Exception:
        pass
# ==========================================================
# ⚙ CONTAR POSICOES (LONG / SHORT / TOTAL)
# ==========================================================
def contar_posicoes_local():

    resultado = {
        "total": 0,
        "long": 0,
        "short": 0,
        "por_symbol": {}
    }

    for chave, pos in estado_posicoes.items():
        symbol, side = chave.split("_")

        if symbol not in resultado["por_symbol"]:
            resultado["por_symbol"][symbol] = {"long":0,"short":0}

        resultado["total"] += 1

        if side == "LONG":
            resultado["long"] += 1
            resultado["por_symbol"][symbol]["long"] += 1
        else:
            resultado["short"] += 1
            resultado["por_symbol"][symbol]["short"] += 1

    return resultado


def contar_ordens_entrada():

#    Conta apenas ordens que realmente ABREM posição. (Ignora TP / SL / Trailing.)

    resultado = {
        "total": 0,
        "long": 0,
        "short": 0,
        "por_symbol": {}
    }

    try:
        open_orders = binance_client.futures_get_open_orders()

        for o in open_orders:

            # Apenas ordens ativas
            if o["status"] not in ("NEW", "PARTIALLY_FILLED"):
                continue

            # Ignorar ordens de saída
            if o.get("reduceOnly"):
                continue

            symbol = o["symbol"]
            pos_side = o.get("positionSide")

            if symbol not in resultado["por_symbol"]:
                resultado["por_symbol"][symbol] = {"long": 0, "short": 0}

            if pos_side == "LONG":
                resultado["long"] += 1
                resultado["por_symbol"][symbol]["long"] += 1
            elif pos_side == "SHORT":
                resultado["short"] += 1
                resultado["por_symbol"][symbol]["short"] += 1

            resultado["total"] += 1

        return resultado

    except Exception as e:
        print(f"[ERRO] contar_ordens_entrada: {e}")
        return resultado

def contar_estado_atual():

#    Consolida: posições abertas e ordens de entrada abertas

    pos = contar_posicoes_local()
    ords = contar_ordens_entrada()

    resultado = {
        "total": pos["total"] + ords["total"],
        "long": pos["long"] + ords["long"],
        "short": pos["short"] + ords["short"],
        "por_symbol": {}
    }

    symbols = set(list(pos["por_symbol"].keys()) + list(ords["por_symbol"].keys()))

    for s in symbols:
        resultado["por_symbol"][s] = {
            "long": pos["por_symbol"].get(s, {}).get("long", 0) +
                    ords["por_symbol"].get(s, {}).get("long", 0),

            "short": pos["por_symbol"].get(s, {}).get("short", 0) +
                     ords["por_symbol"].get(s, {}).get("short", 0)
        }

    return resultado

def pode_abrir_nova_ordem(symbol, side):

    estado = contar_estado_atual()

    print(f"[DEBUG] TOTAL={estado['total']} LONG={estado['long']} SHORT={estado['short']}")

    if estado["total"] >= MAX_POSICOES_ABERTAS:
        print("[SKIP] Limite total atingido")
        return False

    if side == "LONG" and estado["long"] >= MAX_LONGS:
        print("[SKIP] Limite LONG atingido")
        return False

    if side == "SHORT" and estado["short"] >= MAX_SHORTS:
        print("[SKIP] Limite SHORT atingido")
        return False

    # trava por símbolo
    sym_data = estado["por_symbol"].get(symbol, {"long": 0, "short": 0})

    if side == "LONG" and sym_data["long"] > 0:
        print(f"[SKIP] Já existe LONG ativo em {symbol}")
        return False

    if side == "SHORT" and sym_data["short"] > 0:
        print(f"[SKIP] Já existe SHORT ativo em {symbol}")
        return False

    return True

def ja_existe_posicao(symbol, side):
    chave = f"{symbol}_{side}"
    return chave in estado_posicoes


def renovar_listen_key(listen_key):
    while True:
        try:
            binance_client.futures_stream_keepalive(listen_key)
        except Exception as e:
            print(f"[ERRO] keepalive: {e}")
        time.sleep(1800)

# ==========================================================
# 📌 EXECUTOR PRINCIPAL
# ==========================================================
def candle_id(timeframe):
    now = datetime.utcnow()
    if timeframe == "15m":
        return f"{now.year}{now.month}{now.day}{now.hour}{now.minute//15}"
    if timeframe == "1h":
        return f"{now.year}{now.month}{now.day}{now.hour}"
    if timeframe == "4h":
        return f"{now.year}{now.month}{now.day}{now.hour//4}"

def executar_ordem(sinal: dict):
    symbol = sinal["symbol"]
    side = sinal["side"]
    timeframe = sinal["timeframe"]
    order_type = sinal["order_type"]

    with symbol_locks[symbol]:

        # ==================================================
        # 🔒 CONTROLE POR PREÇO
        # ==================================================
        permitido, _ = preco_permitido(symbol)
        if not permitido:
            print(f"[SKIP] Preço não permitido")
            return

        # ==================================================
        # 🔒 CONTROLE POR VELA
        # ==================================================
        vela = candle_id(timeframe)
        chave = f"{symbol}_{side}_{timeframe}"

        if executed_signals.get(chave) == vela:
            print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} [SKIP] Sinal já executado nesta vela.")
            return

        # ==================================================
        # 📊 CONTROLE DE POSIÇÕES E ORDENS
        # ==================================================
        if ja_existe_posicao(symbol, side):
            print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} [SKIP] Já existe posição neste lado")
            print("============================================================================================")
            return

        if not pode_abrir_nova_ordem(symbol, side):
            print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} [SKIP] Não pode abrir nova ordem [QUANTIDADE DE POSIÇÃO EXCEDIDA]")
            print("============================================================================================")
            return

        # ==================================================
        # 💰 CÁLCULOS
        # ==================================================
        if not USE_BINANCE or DRY_RUN:
            print("[SIMULADO]")
            return

        set_margin_type(symbol)
        set_leverage(symbol)

        tick, step = get_symbol_filters(symbol)
        price = calcular_mm8(symbol, timeframe)
        price = normalize_price(price, tick)
        qty = calcular_quantidade(symbol, price)
        qty = normalize_qty(qty, step)

        params = dict(
            symbol=symbol,
            side="BUY" if side == "LONG" else "SELL",
            positionSide=side,
            type=order_type,
            quantity=qty
        )

        if order_type == "LIMIT":
            client_id = f"MM8_{symbol}_{side}_{timeframe}_{vela}"
            params["price"] = price
            params["timeInForce"] = "GTC"

        # ================================
        # 🚀 ENVIO DA ORDEM
        # ================================
        try:
            order = binance_client.futures_create_order(**params)
            print(f"[ORDEM] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} {symbol} {side} QTY={qty} PRICE_MM8={price}")

            if order_type == "LIMIT":
                chave_mm8 = f"{symbol}_{side}_{timeframe}"

                ordens_mm8[chave_mm8] = {
                    "order_id": order["orderId"],
                    "price": price,
                    "vela_origem": vela,
                    "candles_passados": 0
                }

            # LOG
            log_event(
                event_type="ORDER_SENT",
                symbol=symbol,
                side=side,
                order_type=order_type,
                price=price,
                qty=qty,
                order_id=order.get("orderId"),
                status="NEW"
            )

        except Exception as e:
            print(f"[ERROR] {e}")


        # ================================
        # 🔐 MARCAR COMO EXECUTADO
        # ================================
        executed_signals[chave] = vela

# ==========================================================
# 🎯 TP PARCIAL
# ==========================================================
def enviar_tp_parcial(symbol, side, qty, entry):
    try:
        # ================================
        # OBTER FILTROS UMA VEZ
        # ================================
        tick, step = get_symbol_filters(symbol)

        # ================================
        # TP1
        # ================================
        tp_qty = qty * TP_PARCIAL_QTY

        if tp_qty <= 0:
            print("[SKIP] TP qty ficou zero")
            return

        tp_qty = normalize_qty(tp_qty, step)

        if side == "LONG":
            tp_price = entry * (1 + TP_PARCIAL_PERCENT/100)
            close_side = "SELL"
        else:
            tp_price = entry * (1 - TP_PARCIAL_PERCENT/100)
            close_side = "BUY"

        tp_price = normalize_price(tp_price, tick)

        binance_client.futures_create_order(
            symbol=symbol,
            side=close_side,
            positionSide=side,
            type="LIMIT",
            price=tp_price,
            quantity=tp_qty,
            timeInForce="GTC"
        )

        print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} [TP1] {symbol} Parcial enviado {tp_price} qty {tp_qty}")

        # ================================
        # TP2
        # ================================
        restante = qty - tp_qty
        tp2_qty = restante

        if tp2_qty <= 0:
            return

        tp2_qty = normalize_qty(tp2_qty, step)

        if side == "LONG":
            tp2_price = entry * (1 + TP_PARCIAL_PERCENT * 2 / 100)
        else:
            tp2_price = entry * (1 - TP_PARCIAL_PERCENT * 2 / 100)

        tp2_price = normalize_price(tp2_price, tick)

        if tp2_qty > 0:
            binance_client.futures_create_order(
                symbol=symbol,
                side=close_side,
                positionSide=side,
                type="LIMIT",
                price=tp2_price,
                quantity=tp2_qty,
                timeInForce="GTC"
            )

            print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} [TP2] {symbol} Parcial enviado {tp2_price} qty={tp2_qty}")

    except Exception as e:
        print(f"[ERRO] TP: {e}")


# ==========================================================
# 🔁 TRAILING STOP
# ==========================================================
def enviar_trailing_stop(symbol, side, qty, entry):
    try:
        if side == "LONG":
            activation = entry * (1 + TRAILING_ACTIVATION_PERCENT/100)
            close_side = "SELL"
        else:
            activation = entry * (1 - TRAILING_ACTIVATION_PERCENT/100)
            close_side = "BUY"

        tick, step = get_symbol_filters(symbol)
        activation = normalize_price(activation, tick)
        qty = normalize_qty(qty, step)

        binance_client.futures_create_order(
            symbol=symbol,
            side=close_side,
            positionSide=side,
            type="TRAILING_STOP_MARKET",
            quantity=qty,
            activationPrice=activation,
            callbackRate=TRAILING_CALLBACK_RATE,
            workingType="MARK_PRICE"
        )

        print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} [TRAIL] {symbol} Enviado {activation} qty {qty}")

    except Exception as e:
        print(f"[ERRO] Trailing: {e}")

#============================================================
# 🛡 STOP em +10% lucro
# ==========================================================
def mover_stop_para_lucro(symbol, side, entry_price, qty_restante):
    try:
        mark_price = float(client.futures_mark_price(symbol=symbol)["markPrice"])

        if side == "LONG":
            stop_price = entry_price * 1.002  # 10% lucro no LONG com 50X de alavancagem
            stop_price = min(stop_price, mark_price * 0.999)
            close_side = "SELL"
        else:
            stop_price = entry_price * 0.998  # 10% lucro no SHORT
            stop_price = max(stop_price, mark_price * 1.001)
            close_side = "BUY"

        tick = get_tick_size(symbol)
        step = get_step_size(symbol)

        stop_price = normalize_price(stop_price, tick)
        qty_restante = normalize_qty(qty_restante, step)

        binance_client.futures_create_order(
            symbol=symbol,
            side=close_side,
            positionSide=side,
            type="STOP_MARKET",
            stopPrice=stop_price,
            quantity=qty_restante,
            workingType="MARK_PRICE",
        )

        print(f"[STOP LUCRO] {symbol} novo stop em {stop_price}")

    except Exception as e:
        print(f"[ERRO STOP LUCRO]: {e}")

