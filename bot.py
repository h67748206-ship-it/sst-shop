"""
Bot Discord - Système de Shop avec paiement PayPal (EUR)
----------------------------------------------------------
Commandes disponibles :
  /create_shop nom paypal   -> Crée toute la structure de la boutique (salons) (admin)
  /delete_shop confirmer     -> Supprime la boutique et ses salons (admin)
  /set_paypal lien          -> Change le lien PayPal de la boutique (admin)
  /import_stock              -> Ajoute plusieurs articles via un fichier (admin)
  /import_stock_image        -> Ajoute des articles depuis une photo (admin)
  /set_stock                -> Modifie le stock d'un article existant (admin)
  /remove_item               -> Supprime un article (admin)
  /shop                     -> Republie le catalogue
  /buy                       -> Commander un article (crée une commande en attente de paiement)
  /pay                       -> Donne le lien de paiement PayPal
  /confirm_paiement          -> Marque une commande comme payée (admin)
  /mes_commandes              -> Voir ses commandes

Stockage : fichier JSON local (data.json).
"""

import asyncio
import io
import json
import os
import re
import discord
import requests
from discord import app_commands
from discord.ext import commands
from PIL import Image, ImageDraw, ImageFont
from keep_alive import keep_alive

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

# Clé API pour la lecture de texte sur images (OCR), via ocr.space (gratuit).
# "helloworld" est une clé de démo publique très limitée (peu de requêtes/jour).
# Pour un usage fiable, crée ta propre clé gratuite sur https://ocr.space/ocrapi
# puis mets-la en variable d'environnement OCR_SPACE_API_KEY.
OCR_SPACE_API_KEY = os.getenv("OCR_SPACE_API_KEY", "helloworld")

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
    bot.add_view(BuyButtonView())  # Rend le bouton "Commander" cliquable même après un redémarrage

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
    ticket_category = await guild.create_category("🎫 Tickets", overwrites=admin_only)

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
        "ticket_category_id": ticket_category.id,
    }
    save_data(data)

    # Message d'accueil dans le salon catalogue
    embed = discord.Embed(
        title=f"🛒 {nom}",
        description="Le catalogue est vide pour le moment.\nUn admin peut ajouter des articles avec `/import_stock` ou `/import_stock_image`.",
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

    # Message d'accueil dans le salon de commande, avec bouton permanent
    order_embed = discord.Embed(
        title="🛍️ Passer commande",
        description="Clique sur le bouton ci-dessous ou utilise `/buy` pour choisir un article.",
        color=discord.Color.green(),
    )
    await order_channel.send(embed=order_embed, view=BuyButtonView())

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
# /restock -> ajoute du stock à un article et annonce le restock aux clients
# ---------------------------------------------------------------------------

@bot.tree.command(name="restock", description="Ajoute du stock à un article et annonce le restock aux clients")
@app_commands.describe(
    nom="Nom de l'article",
    quantite="Quantité à ajouter au stock actuel",
)
@app_commands.checks.has_permissions(administrator=True)
async def restock(interaction: discord.Interaction, nom: str, quantite: int):
    data = load_data()
    shop = get_shop(data, interaction.guild_id)

    if not shop or nom.lower() not in shop["items"]:
        await interaction.response.send_message(
            "❌ Cet article n'existe pas. Utilise `/import_stock` ou `/import_stock_image` pour le créer d'abord.", ephemeral=True
        )
        return

    if quantite <= 0:
        await interaction.response.send_message("❌ La quantité doit être supérieure à 0.", ephemeral=True)
        return

    item = shop["items"][nom.lower()]

    if item["stock"] == -1:
        await interaction.response.send_message(
            f"ℹ️ **{item['display_name']}** est déjà en stock illimité, rien à ajouter.", ephemeral=True
        )
        return

    item["stock"] += quantite
    save_data(data)
    await refresh_catalogue(shop)

    await interaction.response.send_message(
        f"✅ **+{quantite}** {item['display_name']} ajouté(s). Nouveau stock : **{item['stock']}**."
    )

    # Annonce automatique du restock dans le salon de commande
    order_channel = bot.get_channel(shop.get("order_channel_id"))
    if order_channel:
        embed = discord.Embed(
            title="🔄 Restock !",
            description=(
                f"**{item['display_name']}** est de retour en stock !\n"
                f"Quantité disponible : **{item['stock']}**\n"
                f"Prix : **{fmt_price(item['price'])}**\n\n"
                f"Clique sur le bouton 🛍️ Commander ci-dessus ou utilise `/buy` pour en profiter !"
            ),
            color=discord.Color.blue(),
        )
        await order_channel.send(embed=embed)


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
# /stock -> génère une image récapitulative de tout le stock
# ---------------------------------------------------------------------------

def generate_stock_image(shop: dict) -> io.BytesIO:
    """Dessine un tableau (nom, prix, stock) sous forme d'image PNG et le retourne en mémoire."""
    items = list(shop["items"].values())

    # Polices (fallback sur la police par défaut si aucune police système n'est trouvée)
    try:
        font_title = ImageFont.truetype("DejaVuSans-Bold.ttf", 28)
        font_header = ImageFont.truetype("DejaVuSans-Bold.ttf", 20)
        font_text = ImageFont.truetype("DejaVuSans.ttf", 20)
    except OSError:
        font_title = ImageFont.load_default()
        font_header = ImageFont.load_default()
        font_text = ImageFont.load_default()

    row_height = 44
    header_height = 90
    width = 760
    height = header_height + row_height * max(len(items), 1) + 30

    bg_color = (30, 33, 36)
    header_color = (47, 49, 54)
    row_color_a = (40, 43, 48)
    row_color_b = (35, 38, 43)
    text_color = (235, 235, 235)
    ok_color = (87, 242, 135)
    low_color = (250, 166, 26)
    out_color = (237, 66, 69)

    img = Image.new("RGB", (width, height), bg_color)
    draw = ImageDraw.Draw(img)

    # Titre
    draw.text((20, 15), f"📦 Stock — {shop['name']}", font=font_title, fill=text_color)

    # En-têtes de colonnes
    y = header_height
    draw.rectangle([(0, y - 40), (width, y)], fill=header_color)
    draw.text((20, y - 34), "Article", font=font_header, fill=text_color)
    draw.text((450, y - 34), "Prix", font=font_header, fill=text_color)
    draw.text((580, y - 34), "Stock", font=font_header, fill=text_color)

    if not items:
        draw.text((20, y + 10), "Aucun article dans le catalogue.", font=font_text, fill=text_color)
    else:
        for i, item in enumerate(items):
            row_color = row_color_a if i % 2 == 0 else row_color_b
            draw.rectangle([(0, y), (width, y + row_height)], fill=row_color)

            draw.text((20, y + 10), item["display_name"][:40], font=font_text, fill=text_color)
            draw.text((450, y + 10), fmt_price(item["price"]), font=font_text, fill=text_color)

            if item["stock"] == -1:
                stock_txt, stock_color = "Illimité", ok_color
            elif item["stock"] == 0:
                stock_txt, stock_color = "Rupture", out_color
            elif item["stock"] <= 5:
                stock_txt, stock_color = str(item["stock"]), low_color
            else:
                stock_txt, stock_color = str(item["stock"]), ok_color

            draw.text((580, y + 10), stock_txt, font=font_text, fill=stock_color)
            y += row_height

    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)
    return buffer


