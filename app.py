from flask import Flask, jsonify
import os

app = Flask(__name__)

@app.route('/')
def home():
    return jsonify({
        "status": "online",
        "message": "Bem-vindo à API do Ycine!",
        "version": "1.0.0"
    })

if __name__ == "__main__":
    # O Railway define a porta automaticamente pela variável de ambiente PORT
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
