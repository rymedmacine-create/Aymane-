import discord
from discord.ui import View, Button
from discord import app_commands
import asyncio
import random
import time
import os
import re
import traceback
from collections import deque
from urllib.parse import quote
import stripe
from aiohttp import web
from curl_cffi import requests
from datetime import datetime, timezone

try:
    import mercari as mercari_api  # pip install mercari
except ImportError:
    mercari_api = None

TOKEN = os.environ.get("DISCORD_TOKEN") or os.environ.get("TOKEN")
STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET")

ROLE_ID = 1512217244082503710
LIEN_1MOIS = "https://buy.stripe.com/dRm28t2Akdm75zp5ed7Vm00"
LIEN_3MOIS = "https://buy.stripe.com/6oUfZja2Mci37Hx7ml7Vm02"

CANAUX = {
    "iphone 11 pro max": (1510863948810027119, 100),
    "iphone 11 pro": (1510863813283545188, 100),
    "iphone 11": (1510863724049600723, 100),
    "iphone 12 pro max": (1510864102241734707, 170),
    "iphone 12 pro": (1510864043349377114, 150),
    "iphone 12 mini": (1510866716131856465, 130),
    "iphone 12": (1510863996515778610, 100),
    "iphone 13 pro max": (1510866935527510167, 300),
    "iphone 13 pro": (1510866837326397471, 300),
    "iphone 13 mini": (1510864181308690622, 170),
    "iphone 13": (1510866798701051934, 250),
    "iphone 14 pro max": (1510867086627569784, 400),
    "iphone 14 pro": (1510867039776931961, 300),
    "iphone 14 plus": (1511368482938425415, 500),
    "iphone 14": (1510866988216488076, 280),
    "iphone 15 pro max": (1510867215434387540, 550),
    "iphone 15 pro": (1510867166117757009, 600),
    "iphone 15 plus": (1511368428370530454, 500),
    "iphone 15": (1510867119565312190, 300),
    "iphone 16 pro max": (1510867393327661137, 500),
    "iphone 16 pro": (1510867311144210462, 550),
    "iphone 16 plus": (1511368364033970327, 500),
    "iphone 16": (1510867255053779086, 640),
}

RECHERCHES = [
    "iphone 11", "iphone 12", "iphone 13",
    "iphone 14", "iphone 14 plus",
    "iphone 15", "iphone 15 plus",
    "iphone 16", "iphone 16 plus"
]
PRIX_MIN = 30

# ─── Mercari JP : recherches + taux de conversion ──────────────────────────────
RECHERCHES_MERCARI = [
    "iphone 11", "iphone 12", "iphone 13",
    "iphone 14", "iphone 14 plus",
    "iphone 15", "iphone 15 plus",
    "iphone 16", "iphone 16 plus"
]

# Taux JPY -> EUR. A ajuster manuellement de temps en temps (ou brancher une
# API de taux de change en direct si tu veux que ce soit toujours a jour).
JPY_TO_EUR = 0.0062

MAX_RESULTATS_MERCARI_PAR_RECHERCHE = 60  # mercari.search() paginate tout, on limite pour ne pas scanner trop longtemps

# --- Anti fuite memoire : on garde seulement les N derniers IDs vus ---
VUS_MAX = 5000
vus = set()
vus_ordre = deque(maxlen=VUS_MAX)

vus_mercari = set()
vus_mercari_ordre = deque(maxlen=VUS_MAX)


def marquer_vu(item_id):
    if item_id in vus:
        return
    if len(vus_ordre) == vus_ordre.maxlen:
        plus_ancien = vus_ordre[0]
        vus.discard(plus_ancien)
    vus_ordre.append(item_id)
    vus.add(item_id)


def marquer_vu_mercari(item_id):
    if item_id in vus_mercari:
        return
    if len(vus_mercari_ordre) == vus_mercari_ordre.maxlen:
        plus_ancien = vus_mercari_ordre[0]
        vus_mercari.discard(plus_ancien)
    vus_mercari_ordre.append(item_id)
    vus_mercari.add(item_id)


