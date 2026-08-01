# 🛒 Bot Discord - Shop avec paiement PayPal (EUR)

Un bot Discord qui crée automatiquement une **vraie boutique organisée en salons**, avec des prix en euros et un système de commande + paiement PayPal.

## 📋 Commandes

| Commande | Description | Accès |
|---|---|---|
| `/create_shop nom paypal` | Crée la boutique + tous ses salons | Admin |
| `/delete_shop confirmer:oui` | Supprime la boutique et ses salons | Admin |
| `/set_paypal lien` | Change/ajoute le lien PayPal | Admin |
| `/add_item nom prix [stock] [description]` | Ajoute un article (prix en €) | Admin |
| `/import_stock fichier` | Ajoute plusieurs articles d'un coup depuis un fichier | Admin |
| `/set_stock nom stock` | Modifie le stock d'un article existant | Admin |
| `/restock nom quantite` | Ajoute du stock + annonce le restock aux clients | Admin |
| `/remove_item nom` | Supprime un article | Admin |
| `/shop` | Republie le catalogue | Tout le monde |
| `/stock` | Affiche une image récapitulative du stock | Tout le monde |
| `/buy` | Affiche un menu déroulant pour choisir un article → ouvre un ticket privé | Tout le monde |
| `/close_ticket` | Ferme le ticket de commande en cours | Client concerné / Admin |
| `/paypal` | Affiche simplement le lien PayPal de la boutique | Tout le monde |
| `/pay [montant]` | Obtenir le lien de paiement PayPal avec montant pré-rempli | Tout le monde |
| `/confirm_paiement id_commande` | Valider une commande payée | Admin |
| `/mes_commandes` | Voir ses propres commandes | Tout le monde |
| `/commandes_en_attente` | Liste les commandes pas encore payées | Admin |

## 🏗️ Ce que `/create_shop` crée automatiquement

Une catégorie **🛒 [Nom de ta boutique]** contenant 4 salons :

- **📖-catalogue** — liste des articles (lecture seule, mis à jour automatiquement par le bot)
- **💳-infos-paiement** — explique comment payer + contient le lien PayPal (lecture seule)
- **🛍️-commander** — salon où les clients tapent `/buy` pour commander
- **📦-commandes-admin** — salon privé (visible seulement par les admins) où arrivent les notifications de nouvelles commandes

Une catégorie séparée **🎫 Tickets** est aussi créée : c'est là qu'apparaissent les salons privés de commande (un salon par commande, visible uniquement par le client concerné et les admins).

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

