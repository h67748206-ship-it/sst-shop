"""
Bot Discord - Système de Shop avec paiement PayPal (EUR)
----------------------------------------------------------
Commandes disponibles :
  /create_shop nom paypal   -> Crée toute la structure de la boutique (salons) (admin)
  /delete_shop confirmer     -> Supprime la boutique et ses salons (admin)
  /set_paypal lien          -> Change le lien PayPal de la boutique (admin)
  /add_item                 -> Ajoute un article au catalogue (admin)
  /set_stock                -> Modifie le stock d'un article existant (admin)
  /remove_item               -> Supprime un article (admin)
  /shop                     -> Republie le catalogue
  /buy                       -> Commander un article (crée une commande en attente de paiement)
  /pay                       -> Donne le lien de paiement PayPal
  /confirm_paiement          -> Marque une commande comme payée (admin)
  /mes_commandes              -> Voir ses commandes

Stockage : fichier JSON local (data.json).
"""

import json
import os
import discord
from discord import app_commands
from discord.ext import commands

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

TOKEN = os.getenv("DISCORD_TOKEN", "TON_TOKEN_ICI")
DATA_FILE = "data.json"
CURRENCY_SYMBOL = "€"

# ID de ton serveur Discord (recommandé) pour une synchro instantanée des
# commandes /. Réglages Discord > Avancés > Mode développeur, puis clic droit
# sur le serveur > Copier l'identifiant.
GUILD_ID = os.getenv("GUILD_ID")

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)


# ---------------------------------------------------------------------------
# Gestion des données (JSON)
# ---------------------------------------------------------------------------

def load_data() -> dict:
    if not os.path.exists(DATA_FILE):
        return {"shops": {}}
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_data(data: dict) -> None:
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)


def get_shop(data: dict, guild_id: int) -> dict:
    return data["shops"].get(str(guild_id))


def fmt_price(amount: float) -> str:
    return f"{amount:.2f} {CURRENCY_SYMBOL}"


# ---------------------------------------------------------------------------
# Events
# ---------------------------------------------------------------------------

@bot.event
async def on_ready():
    try:
        if GUILD_ID:
            guild = discord.Object(id=int(GUILD_ID))
            bot.tree.copy_global_to(guild=guild)
            synced = await bot.tree.sync(guild=guild)
            print(f"✅ Connecté en tant que {bot.user} | {len(synced)} commandes synchronisées instantanément.")
        else:
            synced = await bot.tree.sync()
            print(f"✅ Connecté en tant que {bot.user} | {len(synced)} commandes synchronisées (jusqu'à 1h de délai).")
    except Exception as e:
        print(f"Erreur de synchronisation : {e}")


# ---------------------------------------------------------------------------
# /create_shop -> crée la structure complète de la boutique (salons)
# ---------------------------------------------------------------------------