MOTS_EXCLUS = [
    "coque", "case", "cover", "housse", "etui", "bumper", "silicone",
    "verre", "glass", "film", "protection", "tempered", "screen", "ecran",
    "cable", "chargeur", "charger", "lightning", "usb", "adaptateur",
    "airpod", "ecouteur", "batterie", "powerbank", "dock",
    "hoesje", "handyhull", "hulle", "custodia", "funda",
    "fundas", "caja", "pellicola", "vetro", "privacy", "doorzichtig",
    "burga", "spigen", "otterbox", "casetify", "rhinoshield", "pela",
    "magsafe", "popsocket", "pop socket", "sticker", "skin", "anneau", "ring",
    "grip", "strap", "laniere", "lot de", "piece", "nappe",
    "reparation", "repair", "vitre", "chassis", "facade",
    "tiroir", "sim", "portefeuille", "wallet", "flip", "support"
]

# Mots a exclure specifiques aux annonces japonaises (Mercari)
MOTS_EXCLUS_JP = [
    "ケース", "カバー", "保護", "フィルム", "ガラス", "充電器", "ケーブル",
    "イヤホン", "バッテリー", "ジャンク品", "ジャンク", "本体のみ", "箱のみ",
    "付属品のみ", "レンズ", "画面のみ", "液晶", "部品", "修理"
]

USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4_1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14.4; rv:125.0) Gecko/20100101 Firefox/125.0",
]

_session = None
_session_requetes = 0
_session_creee = 0
SESSION_MAX_REQUETES = 15
SESSION_MAX_AGE = 900
_blocages_consecutifs = 0


# ─── BOUTONS DISCORD (Vinted) ──────────────────────────────────────────────────

class AnnonceView(View):
    def __init__(self, lien: str, titre: str, prix: float):
        super().__init__(timeout=None)
        self.lien = lien
        self.titre = titre
        self.prix = prix
        self.add_item(Button(
            label="🔗 Voir sur Vinted",
            style=discord.ButtonStyle.link,
            url=lien,
        ))

    @discord.ui.button(label="🔖 Sauvegarder", style=discord.ButtonStyle.success, custom_id="save")
    async def sauvegarder(self, interaction: discord.Interaction, button: Button):
        try:
            await interaction.user.send(
                f"📌 **Annonce sauvegardée !**\n"
                f"**{self.titre}** — {self.prix:.0f}€\n"
                f"{self.lien}"
            )
            await interaction.response.send_message("✅ Envoyé en DM !", ephemeral=True)
        except discord.Forbidden:
            await interaction.response.send_message(
                "❌ Impossible d'envoyer un DM (active tes DMs).", ephemeral=True
            )

    @discord.ui.button(label="❌ Ignorer", style=discord.ButtonStyle.danger, custom_id="ignore")
    async def ignorer(self, interaction: discord.Interaction, button: Button):
        try:
            await interaction.message.delete()
            await interaction.response.send_message("🗑️ Annonce supprimée.", ephemeral=True)
        except discord.HTTPException:
            pass


# ─── BOUTONS DISCORD (Mercari + ZenMarket) ─────────────────────────────────────

