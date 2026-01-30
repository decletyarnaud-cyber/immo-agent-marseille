"""
Scraper for vench.fr - Judicial real estate auctions
"""
import re
from datetime import datetime, date
from typing import List, Optional, Dict, Any
from bs4 import BeautifulSoup
from loguru import logger

from .base_scraper import BaseScraper
from src.storage.models import Auction, Lawyer, PropertyType, AuctionStatus, PVStatus


class VenchScraper(BaseScraper):
    """Scraper for vench.fr"""

    TRIBUNAUX = {
        "marseille": {
            "url": "liste-des-ventes-au-tribunal-judiciaire-marseille.html",
            "nom": "Tribunal Judiciaire de Marseille"
        },
        "aix-en-provence": {
            "url": "liste-des-ventes-au-tribunal-judiciaire-aix-en-provence.html",
            "nom": "Tribunal Judiciaire d'Aix-en-Provence"
        },
        "toulon": {
            "url": "liste-des-ventes-au-tribunal-judiciaire-toulon.html",
            "nom": "Tribunal Judiciaire de Toulon"
        }
    }

    def __init__(self):
        super().__init__(
            name="Vench",
            base_url="https://www.vench.fr"
        )

    def get_auction_list_url(self, page: int = 1) -> str:
        """Build URL for auction listing"""
        return f"{self.base_url}/liste-des-ventes-au-tribunal-judiciaire-marseille.html"

    def get_tribunal_list_url(self, tribunal_key: str) -> str:
        """Get URL for specific tribunal"""
        tribunal = self.TRIBUNAUX.get(tribunal_key, {})
        return f"{self.base_url}/{tribunal.get('url', '')}"

    def parse_auction_list(self, soup: BeautifulSoup) -> List[Dict[str, Any]]:
        """Parse auction listing page"""
        auctions = []
        seen_urls = set()

        # Method 1: Look for auction links directly (vente-XXXXX-... pattern with number)
        for link in soup.find_all("a", href=True):
            href = link.get("href", "")
            # Must match vente-NUMBER pattern (actual auctions)
            if re.search(r"vente-\d+", href) and href not in seen_urls:
                # Build full URL
                full_url = href if href.startswith("http") else f"{self.base_url}/{href.lstrip('./')}"
                seen_urls.add(href)

                text = link.get_text(strip=True)
                auctions.append({
                    "url": full_url,
                    "title": text
                })

        # Method 2: Try card/article structures if no links found
        if not auctions:
            cards = soup.select(".vente-item, .annonce, article, .listing-item, .vente-card")
            for card in cards:
                try:
                    auction_data = self._parse_card(card)
                    if auction_data and auction_data.get("url") not in seen_urls:
                        seen_urls.add(auction_data.get("url"))
                        auctions.append(auction_data)
                except Exception as e:
                    logger.warning(f"[Vench] Error parsing card: {e}")

        logger.debug(f"[Vench] Found {len(auctions)} auction links")
        return auctions

    def _parse_card(self, card) -> Optional[Dict[str, Any]]:
        """Parse individual auction card/row"""
        data = {}

        # Get URL
        link = card.find("a", href=True)
        if link:
            href = link.get("href", "")
            if not href.startswith("http"):
                href = f"{self.base_url}/{href.lstrip('/')}"
            data["url"] = href
            data["title"] = link.get_text(strip=True)

        # Get text content for parsing
        text = card.get_text(strip=True)

        # Extract date
        date_match = re.search(r"(\d{1,2}/\d{1,2}/\d{4})", text)
        if date_match:
            data["date_text"] = date_match.group(1)

        # Extract price
        price_match = re.search(r"([\d\s]+)\s*€", text)
        if price_match:
            data["price_text"] = price_match.group(1)

        # Extract location
        cp_match = re.search(r"\b(13\d{3}|83\d{3})\b", text)
        if cp_match:
            data["code_postal"] = cp_match.group(1)

        return data if data.get("url") else None

    def parse_auction_detail(self, url: str) -> Optional[Auction]:
        """Parse individual auction page"""
        soup = self.fetch_page(url)
        if not soup:
            return None

        auction = Auction()
        auction.source = "vench"
        auction.url = url

        # Extract ID from URL
        match = re.search(r"/(\d+)-", url)
        if match:
            auction.source_id = match.group(1)

        # Parse content
        self._parse_location_info(soup, auction)
        self._parse_property_info(soup, auction)
        self._parse_sale_info(soup, auction)
        self._parse_documents_links(soup, auction)
        self._parse_photos(soup, auction)
        self._parse_lawyer_info(soup, auction)

        return auction

    def _parse_location_info(self, soup: BeautifulSoup, auction: Auction):
        """Parse location information"""
        # Title often contains address
        title = soup.select_one("h1, .titre-vente, .page-title")
        if title:
            auction.description = title.get_text(strip=True)

        # Look for address in various places
        address_selectors = [".adresse", ".localisation", ".lieu", "[itemprop='address']"]

        for selector in address_selectors:
            elem = soup.select_one(selector)
            if elem:
                auction.adresse = elem.get_text(strip=True)
                break

        if not auction.adresse:
            auction.adresse = auction.description or ""

        # Extract postal code
        full_text = f"{auction.adresse} {auction.description}"
        cp_match = re.search(r"\b(13\d{3}|83\d{3})\b", full_text)
        if cp_match:
            auction.code_postal = cp_match.group(1)
            auction.department = auction.code_postal[:2]

        # Extract city - multiple patterns
        # Pattern 1: Known cities in the region (most reliable)
        known_cities = [
            "La Seyne-sur-Mer", "Aix-en-Provence", "Salon-de-Provence", "Fos-sur-Mer",
            "Six-Fours-les-Plages", "Sanary-sur-Mer", "Le Pradet", "La Garde", "La Ciotat",
            "Marseille", "Toulon", "Martigues", "Aubagne", "Cassis", "Miramas",
            "Istres", "Vitrolles", "Marignane", "Arles", "Hyères", "Fréjus",
            "Draguignan", "Bandol", "Ollioules", "Carqueiranne", "Le Lavandou", "Gonfaron"
        ]
        full_text_lower = full_text.lower()
        for city in known_cities:
            if city.lower() in full_text_lower:
                auction.ville = city
                break

        # Pattern 2: After postal code "13001 Marseille" (fallback)
        if not auction.ville:
            city_match = re.search(r"(?:13\d{3}|83\d{3})\s+([A-ZÀ-Ü][a-zà-ü\-]+(?:\s+[a-zà-ü\-]+)*)", full_text, re.IGNORECASE)
            if city_match:
                auction.ville = city_match.group(1).title()

    def _parse_property_info(self, soup: BeautifulSoup, auction: Auction):
        """Parse property details"""
        text = soup.get_text().lower()

        # Type
        type_mapping = {
            PropertyType.APPARTEMENT: ["appartement", "studio", "f1", "f2", "f3", "f4", "f5", "t1", "t2", "t3", "t4", "t5"],
            PropertyType.MAISON: ["maison", "villa", "pavillon", "propriété"],
            PropertyType.LOCAL_COMMERCIAL: ["local", "commerce", "bureau", "boutique"],
            PropertyType.TERRAIN: ["terrain", "parcelle"],
            PropertyType.PARKING: ["parking", "garage", "box", "stationnement"],
        }

        for prop_type, keywords in type_mapping.items():
            if any(kw in text for kw in keywords):
                auction.type_bien = prop_type
                break

        # Surface - multiple patterns
        surface_patterns = [
            r"surface[:\s]+(?:de\s+)?(\d+(?:[.,]\d+)?)\s*m[²2]",
            r"(\d+(?:[.,]\d+)?)\s*m[²2]\s*(?:environ|habitable|utile)?",
            r"(\d+(?:[.,]\d+)?)\s*m²",
        ]
        for pattern in surface_patterns:
            surface_match = re.search(pattern, text)
            if surface_match:
                auction.surface = float(surface_match.group(1).replace(",", "."))
                break

        # Rooms (pièces)
        pieces_match = re.search(r"(\d+)\s*(?:pièces?|pieces?|p\.)", text)
        if pieces_match:
            auction.nb_pieces = int(pieces_match.group(1))

        # Bedrooms (chambres)
        chambres_match = re.search(r"(\d+)\s*(?:chambres?|ch\.)", text)
        if chambres_match:
            auction.nb_chambres = int(chambres_match.group(1))

        # Floor (étage)
        etage_match = re.search(r"(\d+)(?:e|ème|er|eme)?\s*étage", text)
        if etage_match:
            auction.etage = int(etage_match.group(1))

    def _parse_sale_info(self, soup: BeautifulSoup, auction: Auction):
        """Parse sale date, time, price"""
        text = soup.get_text()

        # Date
        date_patterns = [
            r"(?:vente|adjudication|audience)\s+(?:le\s+)?(\d{1,2}/\d{1,2}/\d{4})",
            r"(\d{1,2}/\d{1,2}/\d{4})",
            r"(\d{1,2}\s+\w+\s+\d{4})"
        ]

        for pattern in date_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                date_str = match.group(1)
                parsed = self._parse_date(date_str)
                if parsed:
                    auction.date_vente = parsed
                    break

        # Time
        time_match = re.search(r"[àa]\s+(\d{1,2})[hH:](\d{0,2})", text)
        if time_match:
            h = time_match.group(1)
            m = time_match.group(2) or "00"
            auction.heure_vente = f"{h}h{m}"

        # Price
        price_patterns = [
            r"mise\s+[àa]\s+prix\s*:?\s*([\d\s,.]+)\s*€?",
            r"prix\s*:?\s*([\d\s,.]+)\s*€",
            r"([\d\s,.]+)\s*€"
        ]

        for pattern in price_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                price = self._extract_price(match.group(1))
                if price:
                    auction.mise_a_prix = price
                    break

        # Tribunal
        for key, tribunal_info in self.TRIBUNAUX.items():
            if key in text.lower() or tribunal_info["nom"].lower() in text.lower():
                auction.tribunal = tribunal_info["nom"]
                break

        # Visit dates
        visit_match = re.search(r"visite[s]?\s*:?\s*(.+?)(?:\n|$)", text, re.IGNORECASE)
        if visit_match:
            visit_text = visit_match.group(1)
            dates = re.findall(r"(\d{1,2}/\d{1,2}/\d{4})", visit_text)
            for d in dates:
                parsed = self._parse_date(d)
                if parsed:
                    auction.dates_visite.append(datetime.combine(parsed, datetime.min.time()))

    def _parse_date(self, date_str: str) -> Optional[date]:
        """Parse date string"""
        months = {
            "janvier": 1, "février": 2, "mars": 3, "avril": 4,
            "mai": 5, "juin": 6, "juillet": 7, "août": 8,
            "septembre": 9, "octobre": 10, "novembre": 11, "décembre": 12
        }

        # DD/MM/YYYY
        match = re.match(r"(\d{1,2})/(\d{1,2})/(\d{4})", date_str)
        if match:
            try:
                return date(int(match.group(3)), int(match.group(2)), int(match.group(1)))
            except ValueError:
                pass

        # "15 janvier 2024"
        match = re.match(r"(\d{1,2})\s+(\w+)\s+(\d{4})", date_str)
        if match:
            day = int(match.group(1))
            month = months.get(match.group(2).lower())
            year = int(match.group(3))
            if month:
                try:
                    return date(year, month, day)
                except ValueError:
                    pass

        return None

    def _extract_price(self, text: str) -> Optional[float]:
        """Extract price value"""
        cleaned = re.sub(r"[^\d,.]", "", text.replace(" ", ""))
        cleaned = cleaned.replace(",", ".")

        if cleaned.count(".") > 1:
            parts = cleaned.rsplit(".", 1)
            cleaned = parts[0].replace(".", "") + ("." + parts[1] if len(parts) > 1 else "")

        try:
            return float(cleaned)
        except ValueError:
            return None

    def _parse_documents_links(self, soup: BeautifulSoup, auction: Auction):
        """Parse document links"""
        doc_keywords = ["cahier", "charge", "pv", "pdf", "document", "télécharger"]

        for link in soup.find_all("a", href=True):
            href = link.get("href", "").lower()
            text = link.get_text().lower()

            if any(kw in href or kw in text for kw in doc_keywords):
                if ".pdf" in href:
                    full_url = href if href.startswith("http") else f"{self.base_url}/{href.lstrip('/')}"
                    auction.pv_url = full_url
                    auction.pv_status = PVStatus.A_TELECHARGER
                    break

        if not auction.pv_url:
            auction.pv_status = PVStatus.A_DEMANDER

    def _parse_photos(self, soup: BeautifulSoup, auction: Auction):
        """Parse photo URLs from the page"""
        photos = []

        # Look for images in various containers
        img_selectors = [
            ".photo img", ".photos img", ".gallery img", ".slider img",
            ".carousel img", ".swiper-slide img", ".vente-photo img",
            ".annonce-photo img", "img.photo", "img.vente-img",
            ".fiche-lot img", ".detail-photo img"
        ]

        for selector in img_selectors:
            for img in soup.select(selector):
                src = img.get("src") or img.get("data-src") or img.get("data-lazy")
                if src and self._is_valid_photo(src):
                    full_url = src if src.startswith("http") else f"{self.base_url}/{src.lstrip('/')}"
                    if full_url not in photos:
                        photos.append(full_url)

        # Fallback: look for any large images
        if not photos:
            for img in soup.find_all("img"):
                src = img.get("src", "")
                # Exclude small icons, logos, etc.
                if src and self._is_valid_photo(src):
                    width = img.get("width", "")
                    height = img.get("height", "")
                    # Parse dimensions (handle "100%", "auto", etc.)
                    try:
                        w = int(width) if width and width.isdigit() else 200
                        h = int(height) if height and height.isdigit() else 200
                    except (ValueError, TypeError):
                        w, h = 200, 200
                    # Only include if dimensions suggest it's a property photo
                    if w > 100 and h > 100:
                        full_url = src if src.startswith("http") else f"{self.base_url}/{src.lstrip('/')}"
                        if full_url not in photos:
                            photos.append(full_url)

        auction.photos = photos[:10]  # Limit to 10 photos

    def _is_valid_photo(self, src: str) -> bool:
        """Check if image URL is likely a property photo"""
        src_lower = src.lower()
        # Exclude common non-property images
        exclude_patterns = [
            "logo", "icon", "avatar", "banner", "button", "social",
            "facebook", "twitter", "linkedin", "youtube", "sprite",
            "placeholder", "loading", "default", "no-image"
        ]
        if any(pat in src_lower for pat in exclude_patterns):
            return False
        # Must be an image file
        if not any(ext in src_lower for ext in [".jpg", ".jpeg", ".png", ".webp", ".gif"]):
            return False
        return True

    def _parse_lawyer_info(self, soup: BeautifulSoup, auction: Auction):
        """Parse lawyer information and store directly on auction"""
        text = soup.get_text()

        # Try to find Maitre name
        me_match = re.search(r"(?:Maître|Me|Maitre)\s+([A-ZÀ-Ü][a-zà-ü]+(?:\s+[A-ZÀ-Ü][a-zà-ü]+)*)", text)
        if me_match:
            auction.avocat_nom = f"Me {me_match.group(1)}"

        # Phone
        phone_match = re.search(r"(?:Tél|Tel|Téléphone)\s*:?\s*([\d\s.]+)", text)
        if phone_match:
            auction.avocat_telephone = phone_match.group(1).strip()

        # Email
        email_match = re.search(r"([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})", text)
        if email_match:
            auction.avocat_email = email_match.group(1)

        # Try structured section
        lawyer_section = soup.select_one(".avocat, .contact, .vendeur, .poursuivant")
        if lawyer_section:
            if not auction.avocat_nom:
                name_elem = lawyer_section.select_one(".nom, strong, h4, b")
                if name_elem:
                    auction.avocat_nom = name_elem.get_text(strip=True)

            site = lawyer_section.select_one("a[href*='avocat']")
            if site:
                auction.avocat_site_web = site.get("href", "")

    def extract_lawyer_info(self, soup: BeautifulSoup) -> Optional[Lawyer]:
        """Extract lawyer information"""
        lawyer = Lawyer()

        text = soup.get_text()

        # Try to find Maître name
        me_match = re.search(r"(?:Maître|Me)\s+([A-ZÀ-Ü][a-zà-ü]+(?:\s+[A-ZÀ-Ü][a-zà-ü]+)*)", text)
        if me_match:
            lawyer.nom = f"Me {me_match.group(1)}"

        # Phone
        phone_match = re.search(r"(?:Tél|Tel|Téléphone)\s*:?\s*([\d\s.]+)", text)
        if phone_match:
            lawyer.telephone = phone_match.group(1).strip()

        # Email
        email_match = re.search(r"([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})", text)
        if email_match:
            lawyer.email = email_match.group(1)

        # Try structured section
        lawyer_section = soup.select_one(".avocat, .contact, .vendeur")
        if lawyer_section:
            if not lawyer.nom:
                name_elem = lawyer_section.select_one(".nom, strong, h4")
                if name_elem:
                    lawyer.nom = name_elem.get_text(strip=True)

            site = lawyer_section.select_one("a[href*='avocat']")
            if site:
                lawyer.site_web = site.get("href", "")

        return lawyer if lawyer.nom else None

    def scrape_all_tribunaux(self) -> List[Auction]:
        """Scrape auctions from all tribunaux"""
        all_auctions = []

        for key, tribunal_info in self.TRIBUNAUX.items():
            logger.info(f"[Vench] Scraping {tribunal_info['nom']}...")
            url = self.get_tribunal_list_url(key)
            soup = self.fetch_page(url)

            if soup:
                auction_data = self.parse_auction_list(soup)
                for data in auction_data:
                    if "url" in data:
                        auction = self.parse_auction_detail(data["url"])
                        if auction:
                            if not auction.tribunal:
                                auction.tribunal = tribunal_info["nom"]
                            # Geocode the auction to get GPS coordinates
                            auction = self.geocode_auction(auction)
                            all_auctions.append(auction)

        logger.info(f"[Vench] Total: {len(all_auctions)} auctions scraped")
        return all_auctions
