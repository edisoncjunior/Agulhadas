import os
import requests
from flask import Flask, request, jsonify
from config import TELEGRAM_SOURCE_CHAT_ID

app = Flask(__name__)

# Endereço público do executor local (ngrok)
EXECUTOR_URL = os.getenv("EXECUTOR_URL")  # ex: https://xxxx.ngrok-free.dev/executar

@app.route("/telegram-sinal", methods=["POST"])
def telegram_sinal():
    data = request.json
    try:
        # Encaminha para executor local
        resp = requests.post(f"{EXECUTOR_URL}", json=data, timeout=10)
        return jsonify({"status": "ok", "executor_response": resp.json()})
    except Exception as e:
        return jsonify({"status": "error", "msg": str(e)}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
