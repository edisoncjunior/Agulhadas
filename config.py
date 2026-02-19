# Arquivo 3 – config.py
# Lê variáveis de ambiente (.env) para Telegram e Binance.
# Inicializa clientes: TelegramClient e binance_client.
# Define parâmetros fixos da estratégia, como:
# LEVERAGE, MAX_USDT, MAX_POSICOES_ABERTAS, MAX_SHORTS/LONGS.
# DRY_RUN e USE_BINANCE para simulação/desligar Binance.
# Moedas permitidas (ALLOWED_SYMBOLS) e filtro (FILTER_SYMBOLS).
# Resumo de função: Configuração central do bot, clientes, parâmetros da estratégia e variáveis de ambiente.

import os
import ccxt
from telethon.sessions import StringSession
from telethon import TelegramClient, events 
from binance.client import Client
from dotenv import load_dotenv

# -------------------------------------------------
# Carrega variáveis de ambiente (.env local)
# -------------------------------------------------
try:
    if os.path.exists(".env"):
        load_dotenv()
except ImportError:
    pass

# -------------------------------------------------
# Variáveis de ambiente (obrigatórias)
# -------------------------------------------------
# Telegram
API_ID = int(os.environ.get("API_ID"))
API_HASH = os.environ.get("API_HASH")
SESSION_STRING = os.environ.get("TELEGRAM_SESSION_STRING")
SOURCE_CHAT_ID = int(os.environ.get("SOURCE_CHAT_ID"))
TARGET_CHAT_ID = int(os.environ.get("TARGET_CHAT_ID"))

# Binance
BINANCE_API_KEY = os.environ.get("BINANCE_API_KEY")
BINANCE_API_SECRET = os.environ.get("BINANCE_API_SECRET")

USE_BINANCE = os.getenv("USE_BINANCE", "false").lower() == "true" # permite desligar Binance sem mexer no código
DRY_RUN = False      # True = simula | False = envia ordem real
FILTER_SYMBOLS = True  # True = filtra | False = envia tudo

# -------------------------------------------------
# Validações obrigatórias
# -------------------------------------------------
if not API_ID or not API_HASH:
    raise RuntimeError("API_ID e API_HASH não definidos")

if not SOURCE_CHAT_ID or not TARGET_CHAT_ID:
    raise RuntimeError("SOURCE_CHAT_ID ou TARGET_CHAT_ID não definidos")

if not SESSION_STRING:
    raise RuntimeError(
        "TELEGRAM_SESSION_STRING não definida. "
        "Execute gerar_sessao.py primeiro."
    )

# -------------------------------------------------
# Cliente Telegram
# -------------------------------------------------
telegram_client = TelegramClient(
    StringSession(SESSION_STRING),
    API_ID,
    API_HASH
)

# =========================
# BINANCE CLIENT
# =========================
binance_client = Client(BINANCE_API_KEY, BINANCE_API_SECRET, {"timeout": 30})
if not os.getenv("BINANCE_API_KEY") or not os.getenv("BINANCE_API_SECRET"):
    raise RuntimeError("BINANCE_API_KEY ou BINANCE_API_SECRET não definidos")


# -------------------------------------------------
# PARÂMETROS DA ESTRATÉGIA (CONFIGURÁVEIS)
# -------------------------------------------------

LEVERAGE = int(os.getenv("LEVERAGE", 50))
MAX_USDT = float(os.getenv("MAX_USDT", 1.5))
MAX_PRECO_PERMITIDO = float(os.getenv("MAX_PRECO_PERMITIDO", 2.10)) # seleciona apenas moedas baratas
MAX_POSICOES_ABERTAS = int(os.getenv("MAX_POSICOES_ABERTAS", 8))
MAX_SHORTS = int(os.getenv("MAX_SHORTS", 5))
MAX_LONGS = int(os.getenv("MAX_LONGS", 3))
MARGIN_TYPE = os.getenv("MARGIN_TYPE", "CROSSED")
HEDGE_MODE = os.getenv("HEDGE_MODE", "true").lower() == "true"

