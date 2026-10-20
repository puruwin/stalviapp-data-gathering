#!/usr/bin/env python3
"""
CLI para ejecutar los scrapers de supermercados.

Uso:
    python main.py scrape mercadona                 # Scrape completo de Mercadona
    python main.py scrape mercadona --test          # Modo test (límites)
    python main.py scrape mercadona --dry-run       # Sin persistir (solo scrapear)

    python main.py categories pending mercadona     # Ver categorías pendientes
    python main.py categories stats mercadona       # Ver estadísticas de mapeos
    python main.py categories map mercadona ID MASTER_ID  # Mapear manualmente
"""

from __future__ import annotations

import argparse
import logging
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from scrapers import NormalizedProduct
from scrapers.categories import CategoryMapper, MasterTaxonomy
from scrapers.categories.taxonomy import get_taxonomy
from scrapers.mercadona import MercadonaScraper
from scrapers.consum import ConsumScraper
from scrapers.validators import validate_products

# Configuración de logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


def get_scraper(market: str, max_products=None):
    """Obtiene el scraper para un supermercado."""
    scrapers = {
        "mercadona": MercadonaScraper,
        "consum": ConsumScraper,
    }

    if market not in scrapers:
        raise ValueError(f"Supermercado no soportado: {market}")

    if market == "consum":
        return ConsumScraper(max_products_per_category=max_products)
    return scrapers[market]()


def run_scraper(
    market: str,
    max_categories: Optional[int] = None,
    max_products: Optional[int] = None,
    dry_run: bool = False,
    verbose: bool = False,
    category_ids=None,
    output=None,
    report=None,
) -> List[NormalizedProduct]:
    """
    Ejecuta el scraper para un supermercado.

    Args:
        market: Nombre del supermercado (dia, mercadona, etc.)
        max_categories: Límite de categorías (para testing).
        max_products: Límite de productos por categoría.
        dry_run: Si True, no persiste en Postgres ni guarda mapeos.
        verbose: Si True, muestra más información.

    Returns:
        Lista de productos scrapeados.
    """
    if verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    inicio = datetime.now()
    logger.info(f"Iniciando scraper de {market.upper()}...")

    # Obtener scraper
    scraper = get_scraper(market, max_products=max_products)

    # Obtener categorías
    categories = scraper.get_categories()
    if not categories:
        raise RuntimeError("No se encontraron categorías")

    if category_ids:
        unknown = set(category_ids) - {c.id for c in categories}
        if unknown:
            raise ValueError(f"Categorías hoja desconocidas: {', '.join(sorted(unknown))}")
        categories = [c for c in categories if c.id in category_ids]

    if max_categories:
        categories = categories[:max_categories]
        logger.info(f"Limitado a {max_categories} categorías (modo test)")

    # Scrapear productos
    all_products: List[NormalizedProduct] = []
    processed = 0
    failed = 0
    category_results = []

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
            category_results.append({"id": category.id, "name": str(category), "status": "ok", "products": len(products)})

        except Exception as e:
            failed += 1
            logger.error(f"  -> Error: {e}")
            category_results.append({"id": category.id, "name": str(category), "status": "failed", "error": str(e)})

        scraper.http.delay()

    # Guardar mapeos de categorías
    if not dry_run and not failed:
        scraper.save_category_mappings()

    # Estadísticas de mapeos
    mapper_stats = scraper.category_mapper.get_stats()

    # Validar productos
    valid_products = list({p.id: p for p in validate_products(all_products)}.values())

    def write_json(path, data):
        if path:
            destination = Path(path)
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    summary = {
        "market": market, "started_at": inicio.astimezone().isoformat(),
        "finished_at": datetime.now().astimezone().isoformat(),
        "dry_run": dry_run, "limited": bool(max_categories or max_products or category_ids),
        "price_context": getattr(scraper, "PRICE_CONTEXT", None),
        "processed_categories": processed, "failed_categories": failed,
        "unique_products": len(valid_products), "categories": category_results,
        "status": "failed" if failed else "ok", "persistence": "not_started",
    }
    write_json(output, [p.to_dict() for p in valid_products])
    write_json(report, summary)
    if market == "consum" and failed:
        raise RuntimeError(f"Consum: {failed} categorías fallidas; no se persiste una ejecución incompleta. Ver informe.")

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

    # Persistencia
    if dry_run:
        logger.info("Modo dry-run: no se persisten los productos")
        summary["persistence"] = "skipped"
    else:
        import db

        logger.info(f"Persistiendo {len(valid_products)} productos en Postgres...")
        cat_rows = [
            {
                "market": market,
                "external_id": c.id,
                "name": c.name,
                "parent_name": c.parent_name,
                "master_category_id": scraper.category_mapper.get_master_category(c, auto_map=market != "consum"),
            }
            for c in categories
        ]
        try:
            db.upsert_categories(cat_rows)
            pstats = db.upsert_products(valid_products)
        except Exception as error:
            summary.update(status="failed", persistence="failed", error=str(error))
            write_json(report, summary)
            raise
        summary["persistence"] = pstats
        logger.info(
            "Persistencia: nuevos=%d, precio_cambiado=%d, sin_cambios=%d",
            pstats["new"],
            pstats["price_changed"],
            pstats["unchanged"],
        )
        if pstats.get("context_changed"):
            logger.info("Nuevos baselines por cambio de zona: %d", pstats["context_changed"])

    write_json(report, summary)
    return valid_products


