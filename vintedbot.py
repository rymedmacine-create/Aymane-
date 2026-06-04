import discord
from discord.ui import View, Button
import asyncio
import random
import time
from curl_cffi import requests
from datetime import datetime, timezone

TOKEN = __import__("os").environ.get("DISCORD_TOKEN") or __import__("os").environ.get("TOKEN")

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
    "iphone 13 mini": (1510864102241734707, 170),
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
vus = set()

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
SESSION_MAX_REQUETES = 40
SESSION_MAX_AGE = 600


# ─────────────────────────────────────────────
#  BOUTONS DISCORD
# ─────────────────────────────────────────────

class AnnonceView(View):
    """Boutons attachés à chaque annonce."""

    def __init__(self, lien: str, titre: str, prix: float):
        super().__init__(timeout=None)  # persistent (pas de timeout)
        self.lien = lien
        self.titre = titre
        self.prix = prix

        # Bouton lien direct (style Link = pas de callback nécessaire)
        self.add_item(Button(
            label="🔗 Voir sur Vinted",
            style=discord.ButtonStyle.link,
            url=lien,
        ))

    @discord.ui.button(label="🔖 Sauvegarder", style=discord.ButtonStyle.success, custom_id="save")
    async def sauvegarder(self, interaction: discord.Interaction, button: Button):
        """Envoie un DM à l'utilisateur avec le lien sauvegardé."""
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
        """Supprime le message d'annonce."""
        await interaction.message.delete()
        # Petite confirmation éphémère (visible uniquement par l'utilisateur)
        await interaction.response.send_message("🗑️ Annonce supprimée.", ephemeral=True)


# ─────────────────────────────────────────────
#  SESSION VINTED
# ─────────────────────────────────────────────

def nouvelle_session():
    global _session, _session_requetes, _session_creee
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
        time.sleep(random.uniform(1.5, 3.0))
    except Exception:
        pass
    _session = s
    _session_requetes = 0
    _session_creee = time.time()
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
    global _session_requetes
    try:
        session = get_session()
        url = "https://www.vinted.fr/api/v2/catalog/items"
        params = {"search_text": search, "order": "newest_first", "per_page": 96}
        time.sleep(random.uniform(1.0, 3.5))
        r = session.get(url, params=params, timeout=15)
        _session_requetes += 1
        if r.status_code in (401, 403, 429):
            print(f"Blocage detecte ({r.status_code}), rotation de session...")
            nouvelle_session()
            time.sleep(random.uniform(10, 20))
            r = _session.get(url, params=params, timeout=15)
            _session_requetes += 1
        if not r.text or r.status_code != 200:
            print(f"Reponse inattendue ({r.status_code}) pour '{search}'")
            return []
        try:
            data = r.json()
        except Exception:
            return []
        return data.get("items", [])
    except Exception as e:
        print(f"Erreur requete '{search}': {e}")
        return []


def extraire_modele(titre):
    titre = titre.lower()
    modeles = sorted(CANAUX.keys(), key=lambda x: -len(x))
    for modele in modeles:
        if modele in titre:
            return modele
    return None


def contient_mot_exclu(titre):
    titre = titre.lower()
    return any(mot in titre for mot in MOTS_EXCLUS)


# ─────────────────────────────────────────────
#  SCANNER
# ─────────────────────────────────────────────

async def scanner(client):
    await client.wait_until_ready()
    print("Scan demarre...")

    while not client.is_closed():
        recherches = RECHERCHES.copy()
        random.shuffle(recherches)

        for search in recherches:
            items = chercher_vinted(search)
            nouvelles = 0

            for item in items:
                item_id = item.get("id")
                if item_id in vus:
                    continue
                vus.add(item_id)

                titre = item.get("title", "")
                if contient_mot_exclu(titre):
                    continue

                modele = extraire_modele(titre)
                if not modele:
                    continue

                canal_id, prix_max = CANAUX[modele]
                prix_brut = item.get("price", {})
                if isinstance(prix_brut, dict):
                    prix = float(prix_brut.get("amount", 0))
                else:
                    prix = float(prix_brut)

                if prix < PRIX_MIN or prix > prix_max:
                    continue

                lien = f"https://www.vinted.fr/items/{item_id}"

                photo_url = None
                photos = item.get("photos") or []
                if photos:
                    p = photos[0]
                    photo_url = (
                        p.get("full_size_url")
                        or p.get("url")
                        or p.get("thumbnails", [{}])[-1].get("url")
                    )
                if not photo_url:
                    photo_url = (
                        item.get("photo", {}).get("full_size_url")
                        or item.get("photo", {}).get("url")
                    )

                canal = client.get_channel(canal_id)
                if canal:
                    embed = discord.Embed(
                        title=titre,
                        url=lien,
                        color=0x09B1BA,
                    )
                    embed.add_field(name="· Prix",    value=f"**{prix:.0f}€**",             inline=True)
                    embed.add_field(name="· Modele",  value=modele.title(),                  inline=True)
                    embed.add_field(name="\u200b",    value="\u200b",                        inline=True)
                    embed.add_field(name="\u200b",    value="\u200b",                        inline=True)
                    embed.add_field(name="\u200b",    value="\u200b",                        inline=True)
                    embed.add_field(name="· Annonce", value=f"[Voir sur Vinted]({lien})",    inline=True)
                    if photo_url:
                        embed.set_image(url=photo_url)
                    embed.set_footer(text="Vinted")

                    # ✅ On envoie l'embed + les boutons
                    view = AnnonceView(lien=lien, titre=titre, prix=prix)
                    await canal.send(embed=embed, view=view)
                    nouvelles += 1

            print(f"[{datetime.now().strftime('%H:%M:%S')}] {search}: {len(items)} annonces, {nouvelles} nouvelles")
            await asyncio.sleep(random.uniform(4, 9))

        pause = random.uniform(25, 45)
        print(f"Cycle termine. Prochaine analyse dans {pause:.0f}s...")
        await asyncio.sleep(pause)


# ─────────────────────────────────────────────
#  DEMARRAGE
# ─────────────────────────────────────────────

intents = discord.Intents.default()
client = discord.Client(intents=intents)


@client.event
async def on_ready():
    print(f"Bot connecte : {client.user}")
    client.loop.create_task(scanner(client))


client.run(TOKEN)
