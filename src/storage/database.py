"""
SQLite database module for persistent storage
"""
import sqlite3
import json
from datetime import datetime, date
from pathlib import Path
from typing import List, Optional, Dict, Any
from contextlib import contextmanager
from loguru import logger

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from config.settings import DATABASE_PATH
from src.storage.models import (
    Auction, Lawyer, PropertyType, AuctionStatus, PVStatus,
    ConsolidatedAuction, FieldConflict, UserChoice, SourceData
)


def normalize_property_type(type_bien: Optional[str]) -> PropertyType:
    """Normalize property type string to PropertyType enum"""
    if not type_bien:
        return PropertyType.AUTRE

    normalized = type_bien.lower().strip()

    # Handle plural and variant forms
    mapping = {
        "appartement": PropertyType.APPARTEMENT,
        "appartements": PropertyType.APPARTEMENT,
        "maison": PropertyType.MAISON,
        "maisons": PropertyType.MAISON,
        "local_commercial": PropertyType.LOCAL_COMMERCIAL,
        "local commercial": PropertyType.LOCAL_COMMERCIAL,
        "locaux-commerciaux": PropertyType.LOCAL_COMMERCIAL,
        "locaux commerciaux": PropertyType.LOCAL_COMMERCIAL,
        "immeuble": PropertyType.LOCAL_COMMERCIAL,
        "immeubles": PropertyType.LOCAL_COMMERCIAL,
        "terrain": PropertyType.TERRAIN,
        "terrains": PropertyType.TERRAIN,
        "parking": PropertyType.PARKING,
        "parkings": PropertyType.PARKING,
        "box": PropertyType.PARKING,
        "garage": PropertyType.PARKING,
        "cave": PropertyType.AUTRE,
        "autre": PropertyType.AUTRE,
        "autres": PropertyType.AUTRE,
    }

    return mapping.get(normalized, PropertyType.AUTRE)