class AnnonceViewMercari(View):
    def __init__(self, lien_mercari: str, lien_zenmarket: str, titre: str, prix_eur: float):
        super().__init__(timeout=None)
        self.lien_mercari = lien_mercari
        self.lien_zenmarket = lien_zenmarket
        self.titre = titre
        self.prix_eur = prix_eur
        self.add_item(Button(
            label="🇯🇵 Voir sur Mercari",
            style=discord.ButtonStyle.link,
            url=lien_mercari,
        ))
        self.add_item(Button(
            label="📦 Commander via ZenMarket",
            style=discord.ButtonStyle.link,
            url=lien_zenmarket,
        ))

    @discord.ui.button(label="🔖 Sauvegarder", style=discord.ButtonStyle.success, custom_id="save_mercari")
    async def sauvegarder(self, interaction: discord.Interaction, button: Button):
        try:
            await interaction.user.send(
                f"📌 **Annonce Mercari sauvegardée !**\n"
                f"**{self.titre}** — ≈{self.prix_eur:.0f}€\n"
                f"Mercari : {self.lien_mercari}\n"
                f"ZenMarket : {self.lien_zenmarket}"
            )
            await interaction.response.send_message("✅ Envoyé en DM !", ephemeral=True)
        except discord.Forbidden:
            await interaction.response.send_message(
                "❌ Impossible d'envoyer un DM (active tes DMs).", ephemeral=True
            )

    @discord.ui.button(label="❌ Ignorer", style=discord.ButtonStyle.danger, custom_id="ignore_mercari")
    async def ignorer(self, interaction: discord.Interaction, button: Button):
        try:
            await interaction.message.delete()
            await interaction.response.send_message("🗑️ Annonce supprimée.", ephemeral=True)
        except discord.HTTPException:
            pass


# ─── SESSION VINTED ────────────────────────────────────────────────────────────

def nouvelle_session():
    global _session, _session_requetes, _session_creee, _blocages_consecutifs
    if _session is not None:
        try:
            _session.close()
        except Exception:
            pass
    ua = random.choice(USER_AGENTS)
    s = requests.Session(impersonate="chrome124")
    s.headers.update({
        "User-Agent": ua,
        "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
        "Accept": "application/json, text/plain, */*",
        "Sec-Fetch-Site": "same-origin",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Dest": "empty",
        "Referer": "https://www.vinted.fr/",
    })
    try:
        s.get("https://www.vinted.fr", timeout=15)
        time.sleep(random.uniform(2.0, 5.0))
        s.get("https://www.vinted.fr/catalog", timeout=15)
        time.sleep(random.uniform(2.0, 4.0))
    except Exception:
        pass
    _session = s
    _session_requetes = 0
    _session_creee = time.time()
    _blocages_consecutifs = 0
    print("Nouvelle session creee.")
    return _session


def get_session():
    global _session, _session_requetes, _session_creee
    now = time.time()
    if (
        _session is None
        or _session_requetes >= SESSION_MAX_REQUETES
        or (now - _session_creee) >= SESSION_MAX_AGE
    ):
        return nouvelle_session()
    return _session


def chercher_vinted(search):
    global _session_requetes, _blocages_consecutifs
    for tentative in range(3):
        try:
            session = get_session()
            url = "https://www.vinted.fr/api/v2/catalog/items"
            params = {"search_text": search, "order": "newest_first", "per_page": 48}
            time.sleep(random.uniform(3.0, 8.0))
            r = session.get(url, params=params, timeout=20)
            _session_requetes += 1
            if r.status_code in (401, 403, 429):
                _blocages_consecutifs += 1
                attente = random.uniform(30, 60) * min(_blocages_consecutifs, 4)
                nouvelle_session()
                time.sleep(attente)
                continue
            if r.status_code != 200 or not r.text:
                return []
            try:
                data = r.json()
            except Exception:
                return []
            _blocages_consecutifs = 0
            return data.get("items", [])
        except Exception as e:
            print(f"Erreur requete '{search}' (tentative {tentative+1}): {e}")
            time.sleep(random.uniform(5, 15))
    return []


def normaliser(titre: str) -> str:
    """Enleve les espaces normaux/japonais et met en minuscule, pour matcher
    des titres du style 'iPhone13Pro' ou 'iPhone　13　Pro'."""
    return titre.lower().replace(" ", "").replace("\u3000", "")


def extraire_modele(titre):
    titre = titre.lower()
    modeles = sorted(CANAUX.keys(), key=lambda x: -len(x))
    for modele in modeles:
        if modele in titre:
            return modele
    return None