def cmd_scrape(args):
    """Comando: scrape"""
    if args.all_zones:
        if not args.checkpoint_dir:
            raise ValueError('--all-zones requiere --checkpoint-dir para poder reanudar')
        if args.test or args.categories or args.products or args.category_ids:
            raise ValueError('--all-zones no admite límites de categorías o productos')
        root = Path(args.checkpoint_dir).resolve()
        root.mkdir(parents=True, exist_ok=True)
        if args.market == 'mercadona':
            from mercadona_catalogue import collect
            from regional_catalogue import import_mercadona
            summary = collect(root, args.workers)
            summary['persistence'] = 'skipped' if args.dry_run else import_mercadona(root)
        elif args.market == 'consum':
            from consum_catalogue import collect, prepare, audit_images, import_products
            from regional_catalogue import import_consum
            collect(root, args.workers)
            summary = prepare(root)
            summary['images'] = audit_images(root, args.workers)
            summary['persistence'] = 'skipped' if args.dry_run else import_products(root)
            if not args.dry_run:
                summary['availability'] = import_consum(root)
        else:
            raise ValueError('--all-zones solo admite Mercadona y Consum')
        if args.report:
            Path(args.report).parent.mkdir(parents=True, exist_ok=True)
            Path(args.report).write_text(json.dumps(summary, ensure_ascii=False, indent=2))
        if args.output:
            Path(args.output).parent.mkdir(parents=True, exist_ok=True)
            Path(args.output).write_bytes((root/'products.json').read_bytes())
        logger.info('%s unificado: %d productos', args.market, summary['unique_products'])
        return
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
        category_ids=args.category_ids,
        output=args.output,
        report=args.report,
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
    def positive_int(value):
        number = int(value)
        if number <= 0:
            raise argparse.ArgumentTypeError("El límite debe ser mayor que cero")
        return number

    parser = argparse.ArgumentParser(
        description="Scraper de supermercados",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    subparsers = parser.add_subparsers(dest="command", help="Comandos disponibles")

    # Comando: scrape
    scrape_parser = subparsers.add_parser("scrape", help="Ejecutar scraper")
    scrape_parser.add_argument(
        "market",
        choices=["mercadona", "consum"],
        help="Supermercado a scrapear",
    )
    scrape_parser.add_argument(
        "--test",
        action="store_true",
        help="Modo test: limita a 5 categorías y 3 productos",
    )
    scrape_parser.add_argument(
        "--categories",
        type=positive_int,
        metavar="N",
        help="Límite de categorías a procesar",
    )
    scrape_parser.add_argument(
        "--products",
        type=positive_int,
        metavar="N",
        help="Límite de productos por categoría",
    )
    scrape_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="No persistir (solo scrapear)",
    )
    scrape_parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Mostrar información detallada",
    )
    scrape_parser.set_defaults(func=cmd_scrape)
    scrape_parser.add_argument("--category-id", dest="category_ids", action="append", help="ID de categoría hoja (repetible)")
    scrape_parser.add_argument("--output", help="Guardar productos normalizados como JSON")
    scrape_parser.add_argument("--report", help="Guardar métricas y errores de ejecución como JSON")
    scrape_parser.add_argument("--all-zones", action="store_true", help="Unificar los catálogos regionales de Mercadona o Consum")
    scrape_parser.add_argument("--checkpoint-dir", help="Directorio propio de esta observación para reanudar sin repetir descargas")
    scrape_parser.add_argument("--workers", type=int, choices=range(1, 5), default=4, help="Conexiones máximas del recorrido por zonas (1–4)")

    # Comando: categories
    cat_parser = subparsers.add_parser("categories", help="Gestión de categorías")
    cat_subparsers = cat_parser.add_subparsers(dest="cat_command")

    # categories pending
    pending_parser = cat_subparsers.add_parser(
        "pending", help="Ver categorías pendientes de mapeo"
    )
    pending_parser.add_argument("market", choices=["mercadona", "consum"])
    pending_parser.set_defaults(func=cmd_categories_pending)

    # categories stats
    stats_parser = cat_subparsers.add_parser(
        "stats", help="Ver estadísticas de mapeos"
    )
    stats_parser.add_argument("market", choices=["mercadona", "consum"])
    stats_parser.set_defaults(func=cmd_categories_stats)

    # categories map
    map_parser = cat_subparsers.add_parser(
        "map", help="Mapear categoría manualmente"
    )
    map_parser.add_argument("market", choices=["mercadona", "consum"])
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