class Database:
    """SQLite database for storing auction data"""

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or DATABASE_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_database()

    @contextmanager
    def get_connection(self):
        """Get database connection context manager"""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _init_database(self):
        """Initialize database tables"""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # Lawyers table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS lawyers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    nom TEXT NOT NULL,
                    cabinet TEXT,
                    adresse TEXT,
                    telephone TEXT,
                    email TEXT,
                    site_web TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(nom, cabinet)
                )
            """)

            # Auctions table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS auctions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source TEXT NOT NULL,
                    source_id TEXT,
                    url TEXT UNIQUE,
                    adresse TEXT,
                    code_postal TEXT,
                    ville TEXT,
                    department TEXT,
                    latitude REAL,
                    longitude REAL,
                    type_bien TEXT,
                    surface REAL,
                    nb_pieces INTEGER,
                    nb_chambres INTEGER,
                    etage INTEGER,
                    description TEXT,
                    date_vente DATE,
                    heure_vente TEXT,
                    dates_visite TEXT,
                    date_jugement DATE,
                    mise_a_prix REAL,
                    prix_adjudication REAL,
                    tribunal TEXT,
                    lawyer_id INTEGER,
                    pv_status TEXT,
                    pv_url TEXT,
                    pv_local_path TEXT,
                    prix_marche_estime REAL,
                    prix_m2_marche REAL,
                    decote_pourcentage REAL,
                    score_opportunite REAL,
                    status TEXT DEFAULT 'a_venir',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (lawyer_id) REFERENCES lawyers(id)
                )
            """)

            # Create indexes
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_auctions_code_postal ON auctions(code_postal)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_auctions_date_vente ON auctions(date_vente)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_auctions_source ON auctions(source)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_auctions_status ON auctions(status)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_auctions_score ON auctions(score_opportunite)")

            # Add new columns if they don't exist (for schema migration)
            self._add_column_if_not_exists(cursor, "auctions", "avocat_nom", "TEXT")
            self._add_column_if_not_exists(cursor, "auctions", "avocat_cabinet", "TEXT")
            self._add_column_if_not_exists(cursor, "auctions", "avocat_adresse", "TEXT")
            self._add_column_if_not_exists(cursor, "auctions", "avocat_telephone", "TEXT")
            self._add_column_if_not_exists(cursor, "auctions", "avocat_email", "TEXT")
            self._add_column_if_not_exists(cursor, "auctions", "avocat_site_web", "TEXT")

            # New columns for enriched data from encheres-publiques.com
            self._add_column_if_not_exists(cursor, "auctions", "description_detaillee", "TEXT")
            self._add_column_if_not_exists(cursor, "auctions", "occupation", "TEXT")
            self._add_column_if_not_exists(cursor, "auctions", "cadastre", "TEXT")
            self._add_column_if_not_exists(cursor, "auctions", "photos", "TEXT")  # JSON array
            self._add_column_if_not_exists(cursor, "auctions", "documents", "TEXT")  # JSON array

            # Adjudication results table - stores historical auction sale prices
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS adjudication_results (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source TEXT NOT NULL,
                    source_url TEXT,
                    date_adjudication DATE,
                    adresse TEXT,
                    code_postal TEXT NOT NULL,
                    ville TEXT,
                    type_bien TEXT,
                    surface REAL,
                    nb_pieces INTEGER,
                    mise_a_prix REAL,
                    prix_adjuge REAL,
                    prix_m2 REAL,
                    tribunal TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(source, code_postal, date_adjudication, prix_adjuge)
                )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_adj_code_postal ON adjudication_results(code_postal)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_adj_date ON adjudication_results(date_adjudication)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_adj_type ON adjudication_results(type_bien)")

            # Consolidated auctions table - stores merged data from multiple sources
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS consolidated_auctions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    matching_key TEXT UNIQUE NOT NULL,
                    sources TEXT,  -- JSON array ["licitor", "vench"]
                    source_urls TEXT,  -- JSON {"licitor": "url1", ...}
                    source_data TEXT,  -- JSON full data by source
                    auction_ids TEXT,  -- JSON {"licitor": 1, "vench": 2}
                    conflicts TEXT,  -- JSON {field: FieldConflict}
                    user_choices TEXT,  -- JSON {field: UserChoice}
                    pending_validation TEXT,  -- JSON array of field names
                    adresse TEXT,
                    code_postal TEXT,
                    ville TEXT,
                    department TEXT,
                    latitude REAL,
                    longitude REAL,
                    type_bien TEXT,
                    surface REAL,
                    nb_pieces INTEGER,
                    nb_chambres INTEGER,
                    etage INTEGER,
                    description TEXT,
                    description_detaillee TEXT,
                    occupation TEXT,
                    cadastre TEXT,
                    date_vente DATE,
                    heure_vente TEXT,
                    tribunal TEXT,
                    mise_a_prix REAL,
                    avocat_nom TEXT,
                    avocat_telephone TEXT,
                    avocat_email TEXT,
                    photos TEXT,  -- JSON array
                    documents TEXT,  -- JSON array
                    confidence_score REAL,
                    last_consolidated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_cons_date_vente ON consolidated_auctions(date_vente)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_cons_tribunal ON consolidated_auctions(tribunal)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_cons_confidence ON consolidated_auctions(confidence_score)")

            logger.info(f"Database initialized at {self.db_path}")

    def _add_column_if_not_exists(self, cursor, table: str, column: str, col_type: str):
        """Add a column to a table if it doesn't exist"""
        cursor.execute(f"PRAGMA table_info({table})")
        columns = [row[1] for row in cursor.fetchall()]
        if column not in columns:
            cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}")
            logger.info(f"Added column {column} to {table}")

    # ===== LAWYERS =====

    def save_lawyer(self, lawyer: Lawyer) -> int:
        """Save or update a lawyer"""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            if lawyer.id:
                # Update
                cursor.execute("""
                    UPDATE lawyers SET
                        nom = ?, cabinet = ?, adresse = ?, telephone = ?,
                        email = ?, site_web = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, (
                    lawyer.nom, lawyer.cabinet, lawyer.adresse, lawyer.telephone,
                    lawyer.email, lawyer.site_web, lawyer.id
                ))
                return lawyer.id
            else:
                # Insert or get existing
                cursor.execute("""
                    INSERT OR IGNORE INTO lawyers (nom, cabinet, adresse, telephone, email, site_web)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    lawyer.nom, lawyer.cabinet, lawyer.adresse,
                    lawyer.telephone, lawyer.email, lawyer.site_web
                ))

                if cursor.lastrowid:
                    return cursor.lastrowid

                # Get existing ID
                cursor.execute(
                    "SELECT id FROM lawyers WHERE nom = ? AND cabinet = ?",
                    (lawyer.nom, lawyer.cabinet)
                )
                row = cursor.fetchone()
                return row["id"] if row else 0

    def get_lawyer(self, lawyer_id: int) -> Optional[Lawyer]:
        """Get lawyer by ID"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM lawyers WHERE id = ?", (lawyer_id,))
            row = cursor.fetchone()

            if row:
                return Lawyer(
                    id=row["id"],
                    nom=row["nom"],
                    cabinet=row["cabinet"] or "",
                    adresse=row["adresse"] or "",
                    telephone=row["telephone"] or "",
                    email=row["email"] or "",
                    site_web=row["site_web"] or "",
                )
            return None

    def get_all_lawyers(self) -> List[Lawyer]:
        """Get all lawyers"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM lawyers ORDER BY nom")
            rows = cursor.fetchall()

            return [
                Lawyer(
                    id=row["id"],
                    nom=row["nom"],
                    cabinet=row["cabinet"] or "",
                    adresse=row["adresse"] or "",
                    telephone=row["telephone"] or "",
                    email=row["email"] or "",
                    site_web=row["site_web"] or "",
                )
                for row in rows
            ]

    # ===== AUCTIONS =====

    def save_auction(self, auction: Auction) -> int:
        """Save or update an auction"""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # Serialize dates_visite
            dates_visite_json = json.dumps([
                d.isoformat() for d in auction.dates_visite
            ]) if auction.dates_visite else "[]"

            # Serialize photos and documents
            photos_json = json.dumps(auction.photos) if auction.photos else "[]"
            documents_json = json.dumps(auction.documents) if auction.documents else "[]"

            if auction.id:
                # Update
                cursor.execute("""
                    UPDATE auctions SET
                        source = ?, source_id = ?, url = ?, adresse = ?,
                        code_postal = ?, ville = ?, department = ?,
                        latitude = ?, longitude = ?, type_bien = ?,
                        surface = ?, nb_pieces = ?, nb_chambres = ?, etage = ?,
                        description = ?, description_detaillee = ?, occupation = ?, cadastre = ?,
                        photos = ?, documents = ?,
                        date_vente = ?, heure_vente = ?,
                        dates_visite = ?, date_jugement = ?, mise_a_prix = ?,
                        prix_adjudication = ?, tribunal = ?, lawyer_id = ?,
                        avocat_nom = ?, avocat_cabinet = ?, avocat_adresse = ?,
                        avocat_telephone = ?, avocat_email = ?, avocat_site_web = ?,
                        pv_status = ?, pv_url = ?, pv_local_path = ?,
                        prix_marche_estime = ?, prix_m2_marche = ?,
                        decote_pourcentage = ?, score_opportunite = ?,
                        status = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, (
                    auction.source, auction.source_id, auction.url, auction.adresse,
                    auction.code_postal, auction.ville, auction.department,
                    auction.latitude, auction.longitude, auction.type_bien.value if auction.type_bien else None,
                    auction.surface, auction.nb_pieces, auction.nb_chambres, auction.etage,
                    auction.description, auction.description_detaillee, auction.occupation, auction.cadastre,
                    photos_json, documents_json,
                    auction.date_vente.isoformat() if auction.date_vente else None,
                    auction.heure_vente, dates_visite_json,
                    auction.date_jugement.isoformat() if auction.date_jugement else None,
                    auction.mise_a_prix, auction.prix_adjudication, auction.tribunal,
                    auction.lawyer_id, auction.avocat_nom, auction.avocat_cabinet, auction.avocat_adresse,
                    auction.avocat_telephone, auction.avocat_email, auction.avocat_site_web,
                    auction.pv_status.value if auction.pv_status else None,
                    auction.pv_url, auction.pv_local_path, auction.prix_marche_estime,
                    auction.prix_m2_marche, auction.decote_pourcentage, auction.score_opportunite,
                    auction.status.value if auction.status else None, auction.id
                ))
                return auction.id
            else:
                # Insert
                cursor.execute("""
                    INSERT OR REPLACE INTO auctions (
                        source, source_id, url, adresse, code_postal, ville, department,
                        latitude, longitude, type_bien, surface, nb_pieces, nb_chambres,
                        etage, description, description_detaillee, occupation, cadastre,
                        photos, documents,
                        date_vente, heure_vente, dates_visite,
                        date_jugement, mise_a_prix, prix_adjudication, tribunal, lawyer_id,
                        avocat_nom, avocat_cabinet, avocat_adresse, avocat_telephone, avocat_email, avocat_site_web,
                        pv_status, pv_url, pv_local_path, prix_marche_estime, prix_m2_marche,
                        decote_pourcentage, score_opportunite, status
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    auction.source, auction.source_id, auction.url, auction.adresse,
                    auction.code_postal, auction.ville, auction.department,
                    auction.latitude, auction.longitude, auction.type_bien.value if auction.type_bien else None,
                    auction.surface, auction.nb_pieces, auction.nb_chambres, auction.etage,
                    auction.description, auction.description_detaillee, auction.occupation, auction.cadastre,
                    photos_json, documents_json,
                    auction.date_vente.isoformat() if auction.date_vente else None,
                    auction.heure_vente, dates_visite_json,
                    auction.date_jugement.isoformat() if auction.date_jugement else None,
                    auction.mise_a_prix, auction.prix_adjudication, auction.tribunal,
                    auction.lawyer_id, auction.avocat_nom, auction.avocat_cabinet, auction.avocat_adresse,
                    auction.avocat_telephone, auction.avocat_email, auction.avocat_site_web,
                    auction.pv_status.value if auction.pv_status else None,
                    auction.pv_url, auction.pv_local_path, auction.prix_marche_estime,
                    auction.prix_m2_marche, auction.decote_pourcentage, auction.score_opportunite,
                    auction.status.value if auction.status else "a_venir"
                ))
                return cursor.lastrowid

    def _row_to_auction(self, row) -> Auction:
        """Convert database row to Auction object"""
        dates_visite = []
        if row["dates_visite"]:
            try:
                dates_visite = [
                    datetime.fromisoformat(d)
                    for d in json.loads(row["dates_visite"])
                ]
            except:
                pass

        # Handle new columns that might not exist in old databases
        avocat_nom = None
        avocat_cabinet = None
        avocat_adresse = None
        avocat_telephone = None
        avocat_email = None
        avocat_site_web = None
        description_detaillee = ""
        occupation = ""
        cadastre = ""
        photos = []
        documents = []

        try:
            avocat_nom = row["avocat_nom"]
            avocat_cabinet = row["avocat_cabinet"]
            avocat_adresse = row["avocat_adresse"]
            avocat_telephone = row["avocat_telephone"]
            avocat_email = row["avocat_email"]
            avocat_site_web = row["avocat_site_web"]
        except (KeyError, IndexError):
            pass

        try:
            description_detaillee = row["description_detaillee"] or ""
            occupation = row["occupation"] or ""
            cadastre = row["cadastre"] or ""
            if row["photos"]:
                photos = json.loads(row["photos"])
            if row["documents"]:
                documents = json.loads(row["documents"])
        except (KeyError, IndexError):
            pass

        return Auction(
            id=row["id"],
            source=row["source"],
            source_id=row["source_id"] or "",
            url=row["url"] or "",
            adresse=row["adresse"] or "",
            code_postal=row["code_postal"] or "",
            ville=row["ville"] or "",
            department=row["department"] or "",
            latitude=row["latitude"],
            longitude=row["longitude"],
            type_bien=normalize_property_type(row["type_bien"]),
            surface=row["surface"],
            nb_pieces=row["nb_pieces"],
            nb_chambres=row["nb_chambres"],
            etage=row["etage"],
            description=row["description"] or "",
            description_detaillee=description_detaillee,
            occupation=occupation,
            cadastre=cadastre,
            photos=photos,
            documents=documents,
            date_vente=date.fromisoformat(row["date_vente"]) if row["date_vente"] else None,
            heure_vente=row["heure_vente"],
            dates_visite=dates_visite,
            date_jugement=date.fromisoformat(row["date_jugement"]) if row["date_jugement"] else None,
            mise_a_prix=row["mise_a_prix"],
            prix_adjudication=row["prix_adjudication"],
            tribunal=row["tribunal"] or "",
            lawyer_id=row["lawyer_id"],
            avocat_nom=avocat_nom,
            avocat_cabinet=avocat_cabinet,
            avocat_adresse=avocat_adresse,
            avocat_telephone=avocat_telephone,
            avocat_email=avocat_email,
            avocat_site_web=avocat_site_web,
            pv_status=PVStatus(row["pv_status"]) if row["pv_status"] else PVStatus.NON_DISPONIBLE,
            pv_url=row["pv_url"],
            pv_local_path=row["pv_local_path"],
            prix_marche_estime=row["prix_marche_estime"],
            prix_m2_marche=row["prix_m2_marche"],
            decote_pourcentage=row["decote_pourcentage"],
            score_opportunite=row["score_opportunite"],
            status=AuctionStatus(row["status"]) if row["status"] else AuctionStatus.A_VENIR,
        )

    def get_auction(self, auction_id: int) -> Optional[Auction]:
        """Get auction by ID"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM auctions WHERE id = ?", (auction_id,))
            row = cursor.fetchone()
            return self._row_to_auction(row) if row else None

    def get_auction_by_url(self, url: str) -> Optional[Auction]:
        """Get auction by URL"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM auctions WHERE url = ?", (url,))
            row = cursor.fetchone()
            return self._row_to_auction(row) if row else None

    def get_all_auctions(
        self,
        status: Optional[AuctionStatus] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Auction]:
        """Get all auctions with optional filtering"""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            if status:
                cursor.execute(
                    "SELECT * FROM auctions WHERE status = ? ORDER BY date_vente LIMIT ? OFFSET ?",
                    (status.value, limit, offset)
                )
            else:
                cursor.execute(
                    "SELECT * FROM auctions ORDER BY date_vente LIMIT ? OFFSET ?",
                    (limit, offset)
                )

            return [self._row_to_auction(row) for row in cursor.fetchall()]

    def get_upcoming_auctions(self, days: int = 30) -> List[Auction]:
        """Get auctions in the next N days"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM auctions
                WHERE date_vente >= date('now')
                AND date_vente <= date('now', '+' || ? || ' days')
                ORDER BY date_vente
            """, (days,))
            return [self._row_to_auction(row) for row in cursor.fetchall()]

    def get_top_opportunities(self, limit: int = 10) -> List[Auction]:
        """Get top opportunities by score"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM auctions
                WHERE score_opportunite IS NOT NULL
                AND date_vente >= date('now')
                ORDER BY score_opportunite DESC
                LIMIT ?
            """, (limit,))
            return [self._row_to_auction(row) for row in cursor.fetchall()]

    def search_auctions(
        self,
        code_postal: Optional[str] = None,
        ville: Optional[str] = None,
        type_bien: Optional[PropertyType] = None,
        prix_min: Optional[float] = None,
        prix_max: Optional[float] = None,
        surface_min: Optional[float] = None,
        surface_max: Optional[float] = None,
    ) -> List[Auction]:
        """Search auctions with filters"""
        conditions = ["1=1"]
        params = []

        if code_postal:
            conditions.append("code_postal = ?")
            params.append(code_postal)

        if ville:
            conditions.append("ville LIKE ?")
            params.append(f"%{ville}%")

        if type_bien:
            conditions.append("type_bien = ?")
            params.append(type_bien.value)

        if prix_min is not None:
            conditions.append("mise_a_prix >= ?")
            params.append(prix_min)

        if prix_max is not None:
            conditions.append("mise_a_prix <= ?")
            params.append(prix_max)

        if surface_min is not None:
            conditions.append("surface >= ?")
            params.append(surface_min)

        if surface_max is not None:
            conditions.append("surface <= ?")
            params.append(surface_max)

        query = f"SELECT * FROM auctions WHERE {' AND '.join(conditions)} ORDER BY date_vente"

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            return [self._row_to_auction(row) for row in cursor.fetchall()]

    def get_stats(self) -> Dict[str, Any]:
        """Get database statistics"""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            stats = {}

            # Total auctions
            cursor.execute("SELECT COUNT(*) FROM auctions")
            stats["total_auctions"] = cursor.fetchone()[0]

            # By status
            cursor.execute("""
                SELECT status, COUNT(*) as count
                FROM auctions
                GROUP BY status
            """)
            stats["by_status"] = {row["status"]: row["count"] for row in cursor.fetchall()}

            # By source
            cursor.execute("""
                SELECT source, COUNT(*) as count
                FROM auctions
                GROUP BY source
            """)
            stats["by_source"] = {row["source"]: row["count"] for row in cursor.fetchall()}

            # Upcoming auctions
            cursor.execute("""
                SELECT COUNT(*) FROM auctions
                WHERE date_vente >= date('now')
            """)
            stats["upcoming"] = cursor.fetchone()[0]

            # Lawyers count
            cursor.execute("SELECT COUNT(*) FROM lawyers")
            stats["total_lawyers"] = cursor.fetchone()[0]

            return stats

    # ===== ADJUDICATION RESULTS =====

    def save_adjudication_result(
        self,
        source: str,
        code_postal: str,
        prix_adjuge: float,
        source_url: Optional[str] = None,
        date_adjudication: Optional[date] = None,
        adresse: Optional[str] = None,
        ville: Optional[str] = None,
        type_bien: Optional[str] = None,
        surface: Optional[float] = None,
        nb_pieces: Optional[int] = None,
        mise_a_prix: Optional[float] = None,
        tribunal: Optional[str] = None,
    ) -> Optional[int]:
        """Save an adjudication result"""
        # Calculate price per m² if we have surface
        prix_m2 = round(prix_adjuge / surface, 0) if surface and surface > 0 else None

        with self.get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute("""
                    INSERT OR IGNORE INTO adjudication_results
                    (source, source_url, date_adjudication, adresse, code_postal, ville,
                     type_bien, surface, nb_pieces, mise_a_prix, prix_adjuge, prix_m2, tribunal)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    source, source_url, date_adjudication.isoformat() if date_adjudication else None,
                    adresse, code_postal, ville, type_bien, surface, nb_pieces,
                    mise_a_prix, prix_adjuge, prix_m2, tribunal
                ))
                return cursor.lastrowid if cursor.rowcount > 0 else None
            except Exception as e:
                logger.error(f"Error saving adjudication result: {e}")
                return None

    def get_adjudication_stats_by_postal(
        self,
        code_postal_prefix: str = "13",
        type_bien: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Get aggregated adjudication stats by postal code"""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            query = """
                SELECT
                    code_postal,
                    ville,
                    COUNT(*) as nb_ventes,
                    AVG(prix_adjuge) as prix_moyen,
                    AVG(prix_m2) as prix_m2_moyen,
                    MIN(prix_m2) as prix_m2_min,
                    MAX(prix_m2) as prix_m2_max,
                    AVG(surface) as surface_moyenne,
                    MIN(date_adjudication) as date_min,
                    MAX(date_adjudication) as date_max
                FROM adjudication_results
                WHERE code_postal LIKE ?
            """
            params = [f"{code_postal_prefix}%"]

            if type_bien:
                query += " AND type_bien = ?"
                params.append(type_bien)

            query += """
                GROUP BY code_postal
                HAVING nb_ventes >= 1
                ORDER BY nb_ventes DESC
            """

            cursor.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]

    def get_all_adjudication_results(
        self,
        code_postal_prefix: Optional[str] = None,
        type_bien: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Get all adjudication results with optional filtering"""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            conditions = ["1=1"]
            params = []

            if code_postal_prefix:
                conditions.append("code_postal LIKE ?")
                params.append(f"{code_postal_prefix}%")

            if type_bien:
                conditions.append("type_bien = ?")
                params.append(type_bien)

            query = f"""
                SELECT * FROM adjudication_results
                WHERE {' AND '.join(conditions)}
                ORDER BY date_adjudication DESC
                LIMIT ?
            """
            params.append(limit)

            cursor.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]

    def get_adjudication_count(self) -> int:
        """Get total count of adjudication results"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM adjudication_results")
            return cursor.fetchone()[0]

    def get_newest_auctions(self, limit: int = 5) -> List[Auction]:
        """Get the most recently published auctions (furthest sale date = newest listing)"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM auctions
                WHERE date_vente >= date('now')
                ORDER BY date_vente DESC
                LIMIT ?
            """, (limit,))
            return [self._row_to_auction(row) for row in cursor.fetchall()]

    # ===== CONSOLIDATED AUCTIONS =====

    def save_consolidated_auction(self, auction: ConsolidatedAuction) -> int:
        """Save or update a consolidated auction"""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # Serialize complex fields to JSON
            sources_json = json.dumps(auction.sources)
            source_urls_json = json.dumps(auction.source_urls)
            source_data_json = json.dumps({
                k: v.to_dict() for k, v in auction.source_data.items()
            })
            auction_ids_json = json.dumps(auction.auction_ids)
            conflicts_json = json.dumps({
                k: v.to_dict() for k, v in auction.conflicts.items()
            })
            user_choices_json = json.dumps({
                k: v.to_dict() for k, v in auction.user_choices.items()
            })
            pending_json = json.dumps(auction.pending_validation)
            photos_json = json.dumps(auction.photos)
            documents_json = json.dumps(auction.documents)

            if auction.id:
                # Update
                cursor.execute("""
                    UPDATE consolidated_auctions SET
                        matching_key = ?, sources = ?, source_urls = ?, source_data = ?,
                        auction_ids = ?, conflicts = ?, user_choices = ?, pending_validation = ?,
                        adresse = ?, code_postal = ?, ville = ?, department = ?,
                        latitude = ?, longitude = ?, type_bien = ?, surface = ?,
                        nb_pieces = ?, nb_chambres = ?, etage = ?, description = ?,
                        description_detaillee = ?, occupation = ?, cadastre = ?,
                        date_vente = ?, heure_vente = ?, tribunal = ?, mise_a_prix = ?,
                        avocat_nom = ?, avocat_telephone = ?, avocat_email = ?,
                        photos = ?, documents = ?, confidence_score = ?,
                        last_consolidated = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, (
                    auction.matching_key, sources_json, source_urls_json, source_data_json,
                    auction_ids_json, conflicts_json, user_choices_json, pending_json,
                    auction.adresse, auction.code_postal, auction.ville, auction.department,
                    auction.latitude, auction.longitude,
                    auction.type_bien.value if auction.type_bien else None, auction.surface,
                    auction.nb_pieces, auction.nb_chambres, auction.etage, auction.description,
                    auction.description_detaillee, auction.occupation, auction.cadastre,
                    auction.date_vente.isoformat() if auction.date_vente else None,
                    auction.heure_vente, auction.tribunal, auction.mise_a_prix,
                    auction.avocat_nom, auction.avocat_telephone, auction.avocat_email,
                    photos_json, documents_json, auction.confidence_score,
                    auction.id
                ))
                return auction.id
            else:
                # Insert or replace (upsert based on matching_key)
                cursor.execute("""
                    INSERT OR REPLACE INTO consolidated_auctions (
                        matching_key, sources, source_urls, source_data, auction_ids,
                        conflicts, user_choices, pending_validation,
                        adresse, code_postal, ville, department, latitude, longitude,
                        type_bien, surface, nb_pieces, nb_chambres, etage,
                        description, description_detaillee, occupation, cadastre,
                        date_vente, heure_vente, tribunal, mise_a_prix,
                        avocat_nom, avocat_telephone, avocat_email,
                        photos, documents, confidence_score
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    auction.matching_key, sources_json, source_urls_json, source_data_json,
                    auction_ids_json, conflicts_json, user_choices_json, pending_json,
                    auction.adresse, auction.code_postal, auction.ville, auction.department,
                    auction.latitude, auction.longitude,
                    auction.type_bien.value if auction.type_bien else None, auction.surface,
                    auction.nb_pieces, auction.nb_chambres, auction.etage, auction.description,
                    auction.description_detaillee, auction.occupation, auction.cadastre,
                    auction.date_vente.isoformat() if auction.date_vente else None,
                    auction.heure_vente, auction.tribunal, auction.mise_a_prix,
                    auction.avocat_nom, auction.avocat_telephone, auction.avocat_email,
                    photos_json, documents_json, auction.confidence_score
                ))
                return cursor.lastrowid

    def _row_to_consolidated_auction(self, row) -> ConsolidatedAuction:
        """Convert database row to ConsolidatedAuction object"""
        # Parse JSON fields
        sources = json.loads(row["sources"]) if row["sources"] else []
        source_urls = json.loads(row["source_urls"]) if row["source_urls"] else {}
        auction_ids = json.loads(row["auction_ids"]) if row["auction_ids"] else {}

        # Parse source_data
        source_data = {}
        if row["source_data"]:
            raw_source_data = json.loads(row["source_data"])
            for src, data in raw_source_data.items():
                source_data[src] = SourceData(
                    source=data["source"],
                    url=data["url"],
                    scraped_at=datetime.fromisoformat(data["scraped_at"]) if data.get("scraped_at") else datetime.now(),
                    raw_data=data.get("raw_data", {})
                )

        # Parse conflicts
        conflicts = {}
        if row["conflicts"]:
            raw_conflicts = json.loads(row["conflicts"])
            for field, data in raw_conflicts.items():
                conflicts[field] = FieldConflict.from_dict(data)

        # Parse user_choices
        user_choices = {}
        if row["user_choices"]:
            raw_choices = json.loads(row["user_choices"])
            for field, data in raw_choices.items():
                user_choices[field] = UserChoice.from_dict(data)

        pending = json.loads(row["pending_validation"]) if row["pending_validation"] else []
        photos = json.loads(row["photos"]) if row["photos"] else []
        documents = json.loads(row["documents"]) if row["documents"] else []

        return ConsolidatedAuction(
            id=row["id"],
            matching_key=row["matching_key"],
            sources=sources,
            source_urls=source_urls,
            source_data=source_data,
            auction_ids=auction_ids,
            conflicts=conflicts,
            user_choices=user_choices,
            pending_validation=pending,
            adresse=row["adresse"] or "",
            code_postal=row["code_postal"] or "",
            ville=row["ville"] or "",
            department=row["department"] or "",
            latitude=row["latitude"],
            longitude=row["longitude"],
            type_bien=normalize_property_type(row["type_bien"]),
            surface=row["surface"],
            nb_pieces=row["nb_pieces"],
            nb_chambres=row["nb_chambres"],
            etage=row["etage"],
            description=row["description"] or "",
            description_detaillee=row["description_detaillee"] or "",
            occupation=row["occupation"] or "",
            cadastre=row["cadastre"] or "",
            date_vente=date.fromisoformat(row["date_vente"]) if row["date_vente"] else None,
            heure_vente=row["heure_vente"],
            tribunal=row["tribunal"] or "",
            mise_a_prix=row["mise_a_prix"],
            avocat_nom=row["avocat_nom"],
            avocat_telephone=row["avocat_telephone"],
            avocat_email=row["avocat_email"],
            photos=photos,
            documents=documents,
            confidence_score=row["confidence_score"] or 0,
            last_consolidated=datetime.fromisoformat(row["last_consolidated"]) if row["last_consolidated"] else datetime.now(),
        )

    def get_consolidated_auction(self, auction_id: int) -> Optional[ConsolidatedAuction]:
        """Get consolidated auction by ID"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM consolidated_auctions WHERE id = ?", (auction_id,))
            row = cursor.fetchone()
            return self._row_to_consolidated_auction(row) if row else None

    def get_consolidated_auction_by_key(self, matching_key: str) -> Optional[ConsolidatedAuction]:
        """Get consolidated auction by matching key"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM consolidated_auctions WHERE matching_key = ?", (matching_key,))
            row = cursor.fetchone()
            return self._row_to_consolidated_auction(row) if row else None

    def get_all_consolidated_auctions(self, limit: int = 100, offset: int = 0) -> List[ConsolidatedAuction]:
        """Get all consolidated auctions"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM consolidated_auctions
                ORDER BY date_vente
                LIMIT ? OFFSET ?
            """, (limit, offset))
            return [self._row_to_consolidated_auction(row) for row in cursor.fetchall()]

    def get_consolidated_with_conflicts(self) -> List[ConsolidatedAuction]:
        """Get consolidated auctions that have unresolved conflicts"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM consolidated_auctions
                WHERE pending_validation IS NOT NULL
                AND pending_validation != '[]'
                ORDER BY date_vente
            """)
            return [self._row_to_consolidated_auction(row) for row in cursor.fetchall()]

    def resolve_consolidated_conflict(
        self,
        auction_id: int,
        field_name: str,
        chosen_value: Any,
        chosen_source: str,
        reason: str = None
    ) -> Optional[ConsolidatedAuction]:
        """Resolve a conflict for a consolidated auction"""
        auction = self.get_consolidated_auction(auction_id)
        if not auction:
            return None

        auction.resolve_conflict(field_name, chosen_value, chosen_source, reason)
        self.save_consolidated_auction(auction)
        return auction

    def get_consolidated_stats(self) -> Dict[str, Any]:
        """Get statistics about consolidated auctions"""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            stats = {}

            # Total consolidated
            cursor.execute("SELECT COUNT(*) FROM consolidated_auctions")
            stats["total_consolidated"] = cursor.fetchone()[0]

            # With conflicts
            cursor.execute("""
                SELECT COUNT(*) FROM consolidated_auctions
                WHERE pending_validation IS NOT NULL AND pending_validation != '[]'
            """)
            stats["with_conflicts"] = cursor.fetchone()[0]

            # By source count
            cursor.execute("""
                SELECT
                    json_array_length(sources) as source_count,
                    COUNT(*) as count
                FROM consolidated_auctions
                GROUP BY json_array_length(sources)
            """)
            stats["by_source_count"] = {row[0]: row[1] for row in cursor.fetchall()}

            # Average confidence
            cursor.execute("SELECT AVG(confidence_score) FROM consolidated_auctions")
            avg = cursor.fetchone()[0]
            stats["avg_confidence"] = round(avg, 1) if avg else 0

            return stats
