# 🛒 Bot Discord - Shop avec paiement PayPal (EUR)

Un bot Discord qui crée automatiquement une **vraie boutique organisée en salons**, avec des prix en euros et un système de commande + paiement PayPal.

## 📋 Commandes

| Commande | Description | Accès |
|---|---|---|
| `/create_shop nom paypal` | Crée la boutique + tous ses salons | Admin |
| `/delete_shop confirmer:oui` | Supprime la boutique et ses salons | Admin |
| `/set_paypal lien` | Change/ajoute le lien PayPal | Admin |
| `/add_item nom prix [stock] [description]` | Ajoute un article (prix en €) | Admin |
| `/set_stock nom stock` | Modifie le stock d'un article existant | Admin |
| `/remove_item nom` | Supprime un article | Admin |
| `/shop` | Republie le catalogue | Tout le monde |
| `/buy nom [quantite]` | Passer commande | Tout le monde |
| `/pay [montant]` | Obtenir le lien de paiement PayPal | Tout le monde |
| `/confirm_paiement id_commande` | Valider une commande payée | Admin |
| `/mes_commandes` | Voir ses propres commandes | Tout le monde |

## 🏗️ Ce que `/create_shop` crée automatiquement

Une catégorie **🛒 [Nom de ta boutique]** contenant 4 salons :

- **📖-catalogue** — liste des articles (lecture seule, mis à jour automatiquement par le bot)
- **💳-infos-paiement** — explique comment payer + contient le lien PayPal (lecture seule)
- **🛍️-commander** — salon où les clients tapent `/buy` pour commander
- **📦-commandes-admin** — salon privé (visible seulement par les admins) où arrivent les notifications de nouvelles commandes

## ⚙️ Installation

### 1. Créer ton bot sur Discord

1. Va sur https://discord.com/developers/applications
2. **New Application**, donne-lui un nom
3. Onglet **Bot** → **Add Bot**
4. Active l'intent **MESSAGE CONTENT INTENT**
5. Copie le **Token** — garde-le secret, ne le partage jamais (même en capture d'écran) !
6. Onglet **OAuth2 > URL Generator** :
   - Coche `bot` et `applications.commands`
   - Permissions : coche `Administrator` (pour que le bot puisse créer des salons/catégories)
   - Ouvre l'URL générée pour inviter le bot sur ton serveur

### 2. Installer les dépendances

```bash
pip install -r requirements.txt
```

### 3. (Recommandé) Récupérer l'ID de ton serveur pour une synchro instantanée

Sans ça, les commandes `/` peuvent mettre jusqu'à 1h à apparaître.

1. Discord → Réglages → Avancés → active **Mode développeur**
2. Clic droit sur l'icône de ton serveur → **Copier l'identifiant**

### 4. Configurer les variables et lancer

**Windows (cmd) :**
```
set DISCORD_TOKEN=ton_token_ici
set GUILD_ID=id_de_ton_serveur
python bot.py
```

**Linux / Mac :**
```bash
export DISCORD_TOKEN="ton_token_ici"
export GUILD_ID="id_de_ton_serveur"
python bot.py
```

Si tout fonctionne, tu verras dans la console :
```
✅ Connecté en tant que TonBot#1234 | X commandes synchronisées instantanément.
```

## 🚀 Utilisation complète

1. **Créer la boutique** (en tant qu'admin), avec ton lien PayPal directement :
   ```
   /create_shop nom:Ma Boutique paypal:https://paypal.me/tonpseudo
   ```
   → ça crée tous les salons automatiquement.

2. **Ajouter des articles** :
   ```
   /add_item nom:T-shirt prix:19.99 stock:10 description:T-shirt noir taille M
   ```
   → le catalogue se met à jour tout seul dans #📖-catalogue.

3. **Un client commande** dans #🛍️-commander :
   ```
   /buy nom:T-shirt quantite:1
   ```
   → une commande est créée (ex: commande #1), les admins reçoivent une alerte dans #📦-commandes-admin.

4. **Le client paie** :
   ```
   /pay montant:19.99
   ```
   → le bot lui envoie le lien PayPal avec le montant pré-rempli. Il doit indiquer le **numéro de commande** en note du paiement PayPal.

5. **L'admin confirme le paiement** une fois reçu sur son compte PayPal :
   ```
   /confirm_paiement id_commande:1
   ```
   → le client est notifié que sa commande est validée.

## 💾 Stockage des données

Tout est sauvegardé automatiquement dans `data.json` à côté de `bot.py` (boutique, articles, commandes). Pas de base de données externe nécessaire.

## ⚠️ Notes importantes

- **Le bot ne vérifie PAS automatiquement les paiements PayPal.** PayPal ne permet pas facilement de vérifier un paiement sans un vrai compte marchand + API PayPal (Business). Le système actuel fonctionne en confiance : le client paie, indique son numéro de commande en note, et l'admin confirme manuellement avec `/confirm_paiement`. Si tu veux une vérification automatique, il faudra intégrer l'API PayPal Business — dis-moi si tu veux qu'on le fasse.
- Format du lien PayPal.me recommandé : `https://paypal.me/tonpseudo` (sans slash à la fin)
- Ne partage jamais ton token Discord publiquement
- Pour héberger le bot 24/7 même PC éteint : Railway, Render, ou une VPS