@bot.tree.command(name="stock", description="Affiche une image récapitulative de tout le stock")
async def stock_cmd(interaction: discord.Interaction):
    data = load_data()
    shop = get_shop(data, interaction.guild_id)

    if not shop:
        await interaction.response.send_message("❌ Aucune boutique n'existe.", ephemeral=True)
        return

    await interaction.response.defer()

    buffer = generate_stock_image(shop)
    file = discord.File(buffer, filename="stock.png")
    await interaction.followup.send(file=file)


# ---------------------------------------------------------------------------
# /import_stock -> ajoute plusieurs articles d'un coup via un fichier texte
# ---------------------------------------------------------------------------

def parse_stock_line(line: str):
    """Parse une ligne 'Nom;Stock;Description' -> (nom, stock, description) ou None si invalide.
    Le prix n'est PAS dans le fichier : il est demandé après coup via un formulaire."""
    line = line.strip()
    if not line or line.startswith("#"):
        return None

    parts = [p.strip() for p in line.split(";")]
    if not parts or not parts[0]:
        return None

    nom = parts[0]

    stock = -1
    if len(parts) >= 2 and parts[1] != "":
        try:
            stock = int(parts[1])
        except ValueError:
            stock = -1

    description = parts[2] if len(parts) >= 3 and parts[2] else "Aucune description"

    return nom, stock, description


