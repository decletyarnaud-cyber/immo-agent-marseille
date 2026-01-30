"""
Configuration settings for Immo-Agent
"""
from pathlib import Path
import os

# Base paths
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
LAWYERS_DIR = DATA_DIR / "lawyers"
EXPORTS_DIR = DATA_DIR / "exports"

# Database
DATABASE_PATH = DATA_DIR / "immo_agent.db"

# Geographic scope
DEPARTMENTS = ["13", "83"]  # Bouches-du-Rhône, Var

CITIES = {
    # Marseille - tous les arrondissements
    "marseille": {
        "codes_postaux": [f"130{i:02d}" for i in range(1, 17)],
        "department": "13"
    },
    # Aix-en-Provence et environs
    "aix-en-provence": {
        "codes_postaux": ["13100", "13090", "13540"],
        "department": "13"
    },
    # Toulon et environs
    "toulon": {
        "codes_postaux": ["83000", "83100", "83200"],
        "department": "83"
    },
    # Bouches-du-Rhône (13) - Principales villes
    "aubagne": {"codes_postaux": ["13400"], "department": "13"},
    "la-ciotat": {"codes_postaux": ["13600"], "department": "13"},
    "cassis": {"codes_postaux": ["13260"], "department": "13"},
    "martigues": {"codes_postaux": ["13500"], "department": "13"},
    "istres": {"codes_postaux": ["13800"], "department": "13"},
    "fos-sur-mer": {"codes_postaux": ["13270"], "department": "13"},
    "vitrolles": {"codes_postaux": ["13127"], "department": "13"},
    "marignane": {"codes_postaux": ["13700"], "department": "13"},
    "salon-de-provence": {"codes_postaux": ["13300"], "department": "13"},
    "arles": {"codes_postaux": ["13200"], "department": "13"},
    "gardanne": {"codes_postaux": ["13120"], "department": "13"},
    "miramas": {"codes_postaux": ["13140"], "department": "13"},
    "port-de-bouc": {"codes_postaux": ["13110"], "department": "13"},
    "berre-l-etang": {"codes_postaux": ["13130"], "department": "13"},
    "allauch": {"codes_postaux": ["13190"], "department": "13"},
    "plan-de-cuques": {"codes_postaux": ["13380"], "department": "13"},
    "gemenos": {"codes_postaux": ["13420"], "department": "13"},
    "roquevaire": {"codes_postaux": ["13360"], "department": "13"},
    "pennes-mirabeau": {"codes_postaux": ["13170"], "department": "13"},
    "bouc-bel-air": {"codes_postaux": ["13320"], "department": "13"},
    "cabries": {"codes_postaux": ["13480"], "department": "13"},
    "fuveau": {"codes_postaux": ["13710"], "department": "13"},
    "trets": {"codes_postaux": ["13530"], "department": "13"},
    "lambesc": {"codes_postaux": ["13410"], "department": "13"},
    "eguilles": {"codes_postaux": ["13510"], "department": "13"},
    # Var (83) - Principales villes ressort TJ Toulon
    "hyeres": {"codes_postaux": ["83400"], "department": "83"},
    "la-seyne-sur-mer": {"codes_postaux": ["83500"], "department": "83"},
    "six-fours-les-plages": {"codes_postaux": ["83140"], "department": "83"},
    "sanary-sur-mer": {"codes_postaux": ["83110"], "department": "83"},
    "bandol": {"codes_postaux": ["83150"], "department": "83"},
    "la-garde": {"codes_postaux": ["83130"], "department": "83"},
    "ollioules": {"codes_postaux": ["83190"], "department": "83"},
    "la-valette-du-var": {"codes_postaux": ["83160"], "department": "83"},
    "le-pradet": {"codes_postaux": ["83220"], "department": "83"},
    "carqueiranne": {"codes_postaux": ["83320"], "department": "83"},
    "la-crau": {"codes_postaux": ["83260"], "department": "83"},
    "sollies-pont": {"codes_postaux": ["83210"], "department": "83"},
    "cuers": {"codes_postaux": ["83390"], "department": "83"},
    "brignoles": {"codes_postaux": ["83170"], "department": "83"},
    "le-beausset": {"codes_postaux": ["83330"], "department": "83"},
    "saint-cyr-sur-mer": {"codes_postaux": ["83270"], "department": "83"},
    "le-castellet": {"codes_postaux": ["83330"], "department": "83"},
    "saint-maximin": {"codes_postaux": ["83470"], "department": "83"},
}

# All postal codes to monitor (explicitement listés)
ALL_POSTAL_CODES = []
for city_data in CITIES.values():
    ALL_POSTAL_CODES.extend(city_data["codes_postaux"])

# Fonction helper pour vérifier si un code postal est dans la zone cible
def is_in_target_area(code_postal: str) -> bool:
    """Vérifie si un code postal est dans notre zone de surveillance"""
    if not code_postal:
        return False
    if code_postal in ALL_POSTAL_CODES:
        return True
    # Fallback: accepter tout le département surveillé
    return code_postal[:2] in DEPARTMENTS

# Sources configuration
SOURCES = {
    "licitor": {
        "base_url": "https://www.licitor.com",
        "search_url": "https://www.licitor.com/ventes-judiciaires-immobilieres",
        "enabled": True,
        "priority": 1
    },
    "encheres_publiques": {
        "base_url": "https://www.encheres-publiques.com",
        "search_url": "https://www.encheres-publiques.com/ventes/immobilier",
        "enabled": True,
        "priority": 2
    },
    "vench": {
        "base_url": "https://www.vench.fr",
        "search_url": "https://www.vench.fr/liste-des-ventes-au-tribunal-judiciaire-marseille.html",
        "enabled": True,
        "priority": 3
    }
}

# Tribunaux
TRIBUNAUX = {
    "tj_marseille": {
        "nom": "Tribunal Judiciaire de Marseille",
        "ville": "Marseille",
        "department": "13"
    },
    "tj_aix": {
        "nom": "Tribunal Judiciaire d'Aix-en-Provence",
        "ville": "Aix-en-Provence",
        "department": "13"
    },
    "tj_toulon": {
        "nom": "Tribunal Judiciaire de Toulon",
        "ville": "Toulon",
        "department": "83"
    }
}

# Scraping settings
SCRAPING = {
    "delay_between_requests": 1.5,  # seconds
    "max_retries": 3,
    "timeout": 30,
    "user_agent": "ImmoAgent/1.0 (Contact: immo-agent@example.com)"
}

# DVF API settings
DVF = {
    "base_url": "https://api.cquest.org/dvf",
    "data_gouv_url": "https://files.data.gouv.fr/geo-dvf/latest/csv",
    "years_to_fetch": 5
}

# Analysis settings
ANALYSIS = {
    "good_deal_threshold": 0.20,  # 20% below market
    "opportunity_threshold": 0.30,  # 30% below market
    "comparison_radius_km": 1.0  # Compare with sales within 1km
}

# Streamlit settings
WEB = {
    "host": "localhost",
    "port": 8501,
    "title": "Immo-Agent - Enchères Judiciaires Marseille & Région"
}