@bot.tree.command(name="create_shop", description="Crée la boutique complète avec ses salons")
@app_commands.describe(
    nom="Nom de la boutique",
    paypal="Ton lien PayPal (ex: https://paypal.me/tonpseudo)",
)
@app_commands.checks.has_permissions(administrator=True)
async def create_shop(interaction: discord.Interaction, nom: str = "Ma Boutique", paypal: str = ""):
    data = load_data()
    guild_id = str(interaction.guild_id)
    guild = interaction.guild

    if guild_id in data["shops"]:
        await interaction.response.send_message(
            "⚠️ Une boutique existe déjà sur ce serveur.", ephemeral=True
        )
        return

    await interaction.response.defer(ephemeral=True)

    # Permissions : lecture seule pour tout le monde sur les salons d'infos,
    # écriture autorisée sur le salon de commande (pour utiliser /buy).
    everyone = guild.default_role
    read_only = {
        everyone: discord.PermissionOverwrite(send_messages=False, view_channel=True),
        guild.me: discord.PermissionOverwrite(send_messages=True, view_channel=True),
    }
    can_write = {
        everyone: discord.PermissionOverwrite(send_messages=True, view_channel=True),
        guild.me: discord.PermissionOverwrite(send_messages=True, view_channel=True),
    }
    admin_only = {
        everyone: discord.PermissionOverwrite(view_channel=False),
        guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True),
    }
    # Ajoute la visibilité admin-only pour tous les rôles ayant la permission administrateur
    for role in guild.roles:
        if role.permissions.administrator:
            admin_only[role] = discord.PermissionOverwrite(view_channel=True, send_messages=True)

    category = await guild.create_category(f"🛒 {nom}")
    catalogue_channel = await guild.create_text_channel("📖-catalogue", category=category, overwrites=read_only)
    payment_channel = await guild.create_text_channel("💳-infos-paiement", category=category, overwrites=read_only)
    order_channel = await guild.create_text_channel("🛍️-commander", category=category, overwrites=can_write)
    admin_channel = await guild.create_text_channel("📦-commandes-admin", category=category, overwrites=admin_only)

    data["shops"][guild_id] = {
        "name": nom,
        "paypal": paypal.strip(),
        "items": {},
        "orders": {},
        "next_order_id": 1,
        "category_id": category.id,
        "catalogue_channel_id": catalogue_channel.id,
        "payment_channel_id": payment_channel.id,
        "order_channel_id": order_channel.id,
        "admin_channel_id": admin_channel.id,
    }
    save_data(data)

    # Message d'accueil dans le salon catalogue
    embed = discord.Embed(
        title=f"🛒 {nom}",
        description="Le catalogue est vide pour le moment.\nUn admin peut ajouter des articles avec `/add_item`.",
        color=discord.Color.blurple(),
    )
    await catalogue_channel.send(embed=embed)

    # Message d'infos paiement
    pay_embed = discord.Embed(
        title="💳 Comment payer",
        description=(
            f"1. Choisis ton article dans {catalogue_channel.mention}\n"
            f"2. Passe ta commande dans {order_channel.mention} avec `/buy`\n"
            f"3. Paie via PayPal avec `/pay` (le lien te sera envoyé)\n"
            f"4. Indique ton **numéro de commande** en note du paiement PayPal\n"
            f"5. Un admin confirmera ta commande une fois le paiement reçu"
        ),
        color=discord.Color.gold(),
    )
    if paypal.strip():
        pay_embed.add_field(name="Lien PayPal", value=paypal.strip(), inline=False)
    else:
        pay_embed.add_field(
            name="⚠️ Lien PayPal non configuré",
            value="Un admin doit utiliser `/set_paypal` pour l'ajouter.",
            inline=False,
        )
    await payment_channel.send(embed=pay_embed)

    # Message d'accueil dans le salon de commande
    order_embed = discord.Embed(
        title="🛍️ Passer commande",
        description="Utilise `/buy nom:<article> quantite:<nombre>` ici pour commander.",
        color=discord.Color.green(),
    )
    await order_channel.send(embed=order_embed)

    await interaction.followup.send(
        f"✅ Boutique **{nom}** créée avec succès !\n"
        f"Salons créés : {catalogue_channel.mention}, {payment_channel.mention}, "
        f"{order_channel.mention}, {admin_channel.mention}",
        ephemeral=True,
    )


# ---------------------------------------------------------------------------
# /delete_shop -> supprime la boutique (données + salons créés)
# ---------------------------------------------------------------------------

@bot.tree.command(name="delete_shop", description="Supprime complètement la boutique de ce serveur")
@app_commands.describe(confirmer="Tape 'oui' pour confirmer la suppression")
@app_commands.checks.has_permissions(administrator=True)
async def delete_shop(interaction: discord.Interaction, confirmer: str):
    data = load_data()
    guild_id = str(interaction.guild_id)
    shop = data["shops"].get(guild_id)

    if not shop:
        await interaction.response.send_message("❌ Aucune boutique n'existe sur ce serveur.", ephemeral=True)
        return

    if confirmer.lower() != "oui":
        await interaction.response.send_message(
            "⚠️ Suppression annulée. Relance la commande avec `confirmer:oui` pour confirmer "
            "(cette action supprime aussi les salons de la boutique, irréversible).",
            ephemeral=True,
        )
        return

    await interaction.response.defer(ephemeral=True)

    # Supprime les salons créés par /create_shop, s'ils existent encore
    channel_ids = [
        shop.get("catalogue_channel_id"),
        shop.get("payment_channel_id"),
        shop.get("order_channel_id"),
        shop.get("admin_channel_id"),
    ]
    for cid in channel_ids:
        channel = bot.get_channel(cid) if cid else None
        if channel:
            try:
                await channel.delete(reason="Suppression de la boutique")
            except discord.HTTPException:
                pass

    category_id = shop.get("category_id")
    category = bot.get_channel(category_id) if category_id else None
    if category:
        try:
            await category.delete(reason="Suppression de la boutique")
        except discord.HTTPException:
            pass

    del data["shops"][guild_id]
    save_data(data)

    await interaction.followup.send("🗑️ Boutique supprimée avec succès. Tu peux en recréer une avec `/create_shop`.", ephemeral=True)


