"""
Catalogue des sites d'avocats avec pages d'enchères immobilières
Région Marseille / Aix-en-Provence / Toulon
"""

# Format: clé = nom normalisé pour matching, valeur = infos du cabinet
LAWYERS_CATALOG = {
    # Marseille
    "mascaron": {
        "cabinet": "SELARL Mascaron Avocats",
        "avocats": ["Philippe Cornet"],
        "site": "https://www.mascaron-avocats.com",
        "page_encheres": "https://www.mascaron-avocats.com/domaines-dintervention/encheres-immobilieres/",
        "ville": "Marseille",
        "telephone": "04 91 33 60 60",
    },
    "cohen_guedj": {
        "cabinet": "SCP Cohen - Guedj - Montéro - Daval-Guedj",
        "avocats": ["Paul Guedj", "Cohen", "Montéro", "Daval-Guedj"],
        "site": "https://www.cohen-guedj-avocats.com",
        "page_encheres": "https://www.cohen-guedj-avocats.com/encheres-immobilieres/",
        "ville": "Marseille",
    },
    "eklar": {
        "cabinet": "SELARL Eklar Avocats",
        "avocats": ["Thomas", "Thomas D'Journo", "Djourno"],
        "site": "https://www.eklar.com",
        "page_encheres": "https://www.eklar.com/vente",
        "ville": "Marseille",
        "telephone": "04 13 24 13 63",
    },
    "naudin": {
        "cabinet": "Cabinet Naudin Avocats",
        "avocats": ["Anne-Cécile Naudin", "Naudin"],
        "site": "https://www.cabinetnaudin.com",
        "page_encheres": "https://www.cabinetnaudin.com/ventes-aux-encheres-immobilieres-w1.html",
        "ville": "Marseille",
    },
    "imavocats": {
        "cabinet": "SELARL Imavocats",
        "avocats": ["Laetitia Criscola"],
        "site": "https://www.imavocats.com",
        "page_encheres": None,
        "ville": "Marseille",
    },
    "lescudier": {
        "cabinet": "SELARL Lescudier et Associés",
        "avocats": ["Dorothée Soulas", "Lescudier"],
        "site": "https://www.lescudier-avocats.fr",
        "page_encheres": None,
        "ville": "Marseille",
    },
    "semelaigne": {
        "cabinet": "AARPI Semelaigne - Dupuy - Delcroix",
        "avocats": ["Pascal Delcroix", "Semelaigne", "Dupuy"],
        "site": None,
        "page_encheres": None,
        "ville": "Marseille",
    },
    "plantard": {
        "cabinet": "SCP Plantard - Rochas - Rouillier - Viry et Roustan Beridot",
        "avocats": ["Julie Rouillier", "Plantard", "Rochas", "Viry", "Roustan Beridot"],
        "site": None,
        "page_encheres": None,
        "ville": "Aix-en-Provence",
    },
    "travert": {
        "cabinet": "AARPI Travert - Robert - Ceyte",
        "avocats": ["Pierre Robert", "Travert", "Ceyte"],
        "site": None,
        "page_encheres": None,
        "ville": "Toulon",
    },
}


def find_lawyer_info(avocat_nom: str = None, cabinet: str = None) -> dict:
    """
    Trouve les infos d'un avocat/cabinet dans le catalogue

    Args:
        avocat_nom: Nom de l'avocat (ex: "Philippe Cornet")
        cabinet: Nom du cabinet (ex: "SELARL Mascaron Avocats")

    Returns:
        Dict avec infos du cabinet ou None
    """
    if not avocat_nom and not cabinet:
        return None

    search_text = f"{avocat_nom or ''} {cabinet or ''}".lower()

    for key, info in LAWYERS_CATALOG.items():
        # Match par clé
        if key in search_text:
            return info

        # Match par nom de cabinet
        if info.get("cabinet") and info["cabinet"].lower() in search_text:
            return info

        # Match par nom d'avocat
        for avocat in info.get("avocats", []):
            if avocat.lower() in search_text:
                return info

    return None


def get_encheres_url(avocat_nom: str = None, cabinet: str = None) -> str:
    """
    Retourne l'URL de la page enchères du cabinet si connue
    """
    info = find_lawyer_info(avocat_nom, cabinet)
    if info:
        return info.get("page_encheres") or info.get("site")
    return None


def get_all_encheres_pages() -> list:
    """
    Retourne toutes les pages d'enchères connues pour scraping
    """
    pages = []
    for key, info in LAWYERS_CATALOG.items():
        if info.get("page_encheres"):
            pages.append({
                "cabinet": info["cabinet"],
                "url": info["page_encheres"],
                "ville": info.get("ville"),
            })
    return pages
