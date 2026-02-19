import re
import asyncio
import requests
from telethon import events
from config_web import (
    telegram_client,
    SOURCE_CHAT_ID,
    TARGET_CHAT_ID,
    EXECUTOR_URL,
    EXECUTOR_TOKEN
)

# -------------------------------------------------
# INTERPRETADOR DE MENSAGEM
# -------------------------------------------------
def interpretar_mensagem(texto):

    texto_lower = texto.lower()

    if not texto.startswith("BINANCE:"):
        return None

    match_symbol = re.search(r'BINANCE:([A-Z0-9]+)', texto)
    if not match_symbol:
        return None

    symbol = match_symbol.group(1)

    match_price = re.search(r'Preço:\s*([^\n]+)', texto)
    if not match_price:
        return None

    raw_price = match_price.group(1)
    price_match = re.search(r'\d+(?:\.\d+)?', raw_price)
    if not price_match:
        return None

    price = float(price_match.group())

    # Timeframe
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

    # Side
    if "compra" in texto_lower:
        side = "LONG"
    elif "venda" in texto_lower:
        side = "SHORT"
    else:
        return None

    return {
        "exchange": "BINANCE",
        "symbol": symbol,
        "side": side,
        "order_type": order_type,
        "timeframe": timeframe,
        "price": price
    }

# -------------------------------------------------
# ENVIAR PARA EXECUTOR LOCAL
# -------------------------------------------------
def enviar_para_executor(sinal):

    try:
        response = requests.post(
            EXECUTOR_URL,
            json=sinal,
            headers={"Authorization": EXECUTOR_TOKEN},
            timeout=10
        )

        print(f"[WEBHOOK] Status: {response.status_code}")

    except Exception as e:
        print(f"[ERRO] Falha ao enviar webhook: {e}")

# -------------------------------------------------
# LISTENER TELEGRAM
# -------------------------------------------------
def registrar_listener():

    @telegram_client.on(events.NewMessage(chats=SOURCE_CHAT_ID))
    async def handler(event):

        if not event.message or not event.message.text:
            return

        texto = event.message.text

        sinal = interpretar_mensagem(texto)

        if not sinal:
            return

        print(f"[SIGNAL] {sinal['symbol']} {sinal['side']} {sinal['timeframe']}")

        # envia para executor local
        await asyncio.to_thread(enviar_para_executor, sinal)

        # opcional: forward para grupo teste
        if TARGET_CHAT_ID:
            await telegram_client.send_message(TARGET_CHAT_ID, texto)

# -------------------------------------------------
# MAIN
# -------------------------------------------------
async def main():

    print("🚀 Iniciando módulo WEB (Telegram → Webhook)")
    registrar_listener()
    await telegram_client.start()
    print("✅ Bot conectado e escutando sinais...")
    await telegram_client.run_until_disconnected()

if __name__ == "__main__":
    asyncio.run(main())
