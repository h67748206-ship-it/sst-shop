"""
Script de nettoyage - à lancer UNE SEULE FOIS
------------------------------------------------
Supprime TOUTES les commandes slash (/) enregistrées sur Discord,
qu'elles soient globales ou spécifiques à ton serveur (GUILD_ID).

Utilise ce script si tu as des commandes qui ne s'affichent plus bien,
des doublons, ou des commandes "obsolètes" dans Discord.

Après avoir lancé ce script, relance normalement bot.py : il réenregistrera
toutes les commandes à jour depuis zéro.
"""

import asyncio
import os
import discord
from discord.ext import commands

TOKEN = os.getenv("DISCORD_TOKEN", "TON_TOKEN_ICI")
GUILD_ID = os.getenv("GUILD_ID")

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)


@bot.event
async def on_ready():
    print(f"Connecté en tant que {bot.user}, nettoyage en cours...")

    # 1. Supprime toutes les commandes GLOBALES
    bot.tree.clear_commands(guild=None)
    await bot.tree.sync()
    print("✅ Commandes globales supprimées.")

    # 2. Supprime toutes les commandes LOCALES au serveur (si GUILD_ID fourni)
    if GUILD_ID:
        guild = discord.Object(id=int(GUILD_ID))
        bot.tree.clear_commands(guild=guild)
        await bot.tree.sync(guild=guild)
        print(f"✅ Commandes locales supprimées pour le serveur {GUILD_ID}.")
    else:
        print("ℹ️ Aucun GUILD_ID fourni, seules les commandes globales ont été nettoyées.")

    print("🧹 Nettoyage terminé. Tu peux fermer ce script et relancer bot.py normalement.")
    await bot.close()


if __name__ == "__main__":
    bot.run(TOKEN)
