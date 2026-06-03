import discord
import asyncio
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

RECHERCHES = ["iphone 11", "iphone 12", "iphone 13", "iphone 14", "iphone 14 plus", "iphone 15", "iphone 15 plus", "iphone 16", "iphone 16 plus"]
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

def get_canal_et_prix(titre):
    titre_lower = titre.lower()
    for mot in MOTS_EXCLUS:
        if mot in titre_lower:
            return None, None
    for modele, (canal_id, prix_max) in CANAUX.items():
        if modele in titre_lower:
            return canal_id, prix_max
    return None, None

def chercher_vinted(search):
    try:
        session = requests.Session(impersonate="chrome110")
        session.get("https://www.vinted.fr", timeout=10)
        url = "https://www.vinted.fr/api/v2/catalog/items"
        params = {"search_text": search, "order": "newest_first", "per_page": 20, "price_from": PRIX_MIN}
        r = session.get(url, params=params, timeout=10)
        return r.json().get("items", [])
    except Exception as e:
        print(f"Erreur requete: {e}")
        return []

def est_recent(item):
    try:
        date_str = item.get("created_at_ts") or item.get("updated_at_ts")
        if not date_str:
            return True
        if isinstance(date_str, int):
            diff = datetime.now(timezone.utc).timestamp() - date_str
        else:
            date = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            diff = (datetime.now(timezone.utc) - date).total_seconds()
        return diff <= 900
    except:
        return True

intents = discord.Intents.default()

async def scanner():
    client = discord.Client(intents=intents)

    @client.event
    async def on_ready():
        print(f"Bot connecte : {client.user}")
        asyncio.create_task(boucle(client))

    async def boucle(client):
        print("Scan demarre...")
        while True:
            try:
                for search in RECHERCHES:
                    items = chercher_vinted(search)
                    print(f"{search}: {len(items)} annonces")
                    for item in items:
                        item_id = item.get("id")
                        titre = item.get("title", "")
                        canal_id, prix_max = get_canal_et_prix(titre)
                        prix = item.get("price", {})
                        if isinstance(prix, dict):
                            prix_val = float(prix.get("amount", 0))
                        else:
                            prix_val = float(prix) if prix else 0
                        if item_id and item_id not in vus and canal_id and est_recent(item) and PRIX_MIN <= prix_val <= prix_max:
                            vus.add(item_id)
                            channel = client.get_channel(canal_id)
                            if not channel:
                                continue
                            url = f"https://www.vinted.fr/items/{item_id}"
                            etat = item.get("condition", "Non precis")
                            taille = item.get("size_title", "")
                            vendeur = item.get("user", {})
                            nom_vendeur = vendeur.get("login", "?")
                            embed = discord.Embed(title=f"{titre}", url=url, color=0x09B1BA)
                            embed.add_field(name="Prix", value=f"{prix_val} EUR", inline=True)
                            embed.add_field(name="Etat", value=etat, inline=True)
                            if taille:
                                embed.add_field(name="Stockage", value=taille, inline=True)
                            embed.add_field(name="Vendeur", value=nom_vendeur, inline=True)
                            embed.add_field(name="Lien", value=f"[Voir l annonce]({url})", inline=False)
                            photo = item.get("photo", {})
                            if photo:
                                img_url = photo.get("full_size_url") or photo.get("url")
                                if img_url:
                                    embed.set_image(url=img_url)
                            await channel.send(embed=embed)
                            print(f"OK {titre} {prix_val}EUR")
                    await asyncio.sleep(3)
            except Exception as e:
                print(f"Erreur {e}")
            await asyncio.sleep(90)

    while True:
        try:
            await client.start(TOKEN)
        except Exception as e:
            print(f"Reconnexion 10s {e}")
            await asyncio.sleep(10)

asyncio.run(scanner())
