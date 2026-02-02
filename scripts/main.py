#!/usr/bin/env python3
"""
CLI unificado para ejecutar scrapers de supermercados.

Uso:
    python main.py scrape dia                 # Scrape completo de DIA
    python main.py scrape dia --test          # Modo test (límites)
    python main.py scrape dia --dry-run       # Sin enviar a Firebase
    
    python main.py categories pending dia     # Ver categorías pendientes
    python main.py categories stats dia       # Ver estadísticas de mapeos
    python main.py categories map dia ID MASTER_ID  # Mapear manualmente
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime
from typing import List, Optional

from scrapers import NormalizedProduct
from scrapers.categories import CategoryMapper, MasterTaxonomy
from scrapers.categories.taxonomy import get_taxonomy
from scrapers.dia import DiaScraper
from scrapers.ingest import ingest_products
from scrapers.carrefour import CarrefourScraper
from scrapers.consum import ConsumScraper
from scrapers.mercadona import MercadonaScraper
from scrapers.validators import validate_products

# Configuración de logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


def get_scraper(market: str):
    """Obtiene el scraper para un supermercado."""
    scrapers = {
        "dia": DiaScraper,
        "mercadona": MercadonaScraper,
        "carrefour": CarrefourScraper,
        "consum": ConsumScraper,
    }

    if market not in scrapers:
        raise ValueError(f"Supermercado no soportado: {market}")

    return scrapers[market]()


def run_scraper(
    market: str,
    max_categories: Optional[int] = None,
    max_products: Optional[int] = None,
    dry_run: bool = False,
    verbose: bool = False,
) -> List[NormalizedProduct]:
    """
    Ejecuta el scraper para un supermercado.

    Args:
        market: Nombre del supermercado (dia, mercadona, etc.)
        max_categories: Límite de categorías (para testing).
        max_products: Límite de productos por categoría.
        dry_run: Si True, no envía a Firebase.
        verbose: Si True, muestra más información.

    Returns:
        Lista de productos scrapeados.
    """
    if verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    inicio = datetime.now()
    logger.info(f"Iniciando scraper de {market.upper()}...")

    # Obtener scraper
    scraper = get_scraper(market)

    # Obtener categorías
    categories = scraper.get_categories()
    if not categories:
        logger.error("No se encontraron categorías")
        return []

    if max_categories:
        categories = categories[:max_categories]
        logger.info(f"Limitado a {max_categories} categorías (modo test)")

    # Scrapear productos
    all_products: List[NormalizedProduct] = []
    processed = 0
    failed = 0

    total = len(categories)
    for idx, category in enumerate(categories, start=1):
        logger.info(f"[{idx}/{total}] {category}")

        try:
            products = scraper.scrape_category(category)

            if max_products:
                products = products[:max_products]

            all_products.extend(products)
            processed += 1
            logger.info(f"  -> {len(products)} productos")

        except Exception as e:
            failed += 1
            logger.error(f"  -> Error: {e}")

        scraper.http.delay()

    # Guardar mapeos de categorías
    scraper.save_category_mappings()

    # Estadísticas de mapeos
    mapper_stats = scraper.category_mapper.get_stats()

    # Validar productos
    valid_products = validate_products(all_products)

    # Resumen
    fin = datetime.now()
    duracion = (fin - inicio).total_seconds()

    logger.info("")
    logger.info("=" * 50)
    logger.info("RESUMEN")
    logger.info("=" * 50)
    logger.info(f"Categorías procesadas: {processed}")
    logger.info(f"Categorías fallidas: {failed}")
    logger.info(f"Productos totales: {len(all_products)}")
    logger.info(f"Productos válidos: {len(valid_products)}")
    logger.info(f"Duración: {duracion:.1f}s")
    logger.info("")
    logger.info("Mapeos de categorías:")
    logger.info(f"  - Confirmados: {mapper_stats.get('confirmed', 0)}")
    logger.info(f"  - Automáticos: {mapper_stats.get('auto', 0)}")
    logger.info(f"  - Pendientes: {mapper_stats.get('pending', 0)}")
    logger.info("=" * 50)

    # Enviar a Firebase
    if dry_run:
        logger.info("Modo dry-run: no se envía a Firebase")
    else:
        logger.info(f"Enviando {len(valid_products)} productos a Firebase...")
        ingest_products(valid_products, validate=False)

    return valid_products


def cmd_scrape(args):
    """Comando: scrape"""
    max_categories = args.categories
    max_products = args.products

    if args.test:
        max_categories = max_categories or 5
        max_products = max_products or 3
        logger.info("MODO TEST activado")

    run_scraper(
        market=args.market,
        max_categories=max_categories,
        max_products=max_products,
        dry_run=args.dry_run,
        verbose=args.verbose,
    )


def cmd_categories_pending(args):
    """Comando: categories pending"""
    mapper = CategoryMapper(args.market)
    pending = mapper.get_pending()

    if not pending:
        print(f"No hay categorías pendientes para {args.market}")
        return

    print(f"\nCategorías pendientes de mapeo para {args.market.upper()}:")
    print("=" * 60)

    for mapping in pending:
        print(f"\nID: {mapping.source_id}")
        print(f"  Path: {mapping.source_path}")
        if mapping.suggestions:
            print(f"  Sugerencias: {', '.join(mapping.suggestions[:3])}")

    print(f"\nTotal: {len(pending)} categorías pendientes")


def cmd_categories_stats(args):
    """Comando: categories stats"""
    mapper = CategoryMapper(args.market)
    stats = mapper.get_stats()

    print(f"\nEstadísticas de mapeos para {args.market.upper()}:")
    print("=" * 40)
    print(f"  Confirmados: {stats.get('confirmed', 0)}")
    print(f"  Automáticos: {stats.get('auto', 0)}")
    print(f"  Pendientes:  {stats.get('pending', 0)}")
    print(f"  Rechazados:  {stats.get('rejected', 0)}")
    print(f"  Total:       {sum(stats.values())}")


def cmd_categories_map(args):
    """Comando: categories map"""
    mapper = CategoryMapper(args.market)

    # Verificar que la categoría maestra existe
    taxonomy = get_taxonomy()
    master_cat = taxonomy.get(args.master_id)

    if not master_cat:
        print(f"Error: Categoría maestra '{args.master_id}' no encontrada")
        print("\nCategorías disponibles:")
        for cat in taxonomy.get_leaves()[:10]:
            print(f"  - {cat.id}: {cat.name}")
        return

    success = mapper.set_mapping(
        source_id=args.source_id,
        master_id=args.master_id,
        status="confirmed",
    )

    if success:
        mapper.save_mappings()
        print(f"Mapeo confirmado: {args.source_id} -> {args.master_id}")
    else:
        print(f"Error: No se pudo crear el mapeo")


def cmd_categories_taxonomy(args):
    """Comando: categories taxonomy"""
    taxonomy = get_taxonomy()

    print("\nTaxonomía maestra de categorías:")
    print("=" * 50)

    for root in taxonomy.get_roots():
        print(f"\n{root.id}: {root.name}")
        for child in root.children:
            print(f"  - {child.id}: {child.name}")


def main():
    """Punto de entrada del CLI."""
    parser = argparse.ArgumentParser(
        description="Scraper de supermercados",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    subparsers = parser.add_subparsers(dest="command", help="Comandos disponibles")

    # Comando: scrape
    scrape_parser = subparsers.add_parser("scrape", help="Ejecutar scraper")
    scrape_parser.add_argument(
        "market",
        choices=["dia", "mercadona", "carrefour", "consum"],
        help="Supermercado a scrapear",
    )
    scrape_parser.add_argument(
        "--test",
        action="store_true",
        help="Modo test: limita a 5 categorías y 3 productos",
    )
    scrape_parser.add_argument(
        "--categories",
        type=int,
        metavar="N",
        help="Límite de categorías a procesar",
    )
    scrape_parser.add_argument(
        "--products",
        type=int,
        metavar="N",
        help="Límite de productos por categoría",
    )
    scrape_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="No enviar a Firebase (solo scrapear)",
    )
    scrape_parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Mostrar información detallada",
    )
    scrape_parser.set_defaults(func=cmd_scrape)

    # Comando: categories
    cat_parser = subparsers.add_parser("categories", help="Gestión de categorías")
    cat_subparsers = cat_parser.add_subparsers(dest="cat_command")

    # categories pending
    pending_parser = cat_subparsers.add_parser(
        "pending", help="Ver categorías pendientes de mapeo"
    )
    pending_parser.add_argument("market", choices=["dia", "mercadona", "carrefour", "consum"])
    pending_parser.set_defaults(func=cmd_categories_pending)

    # categories stats
    stats_parser = cat_subparsers.add_parser(
        "stats", help="Ver estadísticas de mapeos"
    )
    stats_parser.add_argument("market", choices=["dia", "mercadona", "carrefour", "consum"])
    stats_parser.set_defaults(func=cmd_categories_stats)

    # categories map
    map_parser = cat_subparsers.add_parser(
        "map", help="Mapear categoría manualmente"
    )
    map_parser.add_argument("market", choices=["dia", "mercadona", "carrefour", "consum"])
    map_parser.add_argument("source_id", help="ID de la categoría del supermercado")
    map_parser.add_argument("master_id", help="ID de la categoría maestra")
    map_parser.set_defaults(func=cmd_categories_map)

    # categories taxonomy
    taxonomy_parser = cat_subparsers.add_parser(
        "taxonomy", help="Ver taxonomía maestra"
    )
    taxonomy_parser.set_defaults(func=cmd_categories_taxonomy)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    if args.command == "categories" and not args.cat_command:
        cat_parser.print_help()
        sys.exit(1)

    try:
        args.func(args)
    except KeyboardInterrupt:
        logger.warning("Proceso interrumpido por el usuario")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
