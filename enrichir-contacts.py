#!/usr/bin/env python3
"""
Enrichisseur de contacts crèches.
Va chercher les infos manquantes (téléphone, email, site web)
depuis OpenStreetMap + recherches web, et met à jour creches-rennes.json.

Usage : python3 enrichir-contacts.py
"""
import json, os, re, sys
from urllib.request import urlopen, Request
from urllib.parse import quote
import urllib.error

JSON_PATH = os.path.join(os.path.dirname(__file__), "creches-rennes.json")

OVERPASS_URL = "https://overpass-api.de/api/interpreter"
OPENCAGE_KEY = ""  # Optionnel : clé API OpenCage pour meilleur géocoding

def overpass_query(query):
    url = f"{OVERPASS_URL}?data={quote(query, safe='')}"
    req = Request(url, headers={"User-Agent": "CrecheEnricher/1.0"})
    try:
        with urlopen(req, timeout=30) as r:
            return json.loads(r.read())
    except Exception as e:
        print(f"  ⚠️  Erreur Overpass : {e}")
        return None

def search_osm(name, city="Rennes"):
    """Cherche un établissement par nom dans OSM via Overpass."""
    q = f'[out:json][timeout:15];nwr["name"~"{quote(name)}"](area["name"="{city}"]);out center tags 15;'
    data = overpass_query(q)
    if not data or "elements" not in data:
        return None
    for el in data["elements"]:
        tags = el.get("tags", {})
        n = tags.get("name", "")
        if name.lower().strip() in n.lower():
            return tags
    # Fallback : prendre le premier résultat avec un nom proche
    for el in data["elements"]:
        tags = el.get("tags", {})
        n = tags.get("name", "")
        if n:
            return tags
    return None

def extract_contact(tags):
    """Extrait tous les contacts depuis les tags OSM."""
    contact = {}
    if tags.get("phone"):
        contact["phone"] = tags["phone"]
    if tags.get("contact:phone"):
        contact["phone"] = tags["contact:phone"]
    if tags.get("mobile"):
        contact["phone"] = tags["mobile"]
    if tags.get("contact:mobile") and not contact.get("phone"):
        contact["phone"] = tags["contact:mobile"]
    if tags.get("email"):
        contact["email"] = tags["email"]
    if tags.get("contact:email"):
        contact["email"] = tags["contact:email"]
    if tags.get("website"):
        contact["website"] = tags["website"]
    if tags.get("contact:website"):
        contact["website"] = tags["contact:website"]
    if not contact.get("website") and tags.get("url"):
        contact["website"] = tags["url"]
    # Adresse
    addr_parts = []
    for k in ["addr:full","addr:street","addr:city","addr:postcode"]:
        if tags.get(k):
            addr_parts.append(tags[k])
    if addr_parts:
        contact["address"] = ", ".join(addr_parts)
    return contact

def clean_phone(p):
    p = re.sub(r'[^\d+ ]', '', p)
    return p.strip()

def main():
    print("=" * 50)
    print("🔍 Enrichisseur de contacts crèches")
    print("=" * 50)

    if not os.path.exists(JSON_PATH):
        print(f"❌ Fichier {JSON_PATH} introuvable")
        sys.exit(1)

    with open(JSON_PATH, encoding="utf-8") as f:
        data = json.load(f)

    total = len(data)
    with_phone = sum(1 for d in data if d.get("phone"))
    with_email = sum(1 for d in data if d.get("email"))
    with_website = sum(1 for d in data if d.get("website"))

    print(f"\n📊 État initial ({total} établissements) :")
    print(f"   📞 Téléphone : {with_phone}/{total}")
    print(f"   ✉️  Email     : {with_email}/{total}")
    print(f"   🌐 Site web  : {with_website}/{total}")

    enriched = 0
    for i, d in enumerate(data):
        name = d.get("name", "")
        if not name:
            continue

        has_phone = bool(d.get("phone"))
        has_email = bool(d.get("email"))
        has_website = bool(d.get("website"))

        if has_phone and has_email and has_website:
            continue  # Déjà complet

        print(f"\n  [{i+1}/{total}] {name}...")
        tags = search_osm(name, d.get("city", "Rennes"))
        if tags:
            contact = extract_contact(tags)
            changed = False
            if not has_phone and contact.get("phone"):
                d["phone"] = clean_phone(contact["phone"])
                print(f"    ✅ Téléphone trouvé : {d['phone']}")
                changed = True
            if not has_email and contact.get("email"):
                d["email"] = contact["email"]
                print(f"    ✅ Email trouvé : {d['email']}")
                changed = True
            if not has_website and contact.get("website"):
                d["website"] = contact["website"]
                print(f"    ✅ Site web trouvé : {d['website']}")
                changed = True
            if not d.get("address") and contact.get("address"):
                d["address"] = contact["address"]
                print(f"    ✅ Adresse trouvée : {d['address'][:60]}")
                changed = True
            if changed:
                enriched += 1
        else:
            print(f"    ⚠️  Non trouvé dans OSM")

    # Sauvegarde
    with open(JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"\n" + "=" * 50)
    print(f"✅ Terminé ! {enriched} établissements enrichis")
    with_phone_end = sum(1 for d in data if d.get("phone"))
    with_email_end = sum(1 for d in data if d.get("email"))
    with_website_end = sum(1 for d in data if d.get("website"))
    print(f"   📞 Téléphone : {with_phone_end}/{total} (+{with_phone_end-with_phone})")
    print(f"   ✉️  Email     : {with_email_end}/{total} (+{with_email_end-with_email})")
    print(f"   🌐 Site web  : {with_website_end}/{total} (+{with_website_end-with_website})")
    print(f"\n📁 Fichier mis à jour : {JSON_PATH}")
    print(f"\n💡 Conseil : Exécute ce script régulièrement pour enrichir la base.")
    print(f"   Les données viennent d'OpenStreetMap — tu peux aussi y contribuer !")

if __name__ == "__main__":
    main()
