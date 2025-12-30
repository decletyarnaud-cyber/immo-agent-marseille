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
    "marseille": {
        "codes_postaux": [f"130{i:02d}" for i in range(1, 17)],
        "department": "13"
    },
    "aix-en-provence": {
        "codes_postaux": ["13100", "13090", "13540"],
        "department": "13"
    },
    "toulon": {
        "codes_postaux": ["83000", "83100", "83200"],
        "department": "83"
    },
    "aubagne": {"codes_postaux": ["13400"], "department": "13"},
    "la-ciotat": {"codes_postaux": ["13600"], "department": "13"},
    "cassis": {"codes_postaux": ["13260"], "department": "13"},
    "martigues": {"codes_postaux": ["13500"], "department": "13"},
    "istres": {"codes_postaux": ["13800"], "department": "13"},
    "hyeres": {"codes_postaux": ["83400"], "department": "83"},
    "la-seyne-sur-mer": {"codes_postaux": ["83500"], "department": "83"},
    "six-fours-les-plages": {"codes_postaux": ["83140"], "department": "83"},
    "sanary-sur-mer": {"codes_postaux": ["83110"], "department": "83"},
}

# All postal codes to monitor
ALL_POSTAL_CODES = []
for city_data in CITIES.values():
    ALL_POSTAL_CODES.extend(city_data["codes_postaux"])

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
