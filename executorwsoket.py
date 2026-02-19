from flask import Flask, request, jsonify
from config import binance_client, DRY_RUN
from executor_ordens import executar_ordem  # sua lógica existente

app = Flask(__name__)

@app.route("/executar", methods=["POST"])
def executar():
    data = request.json
    symbol = data.get("symbol")
    side = data.get("side")
    timeframe = data.get("timeframe")
    order_type = data.get("order_type")

    if DRY_RUN:
        print(f"[DRY_RUN] Ordem recebida: {symbol} {side} {order_type}")
        return jsonify({"status": "dry_run"})

    try:
        result = executar_ordem(symbol, side, timeframe, order_type)
        return jsonify({"status": "ok", "result": result})
    except Exception as e:
        return jsonify({"status": "error", "msg": str(e)}), 500

if __name__ == "__main__":
    app.run(port=5000)