# SL e TP
TP_PARCIAL_PERCENT = float(os.getenv("TP_PARCIAL_PERCENT", 1.0))  # multiplicado pela alavancagem (1.0 com 25X = 25%)
TP_PARCIAL_QTY = float(os.getenv("TP_PARCIAL_QTY", 0.5)) # retirada parcial de moedas (0.5 = 50%)


# Trailing
TRAILING_CALLBACK_RATE = float(os.getenv("TRAILING_CALLBACK_RATE", 1.0)) # percentual (1.0 = 1%)
TRAILING_ACTIVATION_PERCENT = float(os.getenv("TRAILING_ACTIVATION_PERCENT", 5.0)) # 1% de variação do preço (equivale a 25% considerando 25x)

ALLOWED_SYMBOLS = {
    "1INCHUSDT", "ADAUSDT", "ALGOUSDT", "ALICEUSDT", "APEUSDT", "APTUSDT", "ARBUSDT", 
    "ARPAUSDT", "ARUSDT", "ATAUSDT", "ATOMUSDT", "AXSUSDT", 
    "BANDUSDT", "BATUSDT", "CELOUSDT", "CHZUSDT", "COTIUSDT", "CYBERUSDT",
    "DOTUSDT", "DUSKUSDT", "DYDXUSDT", "ENAUSDT", "ENJUSDT",
    "FETUSDT", "FILUSDT", "FOLKSUSDT", "GALAUSDT", "GMTUSDT", "GRTUSDT",
    "HBARUSDT", "HOTUSDT", "ICPUSDT", "ICXUSDT", "IMXUSDT", "IOTXUSDT",
    "JASMYUSDT", "JTOUSDT", "JUPUSDT", "KAVAUSDT", "KNCUSDT",
    "LDOUSDT", "LPTUSDT", "LQTYUSDT", "LRCUSDT",
    "MASKUSDT", "MTLUSDT", "NEARUSDT", "OGNUSDT", "ONDOUSDT", "ONEUSDT", "OPUSDT",
    "PENDLEUSDT", "PEOPLEUSDT", "QTUMUSDT",
    "RLCUSDT", "RSRUSDT", "RUNEUSDT", "SANDUSDT", "SEIUSDT", "SFPUSDT",
    "SKLUSDT", "SNXUSDT", "STORJUSDT", "SUIUSDT", "SUSHIUSDT",
    "THETAUSDT", "TONUSDT", "TRXUSDT",
    "VETUSDT", "WLFIUSDT", "WOOUSDT", "XLMUSDT",
    "XRPUSDT", "XTZUSDT", "ZILUSDT", "ZRXUSDT"

#    "ASTERUSDT", "CHZUSDT", "DOGEUSDT", "ENAUSDT", "FHEUSDT", "FOLKSUSDT", "JASMYUSDT",
#    "HUSDT", "LITUSDT", "JASMYUSDT", "UNIUSDT", "XMRUSDT", "XRPUSDT", "WLFIUSDT"
}