@bot.tree.command(name="import_stock", description="Ajoute plusieurs articles d'un coup depuis un fichier texte, puis demande le prix")
@app_commands.describe(fichier="Fichier .txt ou .csv, une ligne par article : Nom;Stock;Description")
@app_commands.checks.has_permissions(administrator=True)
async def import_stock(interaction: discord.Interaction, fichier: discord.Attachment):
    data = load_data()
    shop = get_shop(data, interaction.guild_id)

    if not shop:
        await interaction.response.send_message("❌ Aucune boutique n'existe. Utilise `/create_shop` d'abord.", ephemeral=True)
        return

    await interaction.response.defer(ephemeral=True)

    try:
        raw_bytes = await fichier.read()
        content = raw_bytes.decode("utf-8")
    except Exception:
        await interaction.followup.send("❌ Impossible de lire ce fichier. Envoie un fichier texte (.txt ou .csv).", ephemeral=True)
        return

    detected = []
    for line in content.splitlines():
        parsed = parse_stock_line(line)
        if parsed is None:
            continue
        nom, stock, description = parsed
        detected.append((nom, stock, description))

    if not detected:
        await interaction.followup.send(
            "❌ Aucun article valide trouvé dans le fichier.\n"
            "Format attendu, une ligne par article :\n"
            "`Nom;Stock;Description`\n"
            "Exemple : `T-shirt;10;T-shirt noir taille M`\n"
            "(Stock et Description sont optionnels — laisse Stock vide ou -1 pour illimité)",
            ephemeral=True,
        )
        return

    recap = "\n".join(f"• **{nom}** — stock : {'illimité' if s == -1 else s}" for nom, s, _d in detected[:20])
    view = ConfirmPriceView(interaction.guild_id, detected)

    await interaction.followup.send(
        f"🔎 **{len(detected)} article(s) détecté(s) dans le fichier :**\n\n{recap}\n\n"
        f"Clique sur le bouton ci-dessous pour indiquer le prix à appliquer et publier dans le catalogue.",
        view=view,
        ephemeral=True,
    )


# ---------------------------------------------------------------------------
# /import_stock_image -> lit une photo/capture de stock via OCR et ajoute les articles
# ---------------------------------------------------------------------------

def parse_nom_exemplaires_lines(text: str):
    """Reconnaît le format de la page 'Cadeaux' Discord : une ligne avec le nom,
    suivie d'une ligne 'X exemplaires' (ou 'X exemplaire'). Retourne une liste de (nom, stock)."""
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    results = []

    for i, line in enumerate(lines):
        match = re.match(r"^(\d+)\s*exemplaires?$", line, re.IGNORECASE)
        if match and i > 0:
            stock = int(match.group(1))
            nom = lines[i - 1]
            # Évite de reprendre une ligne déjà utilisée comme "stock" par erreur
            if not re.match(r"^\d+\s*exemplaires?$", nom, re.IGNORECASE):
                results.append((nom, stock))

    return results


def parse_ocr_line(line: str):
    """Essaie d'extraire (nom, prix, stock) d'une ligne de texte brut détectée par l'OCR.
    Heuristique : le dernier nombre = stock, l'avant-dernier = prix, le reste = nom.
    S'il n'y a qu'un seul nombre, on suppose que c'est le prix (stock = illimité)."""
    line = line.strip()
    if not line:
        return None

    numbers = re.findall(r"\d+[.,]\d+|\d+", line)
    if not numbers:
        return None

    first_num_match = re.search(r"\d", line)
    nom = line[: first_num_match.start()].strip(" -:;\t.,")
    if not nom or len(nom) < 2:
        return None

    if len(numbers) >= 2:
        try:
            prix = float(numbers[-2].replace(",", "."))
        except ValueError:
            return None
        try:
            stock = int(float(numbers[-1].replace(",", ".")))
        except ValueError:
            stock = -1
    else:
        try:
            prix = float(numbers[0].replace(",", "."))
        except ValueError:
            return None
        stock = -1

    return nom, prix, stock