# ---------------------------------------------------------------------------
# /set_paypal
# ---------------------------------------------------------------------------

@bot.tree.command(name="set_paypal", description="Configure ou met à jour le lien PayPal de la boutique")
@app_commands.describe(lien="Ton lien PayPal (ex: https://paypal.me/tonpseudo)")
@app_commands.checks.has_permissions(administrator=True)
async def set_paypal(interaction: discord.Interaction, lien: str):
    data = load_data()
    shop = get_shop(data, interaction.guild_id)

    if not shop:
        await interaction.response.send_message("❌ Aucune boutique trouvée. Utilise `/create_shop` d'abord.", ephemeral=True)
        return

    shop["paypal"] = lien.strip()
    save_data(data)

    # Met à jour le salon infos paiement si possible
    channel = bot.get_channel(shop["payment_channel_id"])
    if channel:
        embed = discord.Embed(title="💳 Lien PayPal mis à jour", description=lien.strip(), color=discord.Color.gold())
        await channel.send(embed=embed)

    await interaction.response.send_message(f"✅ Lien PayPal mis à jour : {lien.strip()}", ephemeral=True)


# ---------------------------------------------------------------------------
# /add_item
# ---------------------------------------------------------------------------

@bot.tree.command(name="add_item", description="Ajoute un article au catalogue")
@app_commands.describe(
    nom="Nom de l'article",
    prix="Prix en euros (ex: 9.99)",
    stock="Quantité disponible (-1 pour illimité)",
    description="Description de l'article",
)
@app_commands.checks.has_permissions(administrator=True)
async def add_item(
    interaction: discord.Interaction,
    nom: str,
    prix: float,
    stock: int = -1,
    description: str = "Aucune description",
):
    data = load_data()
    shop = get_shop(data, interaction.guild_id)

    if not shop:
        await interaction.response.send_message("❌ Aucune boutique trouvée. Utilise `/create_shop` d'abord.", ephemeral=True)
        return

    if prix < 0:
        await interaction.response.send_message("❌ Le prix ne peut pas être négatif.", ephemeral=True)
        return

    shop["items"][nom.lower()] = {
        "price": prix,
        "stock": stock,
        "description": description,
        "display_name": nom,
    }
    save_data(data)

    await refresh_catalogue(shop)
    await interaction.response.send_message(
        f"✅ Article **{nom}** ajouté pour **{fmt_price(prix)}** "
        f"(stock : {'illimité' if stock == -1 else stock})."
    )


# ---------------------------------------------------------------------------
# /set_stock -> modifie le stock d'un article existant
# ---------------------------------------------------------------------------

@bot.tree.command(name="set_stock", description="Modifie le stock d'un article existant")
@app_commands.describe(
    nom="Nom de l'article",
    stock="Nouvelle quantité en stock (-1 pour illimité)",
)
@app_commands.checks.has_permissions(administrator=True)
async def set_stock(interaction: discord.Interaction, nom: str, stock: int):
    data = load_data()
    shop = get_shop(data, interaction.guild_id)

    if not shop or nom.lower() not in shop["items"]:
        await interaction.response.send_message("❌ Cet article n'existe pas.", ephemeral=True)
        return

    if stock < -1:
        await interaction.response.send_message("❌ Le stock doit être -1 (illimité) ou un nombre positif.", ephemeral=True)
        return

    item = shop["items"][nom.lower()]
    item["stock"] = stock
    save_data(data)

    await refresh_catalogue(shop)
    await interaction.response.send_message(
        f"✅ Stock de **{item['display_name']}** mis à jour : "
        f"{'illimité' if stock == -1 else stock}."
    )


# ---------------------------------------------------------------------------
# /remove_item
# ---------------------------------------------------------------------------

@bot.tree.command(name="remove_item", description="Supprime un article du catalogue")
@app_commands.describe(nom="Nom de l'article à supprimer")
@app_commands.checks.has_permissions(administrator=True)
async def remove_item(interaction: discord.Interaction, nom: str):
    data = load_data()
    shop = get_shop(data, interaction.guild_id)

    if not shop or nom.lower() not in shop["items"]:
        await interaction.response.send_message("❌ Cet article n'existe pas.", ephemeral=True)
        return

    del shop["items"][nom.lower()]
    save_data(data)

    await refresh_catalogue(shop)
    await interaction.response.send_message(f"🗑️ Article **{nom}** supprimé.")