SYMBOL_FILTERS = {
    "BTCUSDT": {'TICK_SIZE': '0.10', 'STEP_SIZE': '0.001'},
    "ETHUSDT": {'TICK_SIZE': '0.01', 'STEP_SIZE': '0.001'},
    "BCHUSDT": {'TICK_SIZE': '0.01', 'STEP_SIZE': '0.001'},
    "XRPUSDT": {'TICK_SIZE': '0.0001', 'STEP_SIZE': '0.1'},
    "LTCUSDT": {'TICK_SIZE': '0.01', 'STEP_SIZE': '0.001'},
    "TRXUSDT": {'TICK_SIZE': '0.00001', 'STEP_SIZE': '1'},
    "ETCUSDT": {'TICK_SIZE': '0.001', 'STEP_SIZE': '0.01'},
    "LINKUSDT": {'TICK_SIZE': '0.001', 'STEP_SIZE': '0.01'},
    "XLMUSDT": {'TICK_SIZE': '0.00001', 'STEP_SIZE': '1'},
    "ADAUSDT": {'TICK_SIZE': '0.00010', 'STEP_SIZE': '1'},
    "XMRUSDT": {'TICK_SIZE': '0.01', 'STEP_SIZE': '0.001'},
    "DASHUSDT": {'TICK_SIZE': '0.01', 'STEP_SIZE': '0.001'},
    "XTZUSDT": {'TICK_SIZE': '0.001', 'STEP_SIZE': '0.1'},
    "BNBUSDT": {'TICK_SIZE': '0.010', 'STEP_SIZE': '0.01'},
    "VETUSDT": {'TICK_SIZE': '0.000001', 'STEP_SIZE': '1'},
    "NEOUSDT": {'TICK_SIZE': '0.001', 'STEP_SIZE': '0.01'},
    "THETAUSDT": {'TICK_SIZE': '0.0001', 'STEP_SIZE': '0.1'},
    "ZILUSDT": {'TICK_SIZE': '0.00001', 'STEP_SIZE': '1'},
    "KNCUSDT": {'TICK_SIZE': '0.00010', 'STEP_SIZE': '1'},
    "ZRXUSDT": {'TICK_SIZE': '0.0001', 'STEP_SIZE': '0.1'},
    "SXPUSDT": {'TICK_SIZE': '0.0001', 'STEP_SIZE': '0.1'},
    "KAVAUSDT": {'TICK_SIZE': '0.0001', 'STEP_SIZE': '0.1'},
    "BANDUSDT": {'TICK_SIZE': '0.0001', 'STEP_SIZE': '0.1'},
    "RLCUSDT": {'TICK_SIZE': '0.0001', 'STEP_SIZE': '0.1'},
    "SNXUSDT": {'TICK_SIZE': '0.001', 'STEP_SIZE': '0.1'},
    "DOTUSDT": {'TICK_SIZE': '0.001', 'STEP_SIZE': '0.1'},
    "TRBUSDT": {'TICK_SIZE': '0.001', 'STEP_SIZE': '0.1'},
    "RUNEUSDT": {'TICK_SIZE': '0.0001', 'STEP_SIZE': '1'},
    "SUSHIUSDT": {'TICK_SIZE': '0.0001', 'STEP_SIZE': '1'},
    "EGLDUSDT": {'TICK_SIZE': '0.001', 'STEP_SIZE': '0.1'},
    "SOLUSDT": {'TICK_SIZE': '0.0100', 'STEP_SIZE': '0.01'},
    "ICXUSDT": {'TICK_SIZE': '0.0001', 'STEP_SIZE': '1'},
    "STORJUSDT": {'TICK_SIZE': '0.0001', 'STEP_SIZE': '1'},
    "UNIUSDT": {'TICK_SIZE': '0.0010', 'STEP_SIZE': '1'},
    "ENJUSDT": {'TICK_SIZE': '0.00001', 'STEP_SIZE': '1'},
    "FLMUSDT": {'TICK_SIZE': '0.0001', 'STEP_SIZE': '1'},
    "NEARUSDT": {'TICK_SIZE': '0.0010', 'STEP_SIZE': '1'},
    "FILUSDT": {'TICK_SIZE': '0.001', 'STEP_SIZE': '0.1'},
    "RSRUSDT": {'TICK_SIZE': '0.000001', 'STEP_SIZE': '1'},
    "BELUSDT": {'TICK_SIZE': '0.00010', 'STEP_SIZE': '1'},
    "ZENUSDT": {'TICK_SIZE': '0.001', 'STEP_SIZE': '0.1'},
    "SKLUSDT": {'TICK_SIZE': '0.00001', 'STEP_SIZE': '1'},
    "GRTUSDT": {'TICK_SIZE': '0.00001', 'STEP_SIZE': '1'},
    "1INCHUSDT": {'TICK_SIZE': '0.0001', 'STEP_SIZE': '1'},
    "CHZUSDT": {'TICK_SIZE': '0.00001', 'STEP_SIZE': '1'},
    "SANDUSDT": {'TICK_SIZE': '0.00001', 'STEP_SIZE': '1'},
    "ANKRUSDT": {'TICK_SIZE': '0.000001', 'STEP_SIZE': '1'},
    "SFPUSDT": {'TICK_SIZE': '0.0001', 'STEP_SIZE': '1'},
    "ALICEUSDT": {'TICK_SIZE': '0.001', 'STEP_SIZE': '0.1'},
    "HBARUSDT": {'TICK_SIZE': '0.00001', 'STEP_SIZE': '1'},
    "ONEUSDT": {'TICK_SIZE': '0.00001', 'STEP_SIZE': '1'},
    "HOTUSDT": {'TICK_SIZE': '0.000001', 'STEP_SIZE': '1'},
    "MTLUSDT": {'TICK_SIZE': '0.0001', 'STEP_SIZE': '1'},
    "OGNUSDT": {'TICK_SIZE': '0.0001', 'STEP_SIZE': '1'},
    "GTCUSDT": {'TICK_SIZE': '0.001', 'STEP_SIZE': '0.1'},
    "MASKUSDT": {'TICK_SIZE': '0.0001', 'STEP_SIZE': '1'},
    "ATAUSDT": {'TICK_SIZE': '0.0001', 'STEP_SIZE': '1'},
    "DYDXUSDT": {'TICK_SIZE': '0.001', 'STEP_SIZE': '0.1'},
    "CELOUSDT": {'TICK_SIZE': '0.001', 'STEP_SIZE': '0.1'},
    "LPTUSDT": {'TICK_SIZE': '0.001', 'STEP_SIZE': '0.1'},
    "ENSUSDT": {'TICK_SIZE': '0.001', 'STEP_SIZE': '0.1'},
    "PEOPLEUSDT": {'TICK_SIZE': '0.00001', 'STEP_SIZE': '1'},
    "IMXUSDT": {'TICK_SIZE': '0.0001', 'STEP_SIZE': '1'},
    "GMTUSDT": {'TICK_SIZE': '0.00001', 'STEP_SIZE': '1'},
    "APEUSDT": {'TICK_SIZE': '0.0001', 'STEP_SIZE': '1'},
    "WOOUSDT": {'TICK_SIZE': '0.00001', 'STEP_SIZE': '1'},
    "JASMYUSDT": {'TICK_SIZE': '0.000001', 'STEP_SIZE': '1'},
    "OPUSDT": {'TICK_SIZE': '0.0001000', 'STEP_SIZE': '0.1'},
    "ICPUSDT": {'TICK_SIZE': '0.001000', 'STEP_SIZE': '1'},
    "FETUSDT": {'TICK_SIZE': '0.0001000', 'STEP_SIZE': '1'},
    "LQTYUSDT": {'TICK_SIZE': '0.000100', 'STEP_SIZE': '0.1'},
    "ARBUSDT": {'TICK_SIZE': '0.000100', 'STEP_SIZE': '0.1'},
    "SUIUSDT": {'TICK_SIZE': '0.000100', 'STEP_SIZE': '0.1'},
    "CYBERUSDT": {'TICK_SIZE': '0.000100', 'STEP_SIZE': '0.1'},
    "TIAUSDT": {'TICK_SIZE': '0.0001000', 'STEP_SIZE': '1'},
    "JTOUSDT": {'TICK_SIZE': '0.000100', 'STEP_SIZE': '1'},
    "JUPUSDT": {'TICK_SIZE': '0.0001000', 'STEP_SIZE': '1'},
    "TONUSDT": {'TICK_SIZE': '0.0001000', 'STEP_SIZE': '0.1'},
}