3. **Un client commande** en tapant simplement `/buy` (n'importe où, ou dans #🛍️-commander) :
   ```
   /buy
   ```
   → un **menu déroulant** apparaît avec tous les articles disponibles. Le client choisit un article, et un **ticket privé** (`#ticket-1-pseudo`) est automatiquement créé, visible uniquement par lui et les admins. Une commande est enregistrée (ex: commande #1), et les admins reçoivent une alerte dans #📦-commandes-admin avec un lien vers le ticket.

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

6. **Fermer le ticket** une fois la transaction terminée (dans le salon du ticket) :
   ```
   /close_ticket
   ```
   → le salon se supprime automatiquement après 5 secondes. Utilisable par le client concerné ou un admin.

## ☁️ Héberger le bot 24/7 via GitHub + Railway

GitHub stocke seulement ton code — il ne fait pas tourner le bot en continu. Le combo gratuit classique : **GitHub héberge le code**, **Railway héberge et fait tourner le bot** en le récupérant automatiquement depuis ton dépôt GitHub.

### 1. Mettre le code sur GitHub

1. Crée un compte sur https://github.com si tu n'en as pas
2. Clique sur **New repository**, donne-lui un nom (ex: `discord-shop-bot`), laisse-le en **Private** (recommandé)
3. Sur ton PC, dans le dossier du bot, ouvre un terminal et tape :
   ```
   git init
   git add .
   git commit -m "Premier commit"
   git branch -M main
   git remote add origin https://github.com/TON_PSEUDO/discord-shop-bot.git
   git push -u origin main
   ```
   (remplace `TON_PSEUDO` par ton pseudo GitHub — Git te demandera de te connecter la première fois)

⚠️ Le fichier `.gitignore` fourni empêche `data.json` (tes commandes/articles) et ton token d'être envoyés sur GitHub par erreur. Ne mets **jamais** ton token directement dans le code.

### 2. Connecter Railway à ton dépôt GitHub

1. Va sur https://railway.app et connecte-toi avec ton compte GitHub
2. **New Project** → **Deploy from GitHub repo**
3. Choisis ton dépôt `discord-shop-bot`
4. Railway détecte automatiquement `requirements.txt` et `Procfile`, et installe/lance le bot tout seul

### 3. Configurer les variables d'environnement sur Railway

Dans ton projet Railway → onglet **Variables** → ajoute :
- `DISCORD_TOKEN` = ton token Discord
- `GUILD_ID` = l'identifiant de ton serveur

Railway relance automatiquement le bot après l'ajout des variables.

### 4. Vérifier que ça tourne

Onglet **Deployments** → clique sur le déploiement en cours → **View Logs**. Tu dois voir :
```
✅ Connecté en tant que TonBot#1234 | X commandes synchronisées.
```

Le bot tourne maintenant 24/7, même PC éteint. À chaque fois que tu modifies le code et fais `git push`, Railway redéploie automatiquement la nouvelle version.

⚠️ **Stockage des données sur Railway** : le fichier `data.json` est stocké sur le disque de Railway, mais il peut être réinitialisé lors d'un redéploiement selon le plan utilisé. Pour une boutique en production sérieuse, pense à migrer vers une vraie base de données (ex: Railway propose aussi des bases PostgreSQL gratuites) — dis-moi si tu veux qu'on le fasse.

## 🆓 Héberger 24/7 gratuitement via Replit + cron-job.org

Solution gratuite mais un peu plus bricolée que Railway. Le bot tourne sur **Replit**, et **cron-job.org** l'empêche de se mettre en veille en le "pingant" régulièrement.

### 1. Créer le Repl

1. Va sur https://replit.com et crée un compte (tu peux te connecter avec GitHub)
2. **Create Repl** → choisis le template **Python**
3. Une fois le Repl créé, **importe tes fichiers** : `bot.py`, `keep_alive.py`, `requirements.txt`
   - Tu peux glisser-déposer les fichiers directement dans l'explorateur de fichiers à gauche
   - Ou importer depuis GitHub si ton code y est déjà (Import from GitHub)

### 2. Configurer le token en sécurité (Secrets)

⚠️ Ne mets **jamais** ton token directement dans le code sur Replit (le projet peut être visible publiquement).

1. Dans Replit, clique sur l'icône **🔒 Secrets** (cadenas) dans le menu de gauche
2. Ajoute :
   - `DISCORD_TOKEN` = ton token Discord
   - `GUILD_ID` = l'identifiant de ton serveur

### 3. Lancer le bot

Clique sur le bouton **▶ Run** en haut. Dans la console, tu dois voir :
```
✅ Connecté en tant que TonBot#1234 | X commandes synchronisées.
```

Une fenêtre "Webview" doit aussi s'afficher dans Replit avec une URL du type :
```
https://discord-shop-bot.tonpseudo.repl.co
```
**Copie cette URL**, tu en auras besoin à l'étape suivante.

### 4. Empêcher la mise en veille avec cron-job.org

1. Va sur https://cron-job.org et crée un compte gratuit
2. **Create cronjob**
3. Dans **URL**, colle l'URL de ton Repl (celle copiée à l'étape 3)
4. Dans **Schedule**, choisis un intervalle toutes les **5 minutes**
5. Sauvegarde

Ce service va maintenant appeler ton Repl toutes les 5 minutes, ce qui empêche Replit de le mettre en veille, et ton bot Discord restera en ligne 24/7.

### ⚠️ Limites à connaître

- Cette méthode est moins fiable que Railway : Replit peut occasionnellement redémarrer le Repl, et les Repls gratuits ont des limites de ressources
- Si le bot passe hors ligne, va dans Replit et clique de nouveau sur **Run**
- Pour une boutique avec de vrais clients qui payent, une solution plus stable (Railway, VPS) est recommandée à terme

## 💾 Stockage des données

Tout est sauvegardé automatiquement dans `data.json` à côté de `bot.py` (boutique, articles, commandes). Pas de base de données externe nécessaire.

## ⚠️ Notes importantes

- **Le bot ne vérifie PAS automatiquement les paiements PayPal.** PayPal ne permet pas facilement de vérifier un paiement sans un vrai compte marchand + API PayPal (Business). Le système actuel fonctionne en confiance : le client paie, indique son numéro de commande en note, et l'admin confirme manuellement avec `/confirm_paiement`. Si tu veux une vérification automatique, il faudra intégrer l'API PayPal Business — dis-moi si tu veux qu'on le fasse.
- Format du lien PayPal.me recommandé : `https://paypal.me/tonpseudo` (sans slash à la fin)
- Ne partage jamais ton token Discord publiquement
- Pour héberger le bot 24/7 même PC éteint : Railway, Render, ou une VPS
