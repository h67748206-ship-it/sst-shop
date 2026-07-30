import os
from flask import Flask
from threading import Thread

app = Flask("")


@app.route("/")
def home():
    return "✅ Le bot est en ligne !"


def run():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)


def keep_alive():
    """Lance le serveur web dans un thread séparé pour ne pas bloquer le bot."""
    t = Thread(target=run)
    t.start()