# ---------------------------------------------------------------------------
# Catalogue -> republication automatique dans le salon catalogue
# ---------------------------------------------------------------------------

async def build_catalogue_embed(shop: dict) -> discord.Embed:
    embed = discord.Embed(title=f"🛒 {shop['name']} — Catalogue", color=discord.Color.blurple())
    if not shop["items"]:
        embed.description = "Le catalogue est vide pour le moment."
    else:
        for item in shop["items"].values():
            stock_txt = "Illimité" if item["stock"] == -1 else str(item["stock"])
            embed.add_field(
                name=f"{item['display_name']} — {fmt_price(item['price'])}",
                value=f"{item['description']}\nStock : {stock_txt}",
                inline=False,
            )
    embed.set_footer(text="Commande avec /buy dans le salon 🛍️-commander")
    return embed


async def refresh_catalogue(shop: dict) -> None:
    channel = bot.get_channel(shop["catalogue_channel_id"])
    if not channel:
        return
    embed = await build_catalogue_embed(shop)
    await channel.send(embed=embed)


@bot.tree.command(name="shop", description="Republie le catalogue de la boutique")
async def shop_cmd(interaction: discord.Interaction):
    data = load_data()
    shop = get_shop(data, interaction.guild_id)

    if not shop:
        await interaction.response.send_message("❌ Aucune boutique n'existe. Un admin doit utiliser `/create_shop`.", ephemeral=True)
        return

    embed = await build_catalogue_embed(shop)
    await interaction.response.send_message(embed=embed)


# ---------------------------------------------------------------------------
# /buy -> crée une commande en attente de paiement
# ---------------------------------------------------------------------------

@bot.tree.command(name="buy", description="Commander un article de la boutique")
@app_commands.describe(nom="Nom de l'article", quantite="Quantité")
async def buy(interaction: discord.Interaction, nom: str, quantite: int = 1):
    data = load_data()
    shop = get_shop(data, interaction.guild_id)

    if not shop or nom.lower() not in shop["items"]:
        await interaction.response.send_message("❌ Cet article n'existe pas.", ephemeral=True)
        return

    if quantite <= 0:
        await interaction.response.send_message("❌ La quantité doit être supérieure à 0.", ephemeral=True)
        return

    item = shop["items"][nom.lower()]

    if item["stock"] != -1 and item["stock"] < quantite:
        await interaction.response.send_message(f"❌ Stock insuffisant (reste {item['stock']}).", ephemeral=True)
        return

    total = round(item["price"] * quantite, 2)
    order_id = str(shop["next_order_id"])
    shop["next_order_id"] += 1

    shop["orders"][order_id] = {
        "user_id": interaction.user.id,
        "item": item["display_name"],
        "quantite": quantite,
        "total": total,
        "status": "en attente de paiement",
    }

    if item["stock"] != -1:
        item["stock"] -= quantite

    save_data(data)
    await refresh_catalogue(shop)

    # Notifie le salon admin
    admin_channel = bot.get_channel(shop["admin_channel_id"])
    if admin_channel:
        embed = discord.Embed(title=f"🆕 Nouvelle commande #{order_id}", color=discord.Color.orange())
        embed.add_field(name="Client", value=interaction.user.mention, inline=True)
        embed.add_field(name="Article", value=f"{quantite}x {item['display_name']}", inline=True)
        embed.add_field(name="Total", value=fmt_price(total), inline=True)
        embed.set_footer(text="Utilise /confirm_paiement une fois le paiement reçu")
        await admin_channel.send(embed=embed)

    embed = discord.Embed(
        title=f"🧾 Commande #{order_id} créée",
        description=(
            f"**{quantite}x {item['display_name']}** — **{fmt_price(total)}**\n\n"
            f"Utilise `/pay montant:{total}` pour obtenir le lien de paiement.\n"
            f"⚠️ N'oublie pas d'indiquer **#{order_id}** en note de ton paiement PayPal."
        ),
        color=discord.Color.green(),
    )
    await interaction.response.send_message(embed=embed)


# ---------------------------------------------------------------------------
# /pay -> donne le lien PayPal
# ---------------------------------------------------------------------------