def extraire_modele_normalise(titre):
    """Meme logique que extraire_modele mais tolerante aux espaces/majuscules
    japonaises (utile pour les titres Mercari)."""
    t = normaliser(titre)
    modeles = sorted(CANAUX.keys(), key=lambda x: -len(x))
    for modele in modeles:
        if normaliser(modele) in t:
            return modele
    return None


def contient_mot_exclu(titre):
    titre_l = titre.lower()
    return any(mot in titre_l for mot in MOTS_EXCLUS)


def contient_mot_exclu_mercari(titre):
    titre_l = titre.lower()
    if any(mot in titre_l for mot in MOTS_EXCLUS):
        return True
    return any(mot in titre for mot in MOTS_EXCLUS_JP)


# ─── ZENMARKET (proxy d'achat Japon -> France) ─────────────────────────────────

def zenmarket_link(mercari_url: str) -> str:
    """Construit un lien ZenMarket a partir d'une URL d'annonce Mercari.

    Important : ZenMarket ne publie pas d'API de deep-link officielle. Leur
    tutoriel officiel indique qu'il suffit de coller l'URL Mercari dans LEUR
    barre de recherche pour arriver directement sur la fiche produit
    (cf. zenmarket.jp/en/blog/post/11774/how-to-buy-from-mercari-japan).
    Ce lien reproduit ce comportement via un parametre de recherche. Teste-le
    une fois a la main : si ZenMarket a change son parametre de recherche, il
    te suffira d'ajuster la ligne ci-dessous. Le lien Mercari brut, lui,
    fonctionne toujours et est fourni en parallele dans chaque annonce.
    """
    return f"https://zenmarket.jp/en/page.aspx?page=Search&Keyword={quote(mercari_url, safe='')}"


# ─── SCANNER VINTED ─────────────────────────────────────────────────────────────

async def traiter_item(client, item):
    """Traite une annonce. Toute erreur ici est rattrapee, ne casse jamais le scanner."""
    item_id = item.get("id")
    if item_id is None or item_id in vus:
        return False
    marquer_vu(item_id)

    titre = item.get("title", "")
    if contient_mot_exclu(titre):
        return False
    modele = extraire_modele(titre)
    if not modele:
        return False

    canal_id, prix_max = CANAUX[modele]
    prix_brut = item.get("price", {})
    if isinstance(prix_brut, dict):
        prix = float(prix_brut.get("amount", 0))
    else:
        prix = float(prix_brut)
    if prix < PRIX_MIN or prix > prix_max:
        return False

    lien = f"https://www.vinted.fr/items/{item_id}"
    photo_url = None
    photos = item.get("photos") or []
    if photos:
        p = photos[0]
        photo_url = (
            p.get("full_size_url") or p.get("url")
            or p.get("thumbnails", [{}])[-1].get("url")
        )
    if not photo_url:
        photo_url = (
            item.get("photo", {}).get("full_size_url")
            or item.get("photo", {}).get("url")
        )

    canal = client.get_channel(canal_id)
    if not canal:
        return False

    embed = discord.Embed(title=titre, url=lien, color=0x09B1BA)
    embed.add_field(name="· Prix", value=f"**{prix:.0f}€**", inline=True)
    embed.add_field(name="· Modele", value=modele.title(), inline=True)
    embed.add_field(name="\u200b", value="\u200b", inline=True)
    embed.add_field(name="\u200b", value="\u200b", inline=True)
    embed.add_field(name="\u200b", value="\u200b", inline=True)
    embed.add_field(name="· Annonce", value=f"[Voir sur Vinted]({lien})", inline=True)
    if photo_url:
        embed.set_image(url=photo_url)
    embed.set_footer(text="Vinted")
    view = AnnonceView(lien=lien, titre=titre, prix=prix)

    try:
        await canal.send(embed=embed, view=view)
        return True
    except discord.HTTPException as e:
        # Ex: 503 Discord temporairement down. On log et on continue, on ne crash plus.
        print(f"Erreur envoi Discord (annonce ignoree, le bot continue) : {e}")
        return False


