import json
import os
from datetime import datetime, timezone
from curl_cffi import requests

NTFY_TOPIC = os.environ.get("NTFY_TOPIC", "")
STATE_FILE = "stocks.json"

# Liste des produits et enseignes à surveiller
# Vous pouvez ajouter autant d'URLs (pages produits ou API Click & Collect JSON) que souhaité
TARGETS = [
    {
        "id": "ps5-standard-direct",
        "name": "PS5 Standard (Édition Disque)",
        "shop": "PlayStation Direct FR",
        "type": "Internet",
        "url": "https://direct.playstation.com/fr-fr/buy-consoles/playstation5-console",
        "keyword_in_stock": "Ajouter",
        "keyword_out_of_stock": "Actuellement indisponible"
    },
    {
        "id": "xbox-series-x-ms",
        "name": "Xbox Series X 1 To",
        "shop": "Microsoft Store FR",
        "type": "Internet",
        "url": "https://www.xbox.com/fr-FR/consoles/xbox-series-x",
        "keyword_in_stock": "Acheter",
        "keyword_out_of_stock": "Rupture de stock"
    },
    {
        "id": "gta6-ps5-micromania",
        "name": "GTA VI (PS5)",
        "shop": "Micromania (Web & Retrait 1h)",
        "type": "Internet / Magasin",
        "url": "https://www.micromania.fr/",
        "keyword_in_stock": "Ajouter au panier",
        "keyword_out_of_stock": "Indisponible"
    }
]

def load_previous_state():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return {item["id"]: item["in_stock"] for item in data.get("items", [])}
        except Exception:
            return {}
    return {}

def send_notification(product_name, shop, url):
    if not NTFY_TOPIC:
        return
    try:
        requests.post(
            f"https://ntfy.sh/{NTFY_TOPIC}",
            data=f"{product_name} disponible chez {shop} !".encode("utf-8"),
            headers={
                "Title": f"DISPO : {product_name}",
                "Priority": "high",
                "Tags": "video_game,rotating_light",
                "Click": url
            },
            timeout=10
        )
    except Exception as e:
        print(f"Erreur notification : {e}")

def check_targets():
    previous_state = load_previous_state()
    results = []

    for target in TARGETS:
        in_stock = False
        status_label = "Vérification impossible (blocage)"

        try:
            resp = requests.get(target["url"], impersonate="chrome", timeout=15)
            html = resp.text

            if resp.status_code == 200:
                has_in = target["keyword_in_stock"].lower() in html.lower()
                has_out = target["keyword_out_of_stock"].lower() in html.lower()

                if has_in and not has_out:
                    in_stock = True
                    status_label = "En stock"
                else:
                    in_stock = False
                    status_label = "Rupture de stock"
            else:
                status_label = f"Erreur HTTP {resp.status_code}"

        except Exception as e:
            status_label = "Erreur réseau"
            print(f"Erreur sur {target['id']} : {e}")

        # Déclenche l'alerte uniquement lors du passage de Rupture à En stock
        was_in_stock = previous_state.get(target["id"], False)
        if in_stock and not was_in_stock:
            send_notification(target["name"], target["shop"], target["url"])

        results.append({
            "id": target["id"],
            "name": target["name"],
            "shop": target["shop"],
            "type": target["type"],
            "url": target["url"],
            "in_stock": in_stock,
            "status": status_label
        })

    output = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "items": results
    }

    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    check_targets()
