#!/usr/bin/env python3
"""
Immo-Agent - Judicial Real Estate Auction Tracker
Main entry point for the application
"""
import argparse
import sys
from pathlib import Path
from loguru import logger

# Configure logging
logger.remove()
logger.add(
    sys.stderr,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan> - <level>{message}</level>",
    level="INFO"
)
logger.add(
    "logs/immo_agent_{time:YYYY-MM-DD}.log",
    rotation="1 day",
    retention="30 days",
    level="DEBUG"
)

from config.settings import WEB
from src.storage.database import Database
from src.storage.csv_handler import CSVHandler
from src.scrapers import LicitorScraper, EncherePubliquesScraper, VenchScraper
from src.scrapers.cross_validator import CrossValidator
from src.scrapers.consolidator import AuctionConsolidator
from src.analysis import DVFClient, PropertyValuator


def run_scraping(cross_validate: bool = True):
    """Run scraping from all sources with optional cross-validation"""
    logger.info("Starting auction scraping...")

    db = Database()
    licitor_auctions = []
    encheres_auctions = []
    other_auctions = []

    # Licitor
    try:
        logger.info("Scraping Licitor...")
        scraper = LicitorScraper()
        auctions = scraper.scrape_all_tribunaux()
        licitor_auctions.extend(auctions)
        logger.info(f"Licitor: {len(auctions)} auctions found")
    except Exception as e:
        logger.error(f"Licitor scraping failed: {e}")

    # Enchères Publiques
    try:
        logger.info("Scraping Enchères Publiques...")
        scraper = EncherePubliquesScraper()
        auctions = scraper.scrape_all_cities()
        encheres_auctions.extend(auctions)
        logger.info(f"Enchères Publiques: {len(auctions)} auctions found")
    except Exception as e:
        logger.error(f"Enchères Publiques scraping failed: {e}")

    # Vench
    try:
        logger.info("Scraping Vench...")
        scraper = VenchScraper()
        auctions = scraper.scrape_all_tribunaux()
        other_auctions.extend(auctions)
        logger.info(f"Vench: {len(auctions)} auctions found")
    except Exception as e:
        logger.error(f"Vench scraping failed: {e}")

    # Cross-validate Licitor and Enchères Publiques
    if cross_validate and licitor_auctions and encheres_auctions:
        logger.info("Cross-validating sources...")
        validator = CrossValidator()
        validated_auctions = validator.validate_and_merge_all(licitor_auctions, encheres_auctions)
        stats = validator.get_stats()
        logger.info(f"Cross-validation: {stats['matches_found']} matches, {stats['fields_improved']} fields improved")
        all_auctions = validated_auctions + other_auctions
    else:
        all_auctions = licitor_auctions + encheres_auctions + other_auctions

    # Save to database
    saved_count = 0
    for auction in all_auctions:
        try:
            db.save_auction(auction)
            saved_count += 1
        except Exception as e:
            logger.warning(f"Failed to save auction: {e}")

    logger.info(f"Scraping complete. Total: {len(all_auctions)} auctions, {saved_count} saved")

    # Consolidate auctions from all sources
    run_consolidation(licitor_auctions, encheres_auctions, other_auctions, db)

    return all_auctions


def run_consolidation(licitor_auctions=None, encheres_auctions=None, vench_auctions=None, db=None):
    """Consolidate auctions from multiple sources and detect conflicts"""
    logger.info("Starting multi-source consolidation...")

    if db is None:
        db = Database()

    # If no auctions provided, load from database
    if licitor_auctions is None or encheres_auctions is None or vench_auctions is None:
        all_db_auctions = db.get_all_auctions(limit=1000)
        licitor_auctions = [a for a in all_db_auctions if a.source == "licitor"]
        encheres_auctions = [a for a in all_db_auctions if a.source == "encheres_publiques"]
        vench_auctions = [a for a in all_db_auctions if a.source == "vench"]

    # Prepare data for consolidator
    auctions_by_source = {
        "licitor": licitor_auctions or [],
        "encheres_publiques": encheres_auctions or [],
        "vench": vench_auctions or [],
    }

    # Filter out empty sources
    auctions_by_source = {k: v for k, v in auctions_by_source.items() if v}

    if not auctions_by_source:
        logger.info("No auctions to consolidate")
        return []

    # Run consolidation
    consolidator = AuctionConsolidator()
    consolidated = consolidator.consolidate(auctions_by_source)

    # Save consolidated auctions
    saved = 0
    conflicts_total = 0
    for auction in consolidated:
        try:
            db.save_consolidated_auction(auction)
            saved += 1
            conflicts_total += len(auction.pending_validation)
        except Exception as e:
            logger.warning(f"Failed to save consolidated auction: {e}")

    logger.info(f"Consolidation complete. {saved} consolidated auctions, {conflicts_total} conflicts detected")
    return consolidated


def run_analysis():
    """Analyze all auctions against market data"""
    logger.info("Starting market analysis...")

    db = Database()
    valuator = PropertyValuator()

    # Get all auctions that need analysis
    auctions = db.get_upcoming_auctions(days=60)
    logger.info(f"Analyzing {len(auctions)} auctions...")

    for auction in auctions:
        try:
            result = valuator.valuate(auction)
            # Update auction with analysis results
            db.save_auction(result.auction)
        except Exception as e:
            logger.warning(f"Failed to analyze auction {auction.source_id}: {e}")

    logger.info("Analysis complete")


def download_dvf():
    """Download DVF market data"""
    logger.info("Downloading DVF data...")

    client = DVFClient()
    paths = client.download_all_departments(years=3)

    logger.info(f"Downloaded {len(paths)} DVF data files")


def export_csv():
    """Export auctions to CSV"""
    logger.info("Exporting to CSV...")

    db = Database()
    csv_handler = CSVHandler()

    auctions = db.get_all_auctions(limit=5000)
    path = csv_handler.export_auctions(auctions)

    logger.info(f"Exported to {path}")


def run_web():
    """Start the Streamlit web interface"""
    import subprocess
    logger.info("Starting web interface...")
    subprocess.run([
        sys.executable, "-m", "streamlit", "run",
        str(Path(__file__).parent / "src" / "web" / "app.py"),
        "--server.port", str(WEB["port"]),
        "--server.address", WEB["host"]
    ])


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Immo-Agent - Judicial Real Estate Auction Tracker"
    )

    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # Scrape command
    subparsers.add_parser("scrape", help="Run scraping from all sources")

    # Analyze command
    subparsers.add_parser("analyze", help="Analyze auctions against market data")

    # Download DVF command
    subparsers.add_parser("download-dvf", help="Download DVF market data")

    # Export command
    subparsers.add_parser("export", help="Export auctions to CSV")

    # Web command
    subparsers.add_parser("web", help="Start the web interface")

    # Consolidate command
    subparsers.add_parser("consolidate", help="Consolidate auctions from all sources")

    # Full pipeline command
    subparsers.add_parser("run-all", help="Run full pipeline (scrape + analyze)")

    args = parser.parse_args()

    if args.command == "scrape":
        run_scraping()
    elif args.command == "analyze":
        run_analysis()
    elif args.command == "download-dvf":
        download_dvf()
    elif args.command == "export":
        export_csv()
    elif args.command == "web":
        run_web()
    elif args.command == "consolidate":
        run_consolidation()
    elif args.command == "run-all":
        run_scraping()
        run_analysis()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
