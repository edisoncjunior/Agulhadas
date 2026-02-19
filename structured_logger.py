import os
from datetime import datetime

LOG_DIR = "logs"
os.makedirs(LOG_DIR, exist_ok=True)

COLUMNS = [
    "timestamp",
    "event_type",
    "symbol",
    "side",
    "order_type",
    "timeframe",
    "price",
    "qty",
    "order_id",
    "status",
    "pnl",
    "roi",
    "raw_message"
]


def get_log_filename():
    data = datetime.utcnow().strftime("%Y-%m-%d")
    return os.path.join(LOG_DIR, f"trading_log_{data}.tsv")


def escrever_header_se_nao_existir(arquivo):
    if not os.path.exists(arquivo):
        with open(arquivo, "w", encoding="utf-8") as f:
            f.write("\t".join(COLUMNS) + "\n")


def log_event(
    event_type,
    symbol="",
    side="",
    order_type="",
    timeframe="",
    price="",
    qty="",
    order_id="",
    status="",
    pnl="",
    roi="",
    raw_message=""
):
    arquivo = get_log_filename()
    escrever_header_se_nao_existir(arquivo)

    timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

    linha = [
        timestamp,
        event_type,
        symbol,
        side,
        order_type,
        timeframe,
        str(price),
        str(qty),
        str(order_id),
        status,
        str(pnl),
        str(roi),
        raw_message.replace("\n", " ").replace("\r", " ")
    ]

    with open(arquivo, "a", encoding="utf-8") as f:
        f.write("\t".join(linha) + "\n")