class PriceModal(discord.ui.Modal, title="Prix des articles détectés"):
    def __init__(self, shop_guild_id: int, detected_items: list):
        super().__init__()
        self.shop_guild_id = shop_guild_id
        self.detected_items = detected_items  # liste de (nom, stock)

    prix = discord.ui.TextInput(
        label="Prix à appliquer (en €)",
        placeholder="Ex: 9.99",
        required=True,
        max_length=10,
    )

    async def on_submit(self, interaction: discord.Interaction):
        try:
            prix_val = float(str(self.prix.value).replace(",", "."))
        except ValueError:
            await interaction.response.send_message("❌ Prix invalide, réessaie avec un nombre (ex: 9.99).", ephemeral=True)
            return

        data = load_data()
        shop = get_shop(data, self.shop_guild_id)
        if not shop:
            await interaction.response.send_message("❌ La boutique n'existe plus.", ephemeral=True)
            return

        added = []
        for entry in self.detected_items:
            if len(entry) == 3:
                nom, stock, description = entry
            else:
                nom, stock = entry
                description = "Aucune description"
            shop["items"][nom.lower()] = {
                "price": prix_val,
                "stock": stock,
                "description": description,
                "display_name": nom,
            }
            added.append((nom, prix_val, stock))

        save_data(data)
        await refresh_catalogue(shop)

        recap = "\n".join(
            f"• **{nom}** — {fmt_price(p)} (stock : {'illimité' if s == -1 else s})" for nom, p, s in added
        )
        await interaction.response.send_message(
            f"✅ **{len(added)} article(s) publié(s) dans le catalogue !**\n\n{recap}", ephemeral=True
        )