@bot.tree.command(name="pay", description="Obtenir le lien de paiement PayPal de la boutique")
@app_commands.describe(montant="Montant à payer en euros (optionnel)")
async def pay(interaction: discord.Interaction, montant: float = None):
    data = load_data()
    shop = get_shop(data, interaction.guild_id)

    if not shop:
        await interaction.response.send_message("❌ Aucune boutique n'existe.", ephemeral=True)
        return

    paypal_link = shop.get("paypal", "").strip()
    if not paypal_link:
        await interaction.response.send_message(
            "❌ Le lien PayPal n'est pas encore configuré. Un admin doit utiliser `/set_paypal`.",
            ephemeral=True,
        )
        return

    link = paypal_link.rstrip("/")
    if montant is not None and montant > 0:
        link = f"{link}/{montant:.2f}EUR"

    embed = discord.Embed(
        title="💳 Paiement PayPal",
        description=f"[Cliquez ici pour payer]({link})\n\n{link}",
        color=discord.Color.gold(),
    )
    if montant is not None:
        embed.add_field(name="Montant", value=fmt_price(montant))
    embed.set_footer(text="Pense à indiquer ton numéro de commande en note du paiement.")

    await interaction.response.send_message(embed=embed, ephemeral=True)


# ---------------------------------------------------------------------------
# /confirm_paiement -> admin confirme la réception du paiement
# ---------------------------------------------------------------------------

@bot.tree.command(name="confirm_paiement", description="Confirme le paiement d'une commande (admin)")
@app_commands.describe(id_commande="Numéro de la commande (ex: 3)")
@app_commands.checks.has_permissions(administrator=True)
async def confirm_paiement(interaction: discord.Interaction, id_commande: str):
    data = load_data()
    shop = get_shop(data, interaction.guild_id)

    if not shop or id_commande not in shop["orders"]:
        await interaction.response.send_message("❌ Commande introuvable.", ephemeral=True)
        return

    order = shop["orders"][id_commande]
    order["status"] = "payée ✅"
    save_data(data)

    await interaction.response.send_message(f"✅ Commande #{id_commande} marquée comme payée.")

    buyer = interaction.guild.get_member(order["user_id"])
    order_channel = bot.get_channel(shop["order_channel_id"])
    if buyer and order_channel:
        await order_channel.send(
            f"✅ {buyer.mention} ta commande **#{id_commande}** "
            f"({order['quantite']}x {order['item']}) a été confirmée, merci !"
        )


# ---------------------------------------------------------------------------
# /mes_commandes
# ---------------------------------------------------------------------------

@bot.tree.command(name="mes_commandes", description="Voir tes commandes")
async def mes_commandes(interaction: discord.Interaction):
    data = load_data()
    shop = get_shop(data, interaction.guild_id)

    if not shop:
        await interaction.response.send_message("❌ Aucune boutique n'existe.", ephemeral=True)
        return

    mine = {oid: o for oid, o in shop["orders"].items() if o["user_id"] == interaction.user.id}
    if not mine:
        await interaction.response.send_message("Tu n'as aucune commande pour le moment.", ephemeral=True)
        return

    embed = discord.Embed(title="🧾 Tes commandes", color=discord.Color.blurple())
    for oid, o in mine.items():
        embed.add_field(
            name=f"Commande #{oid} — {o['status']}",
            value=f"{o['quantite']}x {o['item']} — {fmt_price(o['total'])}",
            inline=False,
        )
    await interaction.response.send_message(embed=embed, ephemeral=True)


# ---------------------------------------------------------------------------
# Gestion des erreurs de permissions
# ---------------------------------------------------------------------------

@create_shop.error
@delete_shop.error
@set_paypal.error
@add_item.error
@set_stock.error
@remove_item.error
@confirm_paiement.error
async def permission_error_handler(interaction: discord.Interaction, error):
    if isinstance(error, app_commands.MissingPermissions):
        await interaction.response.send_message("🚫 Tu dois être administrateur pour utiliser cette commande.", ephemeral=True)
    else:
        try:
            await interaction.response.send_message(f"⚠️ Une erreur est survenue : {error}", ephemeral=True)
        except discord.InteractionResponded:
            await interaction.followup.send(f"⚠️ Une erreur est survenue : {error}", ephemeral=True)


# ---------------------------------------------------------------------------
# Lancement du bot
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    bot.run(TOKEN)
