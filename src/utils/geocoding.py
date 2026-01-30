"""
Geocoding utilities for Immo-Agent
Provides address geocoding and distance calculation functions
"""
import math
import requests
from typing import Optional, Tuple
from loguru import logger


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate the distance in kilometers between two GPS coordinates
    using the Haversine formula.

    Args:
        lat1, lon1: Coordinates of point 1
        lat2, lon2: Coordinates of point 2

    Returns:
        Distance in kilometers
    """
    R = 6371  # Earth's radius in km

    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)

    a = (math.sin(dlat / 2) ** 2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
         math.sin(dlon / 2) ** 2)
    c = 2 * math.asin(math.sqrt(a))

    return R * c


def geocode_address(address: str, city: str, postal_code: str) -> Tuple[Optional[float], Optional[float]]:
    """
    Geocode an address using French government API (most precise) with Nominatim fallback.

    Args:
        address: Street address
        city: City name
        postal_code: Postal code

    Returns:
        Tuple of (latitude, longitude) or (None, None) if geocoding fails
    """
    # Clean and normalize address
    address_clean = (address or "").strip()
    city_clean = (city or "").strip()
    postal_code_clean = (postal_code or "").strip()

    # Strategy 1: French Government API (api-adresse.data.gouv.fr) - most precise for France
    if address_clean or city_clean:
        try:
            # Build query with address components
            query_parts = []
            if address_clean:
                query_parts.append(address_clean)
            if city_clean:
                query_parts.append(city_clean)

            query = " ".join(query_parts)

            params = {
                "q": query,
                "limit": 1,
            }
            # Add postcode filter for more precision
            if postal_code_clean and postal_code_clean.isdigit():
                params["postcode"] = postal_code_clean

            response = requests.get(
                "https://api-adresse.data.gouv.fr/search/",
                params=params,
                headers={"User-Agent": "ImmoAgent/1.0"},
                timeout=5
            )

            if response.status_code == 200:
                data = response.json()
                if data.get("features") and len(data["features"]) > 0:
                    coords = data["features"][0]["geometry"]["coordinates"]
                    # GeoJSON format: [lon, lat]
                    return float(coords[1]), float(coords[0])
        except Exception as e:
            logger.debug(f"Geocoding strategy 1 failed: {e}")

    # Strategy 2: Try with just postcode and city for broader match
    if postal_code_clean and city_clean:
        try:
            response = requests.get(
                "https://api-adresse.data.gouv.fr/search/",
                params={
                    "q": city_clean,
                    "postcode": postal_code_clean,
                    "type": "municipality",
                    "limit": 1,
                },
                headers={"User-Agent": "ImmoAgent/1.0"},
                timeout=5
            )
            if response.status_code == 200:
                data = response.json()
                if data.get("features") and len(data["features"]) > 0:
                    coords = data["features"][0]["geometry"]["coordinates"]
                    return float(coords[1]), float(coords[0])
        except Exception as e:
            logger.debug(f"Geocoding strategy 2 failed: {e}")

    # Strategy 3: Nominatim fallback
    full_query = f"{address_clean}, {postal_code_clean} {city_clean}, France" if address_clean else f"{postal_code_clean} {city_clean}, France"
    try:
        response = requests.get(
            "https://nominatim.openstreetmap.org/search",
            params={
                "q": full_query,
                "format": "json",
                "limit": 1,
                "countrycodes": "fr"
            },
            headers={"User-Agent": "ImmoAgent/1.0"},
            timeout=5
        )
        if response.status_code == 200 and response.json():
            data = response.json()[0]
            return float(data["lat"]), float(data["lon"])
    except Exception as e:
        logger.debug(f"Geocoding strategy 3 (Nominatim) failed: {e}")

    # Strategy 4: Nominatim structured search
    if city_clean:
        try:
            response = requests.get(
                "https://nominatim.openstreetmap.org/search",
                params={
                    "city": city_clean,
                    "postalcode": postal_code_clean,
                    "country": "France",
                    "format": "json",
                    "limit": 1,
                },
                headers={"User-Agent": "ImmoAgent/1.0"},
                timeout=5
            )
            if response.status_code == 200 and response.json():
                data = response.json()[0]
                return float(data["lat"]), float(data["lon"])
        except Exception as e:
            logger.debug(f"Geocoding strategy 4 (Nominatim structured) failed: {e}")

    # Fallback coordinates for major cities in our region
    city_coords = {
        "marseille": (43.2965, 5.3698),
        "aix-en-provence": (43.5297, 5.4474),
        "toulon": (43.1242, 5.9280),
        "aubagne": (43.2927, 5.5708),
        "hyeres": (43.1204, 6.1286),
        "la ciotat": (43.1748, 5.6047),
        "martigues": (43.4053, 5.0476),
        "frejus": (43.4330, 6.7370),
        "draguignan": (43.5366, 6.4647),
        "la seyne-sur-mer": (43.0833, 5.8833),
        "salon-de-provence": (43.6400, 5.0970),
        "istres": (43.5150, 4.9870),
        "vitrolles": (43.4550, 5.2480),
        "arles": (43.6770, 4.6300),
        "tarascon": (43.8060, 4.6600),
        "gardanne": (43.4540, 5.4690),
        "miramas": (43.5850, 5.0010),
        "saint-raphael": (43.4250, 6.7680),
        "six-fours-les-plages": (43.0930, 5.8200),
        "bandol": (43.1350, 5.7520),
        "sanary-sur-mer": (43.1190, 5.8010),
        "ollioules": (43.1410, 5.8520),
        "fos-sur-mer": (43.4376, 4.9444),
        "cassis": (43.2142, 5.5392),
        "la garde": (43.1247, 6.0108),
        "le pradet": (43.1067, 6.0233),
        "carqueiranne": (43.0958, 6.0742),
        "brignoles": (43.4053, 6.0614),
        "cuers": (43.2378, 6.0728),
        "sollies-pont": (43.1903, 6.0417),
        "le beausset": (43.1978, 5.8017),
        "saint-cyr-sur-mer": (43.1817, 5.7081),
        "le castellet": (43.2017, 5.7783),
    }

    city_lower = city_clean.lower() if city_clean else ""
    for city_name, coords in city_coords.items():
        if city_name in city_lower or city_lower in city_name:
            logger.debug(f"Using fallback coordinates for {city_name}")
            return coords

    return None, None