class ConfirmPriceView(discord.ui.View):
    def __init__(self, guild_id: int, detected_items: list):
        super().__init__(timeout=300)
        self.guild_id = guild_id
        self.detected_items = detected_items

    @discord.ui.button(label="💶 Définir le prix et publier", style=discord.ButtonStyle.green)
    async def set_price(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(PriceModal(self.guild_id, self.detected_items))


@bot.tree.command(name="import_stock_image", description="Lit une photo de ton stock, demande le prix, puis publie automatiquement")
@app_commands.describe(image="Photo ou capture d'écran de ta liste de stock (nom + quantité)")
@app_commands.checks.has_permissions(administrator=True)
async def import_stock_image(interaction: discord.Interaction, image: discord.Attachment):
    data = load_data()
    shop = get_shop(data, interaction.guild_id)

    if not shop:
        await interaction.response.send_message("❌ Aucune boutique n'existe. Utilise `/create_shop` d'abord.", ephemeral=True)
        return

    if not (image.content_type or "").startswith("image/"):
        await interaction.response.send_message("❌ Ce fichier n'est pas une image.", ephemeral=True)
        return

    await interaction.response.defer(ephemeral=True)

    try:
        response = requests.post(
            "https://api.ocr.space/parse/image",
            data={"apikey": OCR_SPACE_API_KEY, "language": "fre", "OCREngine": "2"},
            files={"file": (image.filename, await image.read(), image.content_type)},
            timeout=30,
        )
        result = response.json()
    except Exception as e:
        await interaction.followup.send(f"❌ Erreur lors de la lecture de l'image : {e}", ephemeral=True)
        return

    if result.get("IsErroredOnProcessing"):
        await interaction.followup.send(
            f"❌ L'OCR n'a pas pu lire l'image : {result.get('ErrorMessage', 'erreur inconnue')}", ephemeral=True
        )
        return

    parsed_results = result.get("ParsedResults") or []
    if not parsed_results:
        await interaction.followup.send("❌ Aucun texte détecté dans l'image.", ephemeral=True)
        return

    text = parsed_results[0].get("ParsedText", "")

    # 1. On essaie d'abord le format "Nom" + "X exemplaires" (page cadeaux Discord)
    detected = parse_nom_exemplaires_lines(text)

    # 2. Sinon on retombe sur le format générique nom+nombre(s)
    if not detected:
        for line in text.splitlines():
            parsed = parse_ocr_line(line)
            if parsed:
                nom, _prix_ignore, stock = parsed
                detected.append((nom, stock))

    if not detected:
        await interaction.followup.send(
            "❌ Je n'ai réussi à reconnaître aucun article dans l'image.\n"
            "L'OCR fonctionne mieux avec du texte net (capture d'écran) qu'avec de l'écriture manuscrite.\n"
            f"Texte brut détecté :\n```{text[:500]}```",
            ephemeral=True,
        )
        return

    recap = "\n".join(f"• **{nom}** — stock : {'illimité' if s == -1 else s}" for nom, s in detected[:20])
    view = ConfirmPriceView(interaction.guild_id, detected)

    await interaction.followup.send(
        f"🔎 **{len(detected)} article(s) détecté(s) :**\n\n{recap}\n\n"
        f"Clique sur le bouton ci-dessous pour indiquer le prix à appliquer et publier dans le catalogue.",
        view=view,
        ephemeral=True,
    )


# ---------------------------------------------------------------------------
# Fonction commune : création d'un ticket de commande
# ---------------------------------------------------------------------------

async def create_order_ticket(interaction: discord.Interaction, shop: dict, item_key: str, quantite: int = 1):
    data = load_data()
    shop = get_shop(data, interaction.guild_id)  # relit les données à jour

    if not shop or item_key not in shop["items"]:
        await interaction.response.send_message("❌ Cet article n'existe plus.", ephemeral=True)
        return

    item = shop["items"][item_key]

    if item["stock"] != -1 and item["stock"] < quantite:
        await interaction.response.send_message(f"❌ Stock insuffisant (reste {item['stock']}).", ephemeral=True)
        return

    await interaction.response.defer(ephemeral=True)

    total = round(item["price"] * quantite, 2)
    order_id = str(shop["next_order_id"])
    shop["next_order_id"] += 1

    guild = interaction.guild
    ticket_category = guild.get_channel(shop.get("ticket_category_id")) if shop.get("ticket_category_id") else None

    if ticket_category is None:
        # La boutique a été créée avant l'ajout du système de tickets : on crée la catégorie maintenant.
        admin_only = {guild.default_role: discord.PermissionOverwrite(view_channel=False)}
        for role in guild.roles:
            if role.permissions.administrator:
                admin_only[role] = discord.PermissionOverwrite(view_channel=True, send_messages=True)
        ticket_category = await guild.create_category("🎫 Tickets", overwrites=admin_only)
        shop["ticket_category_id"] = ticket_category.id
        save_data(data)

    # Permissions du ticket : uniquement le client + les admins
    overwrites = {
        guild.default_role: discord.PermissionOverwrite(view_channel=False),
        guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True),
        interaction.user: discord.PermissionOverwrite(view_channel=True, send_messages=True),
    }
    for role in guild.roles:
        if role.permissions.administrator:
            overwrites[role] = discord.PermissionOverwrite(view_channel=True, send_messages=True)

    ticket_channel = await guild.create_text_channel(
        f"ticket-{order_id}-{interaction.user.name}"[:95],
        category=ticket_category,
        overwrites=overwrites,
        reason=f"Ticket de commande #{order_id}",
    )

    shop["orders"][order_id] = {
        "user_id": interaction.user.id,
        "item": item["display_name"],
        "quantite": quantite,
        "total": total,
        "status": "en attente de paiement",
        "ticket_channel_id": ticket_channel.id,
    }

    if item["stock"] != -1:
        item["stock"] -= quantite

    save_data(data)
    await refresh_catalogue(shop)

    # Notifie le salon admin (log global)
    admin_channel = bot.get_channel(shop["admin_channel_id"])
    if admin_channel:
        embed = discord.Embed(title=f"🆕 Nouvelle commande #{order_id}", color=discord.Color.orange())
        embed.add_field(name="Client", value=interaction.user.mention, inline=True)
        embed.add_field(name="Article", value=f"{quantite}x {item['display_name']}", inline=True)
        embed.add_field(name="Total", value=fmt_price(total), inline=True)
        embed.add_field(name="Ticket", value=ticket_channel.mention, inline=False)
        embed.set_footer(text="Utilise /confirm_paiement une fois le paiement reçu")
        await admin_channel.send(embed=embed)

    # Message d'accueil dans le ticket
    ticket_embed = discord.Embed(
        title=f"🧾 Ticket — Commande #{order_id}",
        description=(
            f"Bienvenue {interaction.user.mention} !\n\n"
            f"**Article :** {quantite}x {item['display_name']}\n"
            f"**Total :** {fmt_price(total)}\n\n"
            f"Utilise `/pay montant:{total}` pour obtenir le lien de paiement.\n"
            f"⚠️ Indique **#{order_id}** en note de ton paiement PayPal.\n\n"
            f"Un membre de l'équipe va s'occuper de toi ici. Une fois le paiement confirmé, "
            f"ce ticket sera fermé avec `/close_ticket`."
        ),
        color=discord.Color.green(),
    )
    await ticket_channel.send(embed=ticket_embed)

    await interaction.followup.send(
        f"✅ Ta commande **#{order_id}** a été créée ! Rendez-vous dans {ticket_channel.mention}.",
        ephemeral=True,
    )


