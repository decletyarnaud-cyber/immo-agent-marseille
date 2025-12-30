# CLAUDE.md - Immo Agent Marseille

This file provides guidance to Claude Code (claude.ai/code) when working with this repository.

## Project Overview

Immo-Agent Marseille is a judicial real estate auction tracker for the Marseille, Aix-en-Provence, and Toulon regions (departments 13 and 83 in France). It scrapes auction listings from multiple sources, extracts data from legal documents (procès-verbaux), compares prices against official market data (DVF), and provides opportunity scoring.

## Service Info

| Property | Value |
|----------|-------|
| **Service Name** | immo-marseille |
| **Port** | 8501 |
| **Type** | Streamlit |
| **URL** | http://localhost:8501 |
| **GitHub** | https://github.com/decletyarnaud-cyber/immo-agent-marseille |
| **launchd** | `com.ade.immo-marseille` |

### Service Management

```bash
# Via pctl (recommended)
pctl start immo-marseille
pctl stop immo-marseille
pctl restart immo-marseille
pctl logs immo-marseille
pctl open immo-marseille

# Direct launchctl
launchctl load ~/Library/LaunchAgents/com.ade.immo-marseille.plist
launchctl unload ~/Library/LaunchAgents/com.ade.immo-marseille.plist
```

## Commands

```bash
# Install dependencies
pip install -r requirements.txt

# CLI commands (via main.py)
python main.py scrape          # Scrape auctions from all sources
python main.py analyze         # Analyze auctions against DVF market data
python main.py download-dvf    # Download DVF (Demandes de Valeurs Foncières) data
python main.py export          # Export auctions to CSV
python main.py web             # Start Streamlit web interface (localhost:8501)
python main.py run-all         # Full pipeline: scrape + analyze

# Scheduler for automated daily runs
python scheduler.py            # Run daemon (scrapes daily at 06:00)
python scheduler.py --once     # Single execution
python scheduler.py --run-now  # Execute immediately then continue as daemon

# Direct Streamlit start
streamlit run src/web/app.py --server.port 8501
```

## Architecture

### Data Flow

```
Scrapers → Database (SQLite) → Analysis (DVF comparison) → Web UI / CSV Export
```

### Core Modules

**Scrapers** (`src/scrapers/`):
- `LicitorScraper`: Scrapes licitor.com tribunal listings
- `EncherePubliquesScraper`: Scrapes encheres-publiques.com
- `VenchScraper`: Scrapes vench.fr
- `LawyerScraper`: Extracts PV documents from lawyer websites
- `BaseScraper`: Abstract base class for all scrapers

**Extractors** (`src/extractors/`):
- `PDFParser`: PDF text extraction with pdfplumber/PyMuPDF
- `OCRHandler`: Fallback OCR via pytesseract for image PDFs
- `DataExtractor`: Structured data extraction from PV documents
- `LLMExtractor`: Claude-powered extraction for complex documents

**Analysis** (`src/analysis/`):
- `DVFClient`: Downloads/queries official French transaction data
- `MarketAnalyzer`: Finds comparable sales, calculates €/m²
- `PropertyValuator`: Computes opportunity scores (0-100)
- `NeighborhoodAnalyzer`: Analyzes area characteristics

**Storage** (`src/storage/`):
- `Database`: SQLite with auctions, lawyers tables
- `CSVHandler`: CSV export functionality
- Models: `Auction`, `Lawyer`, `DVFTransaction`

**Web** (`src/web/app.py`):
- Streamlit dashboard
- Search and filtering
- Opportunity badges
- Map visualization (Folium)
- CSV export

### Key Data Models

**Auction**:
- `address`, `surface`, `mise_a_prix`
- `date_vente`, `dates_visite`
- `tribunal`, `lawyer_id`
- `pv_status`, `pv_url`
- `score_opportunite`, `decote_pourcentage`
- `prix_m2_marche`, `prix_m2_vente`

### Opportunity Scoring

Thresholds in `config/settings.py`:
- **Good deal**: 20%+ below market
- **Opportunity**: 30%+ below market
- **Excellent**: 40%+ below market

## Data Sources

1. **Licitor** (licitor.com) - Tribunal auction listings
2. **Enchères-Publiques** (encheres-publiques.com) - Aggregator
3. **Vench** (vench.fr) - Additional source
4. **DVF** (data.gouv.fr) - Official transaction data
5. **Lawyer websites** - PV documents

## Configuration

### config/settings.py

```python
DEPARTMENTS = ["13", "83"]  # Bouches-du-Rhône, Var
CITIES = ["Marseille", "Aix-en-Provence", "Toulon", ...]
TRIBUNAUX = ["TJ Marseille", "TJ Aix-en-Provence", "TJ Toulon"]
```

### config/lawyers_config.yaml

Lawyer website configurations for PV document scraping.

## Database

SQLite database at `data/auctions.db`:

```sql
-- Main tables
auctions (id, address, surface, mise_a_prix, date_vente, ...)
lawyers (id, name, email, phone, tribunal, website)
dvf_transactions (id, address, price, surface, date, ...)
```

## Language Note

This project uses French domain terms:
- **enchères** = auctions
- **tribunal** = court
- **avocat** = lawyer
- **mise à prix** = starting price
- **procès-verbal (PV)** = auction report/minutes
- **adjudication** = sale/award