async def scanner(client):
    await client.wait_until_ready()
    print("Scan Vinted demarre...")
    while not client.is_closed():
        try:
            recherches = RECHERCHES.copy()
            random.shuffle(recherches)
            for search in recherches:
                try:
                    items = await asyncio.get_event_loop().run_in_executor(
                        None, chercher_vinted, search
                    )
                except Exception as e:
                    print(f"Erreur recuperation '{search}': {e}")
                    items = []

                nouvelles = 0
                for item in items:
                    try:
                        if await traiter_item(client, item):
                            nouvelles += 1
                    except Exception as e:
                        print(f"Erreur traitement annonce (ignoree): {e}")
                        traceback.print_exc()

                print(f"[{datetime.now().strftime('%H:%M:%S')}] Vinted {search}: {len(items)} annonces, {nouvelles} nouvelles")
                await asyncio.sleep(random.uniform(12, 20))

            pause = random.uniform(60, 120)
            print(f"Cycle Vinted termine. Prochaine analyse dans {pause:.0f}s...")
            await asyncio.sleep(pause)

        except Exception as e:
            # Filet de securite global : le scanner ne doit JAMAIS s'arreter completement.
            print(f"Erreur globale dans le scanner Vinted (le bot continue dans 30s) : {e}")
            traceback.print_exc()
            await asyncio.sleep(30)


# ─── SCANNER MERCARI (JP) ───────────────────────────────────────────────────────

def chercher_mercari(search_term):
    """Utilise la librairie 'mercari' (pip install mercari) qui simule les
    requetes API attendues par Mercari.jp, plutot que du scraping HTML fragile.
    """
    if mercari_api is None:
        return []
    resultats = []
    try:
        for i, item in enumerate(mercari_api.search(search_term)):
            resultats.append(item)
            if i + 1 >= MAX_RESULTATS_MERCARI_PAR_RECHERCHE:
                break
    except Exception as e:
        print(f"Erreur recherche Mercari '{search_term}': {e}")
    return resultats


async def traiter_item_mercari(client, item):
    item_id = getattr(item, "id", None)
    if not item_id or item_id in vus_mercari:
        return False
    marquer_vu_mercari(item_id)

    titre = getattr(item, "productName", "") or ""
    if contient_mot_exclu_mercari(titre):
        return False
    modele = extraire_modele_normalise(titre)
    if not modele:
        return False

    canal_id, prix_max_eur = CANAUX[modele]

    try:
        prix_jpy = float(getattr(item, "price", 0) or 0)
    except (TypeError, ValueError):
        return False
    if prix_jpy <= 0:
        return False

    prix_eur = prix_jpy * JPY_TO_EUR
    if prix_eur < PRIX_MIN or prix_eur > prix_max_eur:
        return False

    lien_mercari = getattr(item, "productURL", None)
    if not lien_mercari:
        return False
    lien_zen = zenmarket_link(lien_mercari)

    canal = client.get_channel(canal_id)
    if not canal:
        return False

    embed = discord.Embed(title=titre, url=lien_mercari, color=0xFF0211)
    embed.add_field(name="· Prix", value=f"**≈{prix_eur:.0f}€** ({prix_jpy:.0f}¥)", inline=True)
    embed.add_field(name="· Modele", value=modele.title(), inline=True)
    embed.add_field(name="\u200b", value="\u200b", inline=True)
    embed.add_field(name="· Mercari", value=f"[Voir l'annonce]({lien_mercari})", inline=True)
    embed.add_field(name="· ZenMarket", value=f"[Commander (proxy JP→FR)]({lien_zen})", inline=True)
    embed.add_field(name="\u200b", value="\u200b", inline=True)

    image_url = getattr(item, "imageURL", None)
    if image_url:
        embed.set_image(url=image_url)
    embed.set_footer(text="Mercari JP • expedie via ZenMarket")
    view = AnnonceViewMercari(lien_mercari, lien_zen, titre, prix_eur)

    try:
        await canal.send(embed=embed, view=view)
        return True
    except discord.HTTPException as e:
        print(f"Erreur envoi Discord Mercari (annonce ignoree, le bot continue) : {e}")
        return False


