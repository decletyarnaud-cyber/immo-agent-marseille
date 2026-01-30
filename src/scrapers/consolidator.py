"""
AuctionConsolidator - Consolidation des enchères multi-source

Ce module permet de:
1. Matcher les enchères de différentes sources par (date_vente, tribunal)
2. Détecter les conflits quand les valeurs diffèrent
3. Fusionner les données (photos, documents) sans conflits
4. Marquer les champs en conflit pour arbitrage utilisateur
"""
import hashlib
from datetime import datetime, date
from typing import List, Dict, Optional, Set, Any
from loguru import logger

from src.storage.models import (
    Auction, ConsolidatedAuction, FieldConflict, UserChoice,
    SourceData, PropertyType, FieldConfidence
)


# Champs à surveiller pour les conflits
CONSOLIDATION_FIELDS = [
    "adresse",
    "code_postal",
    "ville",
    "surface",
    "nb_pieces",
    "nb_chambres",
    "etage",
    "type_bien",
    "mise_a_prix",
    "occupation",
    "cadastre",
    "avocat_nom",
    "avocat_telephone",
    "avocat_email",
]


class AuctionConsolidator:
    """Consolide les enchères provenant de plusieurs sources"""

    def __init__(self):
        self.source_priority = ["encheres_publiques", "vench", "licitor"]

    def generate_matching_key(self, date_vente: Optional[date], tribunal: str) -> str:
        """Génère une clé unique pour matcher les enchères"""
        if not date_vente or not tribunal:
            return ""

        key_str = f"{date_vente.isoformat()}|{tribunal.lower().strip()}"
        return hashlib.md5(key_str.encode()).hexdigest()[:16]

    def consolidate(self, auctions_by_source: Dict[str, List[Auction]]) -> List[ConsolidatedAuction]:
        """
        Consolide les enchères de plusieurs sources.

        Args:
            auctions_by_source: Dict avec source comme clé et liste d'Auction comme valeur
                               Ex: {"licitor": [...], "encheres_publiques": [...], "vench": [...]}

        Returns:
            Liste de ConsolidatedAuction avec conflits détectés
        """
        # 1. Grouper par clé (date_vente, tribunal)
        groups = self._group_by_key(auctions_by_source)
        logger.info(f"[Consolidator] {len(groups)} groupes uniques trouvés")

        # 2. Pour chaque groupe, merger les données
        consolidated = []
        for key, auctions in groups.items():
            if not auctions:
                continue

            merged = self._merge_group(key, auctions)
            consolidated.append(merged)

        logger.info(f"[Consolidator] {len(consolidated)} enchères consolidées")
        return consolidated

    def _group_by_key(self, auctions_by_source: Dict[str, List[Auction]]) -> Dict[str, List[Auction]]:
        """Groupe les enchères par clé (date_vente, tribunal)"""
        groups: Dict[str, List[Auction]] = {}

        for source, auctions in auctions_by_source.items():
            for auction in auctions:
                key = self.generate_matching_key(auction.date_vente, auction.tribunal)
                if not key:
                    # Pas de date ou tribunal -> clé alternative basée sur adresse
                    key = self._fallback_key(auction)

                if key:
                    if key not in groups:
                        groups[key] = []
                    groups[key].append(auction)

        return groups

    def _fallback_key(self, auction: Auction) -> str:
        """Clé de fallback basée sur l'adresse normalisée"""
        if not auction.adresse or not auction.code_postal:
            return ""

        # Normaliser l'adresse
        addr = auction.adresse.lower().strip()
        addr = addr.replace(",", " ").replace(".", " ")
        addr = " ".join(addr.split())  # Normaliser espaces

        key_str = f"{addr}|{auction.code_postal}"
        return hashlib.md5(key_str.encode()).hexdigest()[:16]

    def _merge_group(self, matching_key: str, auctions: List[Auction]) -> ConsolidatedAuction:
        """Fusionne un groupe d'enchères provenant de différentes sources"""
        result = ConsolidatedAuction()
        result.matching_key = matching_key

        # Collecter les sources et URLs
        for auction in auctions:
            if auction.source and auction.source not in result.sources:
                result.sources.append(auction.source)
            if auction.source and auction.url:
                result.source_urls[auction.source] = auction.url
            if auction.source and auction.id:
                result.auction_ids[auction.source] = auction.id

            # Stocker les données brutes de chaque source
            result.source_data[auction.source] = SourceData(
                source=auction.source,
                url=auction.url,
                raw_data=auction.to_dict()
            )

        # Pour chaque champ, collecter les valeurs et détecter les conflits
        for field_name in CONSOLIDATION_FIELDS:
            values_by_source = {}
            for auction in auctions:
                val = getattr(auction, field_name, None)
                if val is not None and val != "" and val != PropertyType.AUTRE:
                    # Normaliser pour comparaison
                    if isinstance(val, PropertyType):
                        val = val.value
                    values_by_source[auction.source] = val

            self._process_field(result, field_name, values_by_source)

        # Champs qui ne causent pas de conflit (on prend le premier non-nul)
        self._merge_non_conflict_fields(result, auctions)

        # Fusionner photos et documents (toutes les sources)
        result.photos = self._merge_photos(auctions)
        result.documents = self._merge_documents(auctions)

        # Calculer le score de confiance
        result.confidence_score = self._calculate_confidence(result, auctions)

        return result

    def _process_field(self, result: ConsolidatedAuction, field_name: str, values_by_source: Dict[str, Any]):
        """Traite un champ: consensus, conflit, ou valeur unique"""
        unique_values = set()
        for val in values_by_source.values():
            if val is not None:
                # Normaliser pour comparaison (lowercase pour strings)
                normalized = str(val).lower().strip() if isinstance(val, str) else val
                unique_values.add(normalized)

        if len(unique_values) == 0:
            # Aucune donnée
            return

        elif len(unique_values) == 1:
            # CONSENSUS : toutes les sources d'accord
            first_value = list(values_by_source.values())[0]
            self._set_field_value(result, field_name, first_value)

        else:
            # CONFLIT : valeurs différentes
            logger.debug(f"[Consolidator] Conflit détecté sur '{field_name}': {values_by_source}")

            result.conflicts[field_name] = FieldConflict(
                field_name=field_name,
                values_by_source=values_by_source,
            )
            result.pending_validation.append(field_name)

            # Utiliser une valeur par défaut (première source par priorité)
            for source in self.source_priority:
                if source in values_by_source:
                    self._set_field_value(result, field_name, values_by_source[source])
                    break

    def _set_field_value(self, result: ConsolidatedAuction, field_name: str, value: Any):
        """Définit la valeur d'un champ sur le résultat consolidé"""
        if field_name == "type_bien":
            if isinstance(value, str):
                try:
                    value = PropertyType(value)
                except ValueError:
                    value = PropertyType.AUTRE
        setattr(result, field_name, value)

    def _merge_non_conflict_fields(self, result: ConsolidatedAuction, auctions: List[Auction]):
        """Fusionne les champs qui ne causent pas de conflit"""
        # Date et heure de vente (consensus attendu)
        for auction in auctions:
            if not result.date_vente and auction.date_vente:
                result.date_vente = auction.date_vente
            if not result.heure_vente and auction.heure_vente:
                result.heure_vente = auction.heure_vente
            if not result.tribunal and auction.tribunal:
                result.tribunal = auction.tribunal
            if not result.department and auction.department:
                result.department = auction.department
            if result.latitude is None and auction.latitude:
                result.latitude = auction.latitude
            if result.longitude is None and auction.longitude:
                result.longitude = auction.longitude
            if not result.description and auction.description:
                result.description = auction.description
            if not result.description_detaillee and auction.description_detaillee:
                result.description_detaillee = auction.description_detaillee

    def _merge_photos(self, auctions: List[Auction]) -> List[str]:
        """Fusionne les photos de toutes les sources (dédupliquées)"""
        seen_urls: Set[str] = set()
        photos: List[str] = []

        # Priorité aux sources avec plus de photos (encheres_publiques souvent)
        sorted_auctions = sorted(auctions, key=lambda a: len(a.photos or []), reverse=True)

        for auction in sorted_auctions:
            for photo in (auction.photos or []):
                # Normaliser l'URL pour déduplication
                normalized = photo.lower().split("?")[0]
                if normalized not in seen_urls:
                    seen_urls.add(normalized)
                    photos.append(photo)

        # Limiter à 30 photos max
        return photos[:30]

    def _merge_documents(self, auctions: List[Auction]) -> List[Dict]:
        """Fusionne les documents de toutes les sources"""
        seen_urls: Set[str] = set()
        documents: List[Dict] = []

        for auction in auctions:
            for doc in (auction.documents or []):
                url = doc.get("url", "")
                if url and url not in seen_urls:
                    seen_urls.add(url)
                    # Ajouter la source
                    doc_with_source = {**doc, "source": auction.source}
                    documents.append(doc_with_source)

        return documents

    def _calculate_confidence(self, result: ConsolidatedAuction, auctions: List[Auction]) -> float:
        """Calcule un score de confiance (0-100) basé sur l'accord entre sources"""
        total_fields = len(CONSOLIDATION_FIELDS)
        conflict_count = len(result.conflicts)
        source_count = len(result.sources)

        # Base: % de champs sans conflit
        agreement_score = ((total_fields - conflict_count) / total_fields) * 100

        # Bonus pour multi-source
        if source_count >= 3:
            agreement_score = min(100, agreement_score + 10)
        elif source_count == 2:
            agreement_score = min(100, agreement_score + 5)

        # Malus pour conflits non résolus
        unresolved = len([c for c in result.conflicts.values() if not c.resolved])
        agreement_score -= unresolved * 5

        return max(0, min(100, agreement_score))

    def resolve_conflict(
        self,
        consolidated: ConsolidatedAuction,
        field_name: str,
        chosen_value: Any,
        chosen_source: str,
        reason: str = None
    ) -> ConsolidatedAuction:
        """Résout un conflit avec le choix de l'utilisateur"""
        consolidated.resolve_conflict(field_name, chosen_value, chosen_source, reason)

        # Recalculer le score de confiance
        total_fields = len(CONSOLIDATION_FIELDS)
        conflict_count = len(consolidated.conflicts)
        unresolved = len([c for c in consolidated.conflicts.values() if not c.resolved])

        base_score = ((total_fields - conflict_count) / total_fields) * 100
        consolidated.confidence_score = max(0, min(100, base_score - unresolved * 5))

        consolidated.last_consolidated = datetime.now()
        return consolidated

    def get_field_comparison(self, consolidated: ConsolidatedAuction, field_name: str) -> Dict[str, Any]:
        """
        Retourne les valeurs d'un champ pour chaque source (pour l'UI de comparaison)
        """
        comparison = {}
        for source, source_data in consolidated.source_data.items():
            raw_data = source_data.raw_data
            comparison[source] = raw_data.get(field_name)
        return comparison