# ---------------------------------------------------------------------------
# Menu déroulant de sélection d'article
# ---------------------------------------------------------------------------

class ItemSelect(discord.ui.Select):
    def __init__(self, shop: dict):
        options = []
        for key, item in shop["items"].items():
            if item["stock"] == 0:
                continue  # article en rupture de stock : on ne le propose pas
            label = f"{item['display_name']} — {fmt_price(item['price'])}"
            options.append(discord.SelectOption(label=label[:100], description=item["description"][:100], value=key))

        if not options:
            options = [discord.SelectOption(label="Aucun article disponible", value="__none__")]

        super().__init__(placeholder="Choisis un article à acheter...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        if self.values[0] == "__none__":
            await interaction.response.send_message("❌ Aucun article disponible pour le moment.", ephemeral=True)
            return

        data = load_data()
        shop = get_shop(data, interaction.guild_id)
        await create_order_ticket(interaction, shop, self.values[0], quantite=1)


class ShopSelectView(discord.ui.View):
    def __init__(self, shop: dict):
        super().__init__(timeout=120)
        self.add_item(ItemSelect(shop))


async def show_buy_menu(interaction: discord.Interaction):
    """Affiche le menu déroulant des articles. Utilisé par /buy et par le bouton permanent."""
    data = load_data()
    shop = get_shop(data, interaction.guild_id)

    if not shop:
        await interaction.response.send_message("❌ Aucune boutique n'existe.", ephemeral=True)
        return

    if not shop["items"]:
        await interaction.response.send_message("❌ Le catalogue est vide pour le moment.", ephemeral=True)
        return

    view = ShopSelectView(shop)
    await interaction.response.send_message(
        "🛍️ Sélectionne l'article que tu veux commander :", view=view, ephemeral=True
    )


class BuyButtonView(discord.ui.View):
    """Vue persistante avec un bouton 'Commander' toujours cliquable, même après redémarrage du bot."""

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🛍️ Commander", style=discord.ButtonStyle.green, custom_id="shop_buy_button_persistent")
    async def buy_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await show_buy_menu(interaction)


# ---------------------------------------------------------------------------
# /buy -> affiche un menu déroulant pour choisir l'article à commander
# ---------------------------------------------------------------------------

@bot.tree.command(name="buy", description="Choisir un article à acheter (ouvre un ticket privé)")
async def buy(interaction: discord.Interaction):
    await show_buy_menu(interaction)


# ---------------------------------------------------------------------------
# /close_ticket -> ferme (supprime) un salon de ticket
# ---------------------------------------------------------------------------

@bot.tree.command(name="close_ticket", description="Ferme le ticket de commande actuel")
async def close_ticket(interaction: discord.Interaction):
    data = load_data()
    shop = get_shop(data, interaction.guild_id)

    if not shop:
        await interaction.response.send_message("❌ Aucune boutique n'existe.", ephemeral=True)
        return

    # Vérifie que la commande est bien lancée dans un salon de ticket
    order_id = None
    for oid, o in shop["orders"].items():
        if o.get("ticket_channel_id") == interaction.channel_id:
            order_id = oid
            break

    if order_id is None:
        await interaction.response.send_message("❌ Cette commande doit être utilisée dans un salon de ticket.", ephemeral=True)
        return

    order = shop["orders"][order_id]
    is_admin = interaction.user.guild_permissions.administrator
    is_owner = interaction.user.id == order["user_id"]

    if not (is_admin or is_owner):
        await interaction.response.send_message("🚫 Tu n'as pas la permission de fermer ce ticket.", ephemeral=True)
        return

    await interaction.response.send_message("🔒 Fermeture du ticket dans 5 secondes...")
    await asyncio.sleep(5)
    try:
        await interaction.channel.delete(reason=f"Ticket fermé par {interaction.user}")
    except discord.HTTPException:
        pass


# ---------------------------------------------------------------------------
# /paypal -> affiche simplement le lien PayPal de la boutique
# ---------------------------------------------------------------------------

@bot.tree.command(name="paypal", description="Affiche le lien PayPal de la boutique")
async def paypal_cmd(interaction: discord.Interaction):
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

    embed = discord.Embed(
        title="💳 Lien PayPal",
        description=f"[Cliquez ici pour payer]({paypal_link})\n\n{paypal_link}",
        color=discord.Color.gold(),
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

    # Retire le préfixe ⏳ du ticket puisqu'il n'est plus en attente
    ticket = interaction.guild.get_channel(order.get("ticket_channel_id")) if order.get("ticket_channel_id") else None
    if ticket and ticket.name.startswith("⏳"):
        try:
            await ticket.edit(name=f"✅-commande-{id_commande}")
        except discord.HTTPException:
            pass

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
# /commandes_en_attente -> liste les commandes non payées (admin)
# ---------------------------------------------------------------------------

@bot.tree.command(name="commandes_en_attente", description="Liste les commandes pas encore payées (admin)")
@app_commands.checks.has_permissions(administrator=True)
async def commandes_en_attente(interaction: discord.Interaction):
    data = load_data()
    shop = get_shop(data, interaction.guild_id)

    if not shop:
        await interaction.response.send_message("❌ Aucune boutique n'existe.", ephemeral=True)
        return

    pending = {
        oid: o for oid, o in shop["orders"].items() if o["status"] == "en attente de paiement"
    }

    if not pending:
        await interaction.response.send_message("✅ Aucune commande en attente de paiement pour le moment.", ephemeral=True)
        return

    await interaction.response.defer(ephemeral=True)

    embed = discord.Embed(
        title=f"⏳ Commandes en attente ({len(pending)})",
        color=discord.Color.orange(),
    )
    for oid, o in pending.items():
        member = interaction.guild.get_member(o["user_id"])
        client_txt = member.mention if member else f"<@{o['user_id']}>"
        ticket = interaction.guild.get_channel(o.get("ticket_channel_id")) if o.get("ticket_channel_id") else None
        ticket_txt = ticket.mention if ticket else "*ticket introuvable*"

        # Renomme le salon du ticket pour le rendre repérable d'un coup d'œil
        if ticket and not ticket.name.startswith("⏳"):
            try:
                await ticket.edit(name=f"⏳-commande-{oid}")
            except discord.HTTPException:
                pass  # Limite de renommage Discord atteinte, on ignore silencieusement

        embed.add_field(
            name=f"Commande #{oid}",
            value=f"Client : {client_txt}\nArticle : {o['quantite']}x {o['item']}\nTotal : {fmt_price(o['total'])}\nTicket : {ticket_txt}",
            inline=False,
        )
    embed.set_footer(text="Utilise /confirm_paiement id_commande:X une fois le paiement reçu")

    await interaction.followup.send(embed=embed, ephemeral=True)


# ---------------------------------------------------------------------------
# Gestion des erreurs de permissions
# ---------------------------------------------------------------------------

@create_shop.error
@delete_shop.error
@set_paypal.error
@import_stock.error
@import_stock_image.error
@set_stock.error
@restock.error
@remove_item.error
@confirm_paiement.error
@commandes_en_attente.error
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
    keep_alive()  # Démarre le serveur web keep-alive (utile sur Replit)
    bot.run(TOKEN)