async def scanner_mercari(client):
    await client.wait_until_ready()
    if mercari_api is None:
        print("⚠️ Module 'mercari' non installe (pip install mercari) — scanner Mercari desactive.")
        return

    print("Scan Mercari demarre...")
    while not client.is_closed():
        try:
            recherches = RECHERCHES_MERCARI.copy()
            random.shuffle(recherches)
            for search_term in recherches:
                try:
                    items = await asyncio.get_event_loop().run_in_executor(
                        None, chercher_mercari, search_term
                    )
                except Exception as e:
                    print(f"Erreur recuperation Mercari '{search_term}': {e}")
                    items = []

                nouvelles = 0
                for item in items:
                    try:
                        if await traiter_item_mercari(client, item):
                            nouvelles += 1
                    except Exception as e:
                        print(f"Erreur traitement annonce Mercari (ignoree): {e}")
                        traceback.print_exc()

                print(f"[{datetime.now().strftime('%H:%M:%S')}] Mercari {search_term}: {len(items)} annonces, {nouvelles} nouvelles")
                await asyncio.sleep(random.uniform(15, 25))

            pause = random.uniform(90, 150)
            print(f"Cycle Mercari termine. Prochaine analyse dans {pause:.0f}s...")
            await asyncio.sleep(pause)

        except Exception as e:
            print(f"Erreur globale dans le scanner Mercari (le bot continue dans 30s) : {e}")
            traceback.print_exc()
            await asyncio.sleep(30)


# ─── WEBHOOK STRIPE ────────────────────────────────────────────────────────────

async def stripe_webhook(request):
    payload = await request.read()
    sig_header = request.headers.get("Stripe-Signature")
    try:
        event = stripe.Webhook.construct_event(payload, sig_header, STRIPE_WEBHOOK_SECRET)
    except Exception as e:
        return web.Response(status=400, text=str(e))
    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        discord_id = session.get("metadata", {}).get("discord_id")
        if discord_id:
            for guild in client.guilds:
                try:
                    member = guild.get_member(int(discord_id)) or await guild.fetch_member(int(discord_id))
                except discord.NotFound:
                    continue
                except Exception as e:
                    print(f"Erreur fetch_member: {e}")
                    continue
                if member:
                    role = guild.get_role(ROLE_ID)
                    if role:
                        try:
                            await member.add_roles(role)
                            print(f"Role donne a {member.name}")
                        except discord.HTTPException as e:
                            print(f"Erreur ajout role: {e}")
    return web.Response(status=200, text="ok")


async def start_webhook_server():
    app = web.Application()
    app.router.add_post("/webhook", stripe_webhook)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", 8080)
    await site.start()
    print("Serveur webhook demarre sur le port 8080")


# ─── COMMANDE /payer ───────────────────────────────────────────────────────────

intents = discord.Intents.default()
intents.members = True
client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)

@tree.command(name="payer", description="Obtenir l'accès premium")
async def payer(interaction: discord.Interaction):
    embed = discord.Embed(title="💳 Choisir ton abonnement", color=0x09B1BA)
    embed.add_field(name="1 mois", value=f"[Payer 1 mois]({LIEN_1MOIS})", inline=False)
    embed.add_field(name="3 mois", value=f"[Payer 3 mois]({LIEN_3MOIS})", inline=False)
    await interaction.response.send_message(embed=embed, ephemeral=True)


# ─── DEMARRAGE ─────────────────────────────────────────────────────────────────

@client.event
async def on_ready():
    print(f"Bot connecte : {client.user}")
    await tree.sync()
    client.loop.create_task(scanner(client))
    client.loop.create_task(scanner_mercari(client))
    client.loop.create_task(start_webhook_server())

client.run(TOKEN) 
