"""
Data models for Immo-Agent
"""
from dataclasses import dataclass, field
from datetime import datetime, date
from typing import Optional, List, Dict, Any
from enum import Enum


class PropertyType(Enum):
    APPARTEMENT = "appartement"
    MAISON = "maison"
    LOCAL_COMMERCIAL = "local_commercial"
    TERRAIN = "terrain"
    PARKING = "parking"
    AUTRE = "autre"


class AuctionStatus(Enum):
    A_VENIR = "a_venir"
    EN_COURS = "en_cours"
    ADJUGE = "adjuge"
    ANNULE = "annule"


class PVStatus(Enum):
    DISPONIBLE = "disponible"
    A_TELECHARGER = "a_telecharger"
    A_DEMANDER = "a_demander"
    NON_DISPONIBLE = "non_disponible"


@dataclass
class Lawyer:
    """Cabinet d'avocat"""
    id: Optional[int] = None
    nom: str = ""
    cabinet: str = ""
    adresse: str = ""
    telephone: str = ""
    email: str = ""
    site_web: str = ""
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)


@dataclass
class Auction:
    """Vente aux enchères judiciaires"""
    id: Optional[int] = None

    # Identification
    source: str = ""  # licitor, encheres_publiques, vench
    source_id: str = ""  # ID unique sur la source
    url: str = ""

    # Localisation
    adresse: str = ""
    code_postal: str = ""
    ville: str = ""
    department: str = ""
    latitude: Optional[float] = None
    longitude: Optional[float] = None

    # Description du bien
    type_bien: PropertyType = PropertyType.AUTRE
    surface: Optional[float] = None  # m²
    nb_pieces: Optional[int] = None
    nb_chambres: Optional[int] = None
    etage: Optional[int] = None
    description: str = ""
    description_detaillee: str = ""  # Description enrichie (composition par étage, etc.)
    occupation: str = ""  # "Libre", "Occupé", etc.
    cadastre: str = ""  # Référence cadastrale

    # Photos et documents
    photos: List[str] = field(default_factory=list)  # URLs des photos
    documents: List[dict] = field(default_factory=list)  # [{nom, url, type}, ...]

    # Dates importantes
    date_vente: Optional[date] = None
    heure_vente: Optional[str] = None
    dates_visite: List[datetime] = field(default_factory=list)
    date_jugement: Optional[date] = None

    # Prix
    mise_a_prix: Optional[float] = None
    prix_adjudication: Optional[float] = None  # Si déjà vendu

    # Tribunal et avocat
    tribunal: str = ""
    lawyer_id: Optional[int] = None
    avocat_nom: Optional[str] = None
    avocat_cabinet: Optional[str] = None
    avocat_adresse: Optional[str] = None
    avocat_telephone: Optional[str] = None
    avocat_email: Optional[str] = None
    avocat_site_web: Optional[str] = None

    # Procès-verbal
    pv_status: PVStatus = PVStatus.NON_DISPONIBLE
    pv_url: Optional[str] = None
    pv_local_path: Optional[str] = None

    # Analyse
    prix_marche_estime: Optional[float] = None
    prix_m2_marche: Optional[float] = None
    decote_pourcentage: Optional[float] = None
    score_opportunite: Optional[float] = None

    # Métadonnées
    status: AuctionStatus = AuctionStatus.A_VENIR
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict:
        """Convert to dictionary for storage"""
        return {
            "id": self.id,
            "source": self.source,
            "source_id": self.source_id,
            "url": self.url,
            "adresse": self.adresse,
            "code_postal": self.code_postal,
            "ville": self.ville,
            "department": self.department,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "type_bien": self.type_bien.value,
            "surface": self.surface,
            "nb_pieces": self.nb_pieces,
            "nb_chambres": self.nb_chambres,
            "etage": self.etage,
            "description": self.description,
            "description_detaillee": self.description_detaillee,
            "occupation": self.occupation,
            "cadastre": self.cadastre,
            "photos": self.photos,
            "documents": self.documents,
            "date_vente": self.date_vente.isoformat() if self.date_vente else None,
            "heure_vente": self.heure_vente,
            "dates_visite": [d.isoformat() for d in self.dates_visite],
            "date_jugement": self.date_jugement.isoformat() if self.date_jugement else None,
            "mise_a_prix": self.mise_a_prix,
            "prix_adjudication": self.prix_adjudication,
            "tribunal": self.tribunal,
            "lawyer_id": self.lawyer_id,
            "avocat_nom": self.avocat_nom,
            "avocat_cabinet": self.avocat_cabinet,
            "avocat_adresse": self.avocat_adresse,
            "avocat_telephone": self.avocat_telephone,
            "avocat_email": self.avocat_email,
            "avocat_site_web": self.avocat_site_web,
            "pv_status": self.pv_status.value,
            "pv_url": self.pv_url,
            "pv_local_path": self.pv_local_path,
            "prix_marche_estime": self.prix_marche_estime,
            "prix_m2_marche": self.prix_m2_marche,
            "decote_pourcentage": self.decote_pourcentage,
            "score_opportunite": self.score_opportunite,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


@dataclass
class DVFTransaction:
    """Transaction immobilière DVF"""
    id: Optional[int] = None
    date_mutation: date = None
    nature_mutation: str = ""  # Vente, etc.
    valeur_fonciere: float = 0.0
    adresse: str = ""
    code_postal: str = ""
    commune: str = ""
    type_local: str = ""
    surface_reelle: Optional[float] = None
    nombre_pieces: Optional[int] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    prix_m2: Optional[float] = None


@dataclass
class AnalysisReport:
    """Rapport d'analyse d'une enchère"""
    auction_id: int
    date_analyse: datetime = field(default_factory=datetime.now)

    # Comparaison marché
    transactions_comparables: List[DVFTransaction] = field(default_factory=list)
    prix_m2_moyen_secteur: Optional[float] = None
    prix_estime: Optional[float] = None

    # Score
    decote: Optional[float] = None  # en %
    score: Optional[float] = None  # 0-100
    recommandation: str = ""  # "Bonne affaire", "Opportunité", "Prix marché", "Surévalué"

    # Détails
    points_forts: List[str] = field(default_factory=list)
    points_vigilance: List[str] = field(default_factory=list)


# ===== CONSOLIDATION MODELS =====

class FieldConfidence(Enum):
    """Niveau de confiance pour un champ"""
    HIGH = "high"        # Consensus entre sources
    MEDIUM = "medium"    # Une seule source
    CONFLICT = "conflict"  # Valeurs contradictoires
    NONE = "none"        # Aucune donnée


@dataclass
class FieldConflict:
    """Représente un conflit sur un champ entre sources"""
    field_name: str
    values_by_source: Dict[str, any] = field(default_factory=dict)  # {"licitor": "val1", "vench": "val2"}
    detected_at: datetime = field(default_factory=datetime.now)
    resolved: bool = False
    chosen_value: Optional[any] = None
    chosen_source: Optional[str] = None  # Source choisie ou "manual" si saisie manuelle

    def to_dict(self) -> dict:
        return {
            "field_name": self.field_name,
            "values_by_source": self.values_by_source,
            "detected_at": self.detected_at.isoformat(),
            "resolved": self.resolved,
            "chosen_value": self.chosen_value,
            "chosen_source": self.chosen_source,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "FieldConflict":
        return cls(
            field_name=data["field_name"],
            values_by_source=data.get("values_by_source", {}),
            detected_at=datetime.fromisoformat(data["detected_at"]) if data.get("detected_at") else datetime.now(),
            resolved=data.get("resolved", False),
            chosen_value=data.get("chosen_value"),
            chosen_source=data.get("chosen_source"),
        )


@dataclass
class UserChoice:
    """Choix fait par l'utilisateur pour résoudre un conflit"""
    field_name: str
    chosen_value: any
    chosen_source: str  # ou "manual" si saisi manuellement
    chosen_at: datetime = field(default_factory=datetime.now)
    reason: Optional[str] = None  # Note optionnelle de l'utilisateur

    def to_dict(self) -> dict:
        return {
            "field_name": self.field_name,
            "chosen_value": self.chosen_value,
            "chosen_source": self.chosen_source,
            "chosen_at": self.chosen_at.isoformat(),
            "reason": self.reason,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "UserChoice":
        return cls(
            field_name=data["field_name"],
            chosen_value=data["chosen_value"],
            chosen_source=data["chosen_source"],
            chosen_at=datetime.fromisoformat(data["chosen_at"]) if data.get("chosen_at") else datetime.now(),
            reason=data.get("reason"),
        )


@dataclass
class SourceData:
    """Données brutes d'une source pour une enchère"""
    source: str  # "licitor", "encheres_publiques", "vench"
    url: str
    scraped_at: datetime = field(default_factory=datetime.now)
    raw_data: Dict[str, any] = field(default_factory=dict)  # Toutes les données brutes

    def to_dict(self) -> dict:
        return {
            "source": self.source,
            "url": self.url,
            "scraped_at": self.scraped_at.isoformat(),
            "raw_data": self.raw_data,
        }


@dataclass
class ConsolidatedAuction:
    """Enchère consolidée à partir de plusieurs sources"""
    id: Optional[int] = None

    # === IDENTIFIANT UNIQUE ===
    matching_key: str = ""  # hash(date_vente + tribunal) pour le matching

    # === SOURCES ===
    sources: List[str] = field(default_factory=list)  # ["licitor", "encheres_publiques", "vench"]
    source_urls: Dict[str, str] = field(default_factory=dict)  # {"licitor": "url1", "ep": "url2"}
    source_data: Dict[str, SourceData] = field(default_factory=dict)  # Données brutes par source

    # === CONFLITS ET ARBITRAGE ===
    conflicts: Dict[str, FieldConflict] = field(default_factory=dict)
    user_choices: Dict[str, UserChoice] = field(default_factory=dict)
    pending_validation: List[str] = field(default_factory=list)

    # === DONNÉES CONSOLIDÉES ===
    # Localisation
    adresse: str = ""
    code_postal: str = ""
    ville: str = ""
    department: str = ""
    latitude: Optional[float] = None
    longitude: Optional[float] = None

    # Bien
    type_bien: PropertyType = PropertyType.AUTRE
    surface: Optional[float] = None
    nb_pieces: Optional[int] = None
    nb_chambres: Optional[int] = None
    etage: Optional[int] = None
    description: str = ""
    description_detaillee: str = ""
    occupation: str = ""
    cadastre: str = ""

    # Enchère
    date_vente: Optional[date] = None
    heure_vente: Optional[str] = None
    tribunal: str = ""
    mise_a_prix: Optional[float] = None

    # Juridique
    avocat_nom: Optional[str] = None
    avocat_telephone: Optional[str] = None
    avocat_email: Optional[str] = None

    # Médias (fusionnés de toutes les sources)
    photos: List[str] = field(default_factory=list)
    documents: List[Dict] = field(default_factory=list)

    # Métadonnées
    confidence_score: float = 0.0  # 0-100, basé sur accord sources
    last_consolidated: datetime = field(default_factory=datetime.now)

    # Référence vers les IDs des auctions sources
    auction_ids: Dict[str, int] = field(default_factory=dict)  # {"licitor": 45, "vench": 78}

    def has_conflicts(self) -> bool:
        """Vérifie s'il y a des conflits non résolus"""
        return any(not c.resolved for c in self.conflicts.values())

    def get_unresolved_conflicts(self) -> List[FieldConflict]:
        """Retourne les conflits non résolus"""
        return [c for c in self.conflicts.values() if not c.resolved]

    def resolve_conflict(self, field_name: str, chosen_value: any, chosen_source: str, reason: str = None):
        """Résout un conflit avec le choix de l'utilisateur"""
        if field_name in self.conflicts:
            self.conflicts[field_name].resolved = True
            self.conflicts[field_name].chosen_value = chosen_value
            self.conflicts[field_name].chosen_source = chosen_source

            self.user_choices[field_name] = UserChoice(
                field_name=field_name,
                chosen_value=chosen_value,
                chosen_source=chosen_source,
                reason=reason
            )

            # Appliquer la valeur choisie
            if hasattr(self, field_name):
                setattr(self, field_name, chosen_value)

            # Retirer de pending_validation
            if field_name in self.pending_validation:
                self.pending_validation.remove(field_name)

    def to_dict(self) -> dict:
        """Convert to dictionary for storage"""
        return {
            "id": self.id,
            "matching_key": self.matching_key,
            "sources": self.sources,
            "source_urls": self.source_urls,
            "auction_ids": self.auction_ids,
            "conflicts": {k: v.to_dict() for k, v in self.conflicts.items()},
            "user_choices": {k: v.to_dict() for k, v in self.user_choices.items()},
            "pending_validation": self.pending_validation,
            "adresse": self.adresse,
            "code_postal": self.code_postal,
            "ville": self.ville,
            "department": self.department,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "type_bien": self.type_bien.value if self.type_bien else None,
            "surface": self.surface,
            "nb_pieces": self.nb_pieces,
            "nb_chambres": self.nb_chambres,
            "etage": self.etage,
            "description": self.description,
            "description_detaillee": self.description_detaillee,
            "occupation": self.occupation,
            "cadastre": self.cadastre,
            "date_vente": self.date_vente.isoformat() if self.date_vente else None,
            "heure_vente": self.heure_vente,
            "tribunal": self.tribunal,
            "mise_a_prix": self.mise_a_prix,
            "avocat_nom": self.avocat_nom,
            "avocat_telephone": self.avocat_telephone,
            "avocat_email": self.avocat_email,
            "photos": self.photos,
            "documents": self.documents,
            "confidence_score": self.confidence_score,
            "last_consolidated": self.last_consolidated.isoformat(),
        }
