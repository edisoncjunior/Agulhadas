# Arquivo - Agulhadas.py
# Faz leitura do Grupo CopiaAgulhadas / processamento / Abre ordens na Binance

import re
import asyncio
from telethon import events
from config import telegram_client, SOURCE_CHAT_ID, TARGET_CHAT_ID, FILTER_SYMBOLS, ALLOWED_SYMBOLS
from executorwebsocket import *
from structured_logger import log_event

# -------------------------------------------------
# ESCUTAR MENSAGENS
# -------------------------------------------------
def registrar_listener():
    @telegram_client.on(events.NewMessage(chats=SOURCE_CHAT_ID))
    async def forward_message(event):
        try:
            # 1️⃣ Validação mínima
            if not event.message or not event.message.text:
                print("[SKIP] Mensagem sem texto")
                return

            text = event.message.text

            # 2️⃣ INTERPRETAÇÃO DE SINAL
            sinal = interpretar_mensagem(text)

            if sinal:
                # =========================
                # 7. LOG
                # =========================
                log_event(
                    event_type="SIGNAL",
                    symbol=sinal["symbol"],
                    side=sinal["side"],
                    order_type=sinal["order_type"],
                    timeframe=sinal["timeframe"],
                    price=sinal["price"],
                    raw_message=text
                        )
                symbol = sinal["symbol"].upper()

                print(f"[SIGN] {symbol} {sinal['side']} {sinal['order_type']} {sinal['timeframe']}")

                # 3️⃣ FILTRO DE MOEDAS (para execução)
                if FILTER_SYMBOLS and symbol not in ALLOWED_SYMBOLS:
                    print(f"[SKIP] Moeda fora da lista: {symbol}")
                    print("============================================================================================")
                else:
                    await asyncio.to_thread(executar_ordem, sinal)

            # 4️⃣ PARSE PADRÃO (LOG / FORWARD)
            parsed = parse_signal_message(text)
            if not parsed:
                return

            # 5️⃣ ENCAMINHAMENTO TELEGRAM
                await telegram_client.send_message(TARGET_CHAT_ID, text)

#            print(f"[SEND] Mensagem enviada Telegram (TestAgulhada): {parsed['exchange']} {parsed['symbol']}")
#            print("============================================================================================")

        except Exception as e:
            print(f"[ERROR] Falha ao processar mensagem: {e}")



# -------------------------------------------------
# INTERPRETADOR DE MENSAGENS
# -------------------------------------------------
def interpretar_mensagem(texto):
    texto_lower = texto.lower()

    # =========================
    # 1. Corretora
    # =========================
    if texto.startswith("BINANCE:"):
        exchange = "BINANCE"
    else:
        return None  # ignorar MEXC E BYBIT

    # =========================
    # 2. Símbolo
    # =========================
    match_symbol = re.search(r'BINANCE:([A-Z0-9]+)', texto)
    if not match_symbol:
        return None

    symbol = match_symbol.group(1)

    # =========================
    # 3. Preço
    # =========================
    match_price = re.search(r'Preço:\s*([^\n]+)', texto)
    if not match_price:
        return None

    raw_price = match_price.group(1)

    price_match = re.search(r'\d+(?:\.\d+)?', raw_price)
    if not price_match:
        return None

    price = float(price_match.group())

    # =========================
    # 4. Timeframe
    # =========================
    if "15 minutos" in texto_lower:
        timeframe = "15m"
        order_type = "MARKET"
    elif "60 minutos" in texto_lower or "1h" in texto_lower:
        timeframe = "1h"
        order_type = "MARKET"
    elif "4h" in texto_lower:
        timeframe = "4h"
        order_type = "LIMIT"
    else:
        return None

    # =========================
    # 5. Tipo de sinal
    # =========================
    if "alerta de compra" in texto_lower:
        side = "LONG"

    elif "agulhada de compra" in texto_lower:
        side = "LONG"
        order_type = "LIMIT"

    elif "agulhada santa de compra" in texto_lower:
        side = "LONG"

    elif "alerta de venda" in texto_lower:
        side = "SHORT"

    elif "agulhada de venda" in texto_lower:
        side = "SHORT"
        order_type = "LIMIT"

    elif "agulhada santa de venda" in texto_lower:
        side = "SHORT"

    else:
        return None

    # =========================
    # 6. Retorno padronizado
    # =========================
    return {
        "exchange": exchange,
        "symbol": symbol,
        "side": side,
        "order_type": order_type,
        "timeframe": timeframe,
        "price": price
    }

# -------------------------------------------------
# Extrai dados estruturados da mensagem
# -------------------------------------------------
def parse_signal_message(text: str):
    text = text.strip().replace("\r", "")

    pattern = re.compile(
        r'(?P<exchange>\w+):(?P<symbol>[\w\.]+)\s+deu\s+'
        r'(?P<signal>.+?)\s+'
        r'(?:nos?|nas?)\s+'
        r'(?P<timeframe>\d+\s*(?:minutos?|H))'
        r'.*?\n+'
        r'Preço:\s*(?P<price>.+)',
        re.IGNORECASE | re.DOTALL
    )

    match = pattern.search(text)
    if not match:
        print("[SKIP] Mensagem fora do padrão")
        return None

    raw_price = match.group("price")

    price_match = re.search(r"\d+(?:\.\d+)?", raw_price)
    if not price_match:
        print(f"[SKIP] Preço inválido: {raw_price}")
        return None

    price = float(price_match.group())


    return {
        "exchange": match.group("exchange").upper(),
        "symbol": match.group("symbol").replace(".P", "").upper(),
        "signal": match.group("signal").lower(),
        "timeframe": match.group("timeframe").lower().replace(" ", ""),
        "price": price
    }

# -------------------------------------------------
# Execução principal (main)
# -------------------------------------------------
async def main():
    print("🔄 Iniciando BOT Agulhadas...")
    registrar_listener()
    await telegram_client.start()
    print("✅ Bot conectado e aguardando mensagens do Grupo CopiaAgulhada...")
    await telegram_client.run_until_disconnected()

# -------------------------------------------------
# Bootstrap
# -------------------------------------------------
if __name__ == "__main__":
    try:
        if USE_BINANCE:
            sincronizar_estado_inicial()
            iniciar_listener_ws()
            time.sleep(3)
        else:
            print("🟡 Binance desligada — executor não iniciado")

        asyncio.run(main())
    except KeyboardInterrupt:
        print("Encerrado manualmente.")
    except Exception as e:
        print(f"Erro fatal: {e}")