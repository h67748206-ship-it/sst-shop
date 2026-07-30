"""
Petit serveur web pour garder le bot en vie sur Replit.
---------------------------------------------------------
Replit met en veille les projets gratuits qui ne reçoivent aucune requête web.
Ce serveur Flask tourne en parallèle du bot Discord et répond à un simple
ping HTTP. En connectant un service comme cron-job.org pour appeler cette
URL toutes les 5 minutes, le Repl reste actif 24/7.
"""

from flask import Flask
from threading import Thread

app = Flask("")


@app.route("/")
def home():
    return "✅ Le bot est en ligne !"


def run():
    app.run(host="0.0.0.0", port=8080)


def keep_alive():
    """Lance le serveur web dans un thread séparé pour ne pas bloquer le bot."""
    t = Thread(target=run)
    t.start()
