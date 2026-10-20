"""Consulta del catálogo real y sus cambios de precio, sin embeddings ni escrituras."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import HTTPException

from .db import app_conn

_CATEGORY = "COALESCE(NULLIF(btrim(split_part(p.category, '>', 1)), ''), 'Sin categoría')"
_BRAND = "COALESCE(NULLIF(btrim(p.brand), ''), 'Sin marca')"
_FIELDS = f"""p.id, p.name, p.supermarket, p.category, p.master_category_id,
    p.price, p.price_per_unit, p.unit, p.brand, p.url, p.image_url,
    p.created_at, p.last_seen, {_CATEGORY} AS category_group,
    p.source_metadata->'image_candidates' AS image_candidates,
    p.source_metadata->'price_scope' AS price_scope,
    p.source_metadata->>'price_context' AS price_context"""
# El scraper guarda baseline y cambios. Nunca interpretamos una única observación
# como una bajada; buscamos el último precio conocido distinto al precio actual.
_PREVIOUS = """LEFT JOIN LATERAL (
    SELECT ph.price FROM price_history ph
    WHERE ph.product_id = p.id AND ph.price IS NOT NULL
      AND p.price IS NOT NULL AND ph.price <> p.price
      AND (ph.source_metadata->>'price_context') IS NOT DISTINCT FROM (p.source_metadata->>'price_context')
    ORDER BY ph.changed_at DESC, ph.id DESC LIMIT 1
) previous ON true"""



def _source(province: str = ''):
    """Una fila por producto; precio y fecha del centro elegido en la provincia."""
    if not province:
        return 'products p', [], _PREVIOUS
    source = """(SELECT
        b.id,b.name,b.supermarket,b.category,b.master_category_id,b.brand,b.url,b.image_url,
        b.created_at,b.embedding,a.price,a.price_per_unit,a.unit,a.observed_at AS last_seen,
        a.zone_id AS selected_zone_id,
        b.source_metadata || jsonb_build_object(
            'price_context',a.market||':online:'||a.zone_id||':EUR',
            'price_scope',jsonb_build_object('zone_id',a.zone_id,'province',a.province,
                'label',a.label||' · observado en '||a.province)) AS source_metadata
        FROM products b JOIN (
            SELECT DISTINCT ON (a.product_id) a.*,zp.province,z.label
            FROM product_availability a
            JOIN catalogue_zone_provinces zp ON zp.market=a.market AND zp.zone_id=a.zone_id
            JOIN catalogue_zones z ON z.market=a.market AND z.zone_id=a.zone_id
            WHERE zp.province_code=%s AND a.available
            ORDER BY a.product_id,a.zone_id
        ) a ON b.id=a.product_id AND b.supermarket=a.market
    ) p"""
    previous = """LEFT JOIN LATERAL (
        SELECT ph.price FROM regional_price_history ph
        WHERE ph.product_id=p.id AND ph.market=p.supermarket AND ph.zone_id=p.selected_zone_id
          AND ph.price IS NOT NULL AND p.price IS NOT NULL AND ph.price<>p.price
        ORDER BY ph.changed_at DESC,ph.id DESC LIMIT 1
    ) previous ON true"""
    return source, [province], previous

def _numbers(row: dict) -> dict:
    for key in ('price', 'price_per_unit', 'previous_price'):
        if row.get(key) is not None:
            row[key] = float(row[key])
    old, price = row.get('previous_price'), row.get('price')
    row['change_percent'] = round((price - old) / old * 100, 2) if old and price is not None else None
    return row


def summary(user_id: str, province: str = '') -> dict:
    source, params, previous = _source(province)
    with app_conn(user_id) as conn, conn.cursor() as cur:
        cur.execute(f"""SELECT count(*) AS total,
            count(DISTINCT {_CATEGORY}) AS category_count,
            count(DISTINCT p.supermarket) AS supermarket_count,
            count(*) FILTER (WHERE p.price < previous.price) AS price_drops,
            count(*) FILTER (WHERE p.price > previous.price) AS price_rises,
            max(p.last_seen) AS last_seen
            FROM {source} {previous}""", params)
        result = dict(cur.fetchone())
        for key, expression in [('categories', _CATEGORY), ('brands', _BRAND), ('supermarkets', 'p.supermarket')]:
            cur.execute(f"SELECT {expression} AS name, count(*) AS count FROM {source} GROUP BY 1 ORDER BY 1", params)
            result[key] = cur.fetchall()
        cur.execute("""SELECT DISTINCT zp.province_code AS code,zp.province AS name
            FROM catalogue_zone_provinces zp WHERE EXISTS (
                SELECT 1 FROM product_availability a
                WHERE a.market=zp.market AND a.zone_id=zp.zone_id AND a.available)
            ORDER BY 2""")
        result['provinces'] = cur.fetchall()
        result['province'] = province or None
    return result


def list_products(user_id: str, *, q: str = '', category: str = '', brand: str = '',
                  supermarket: str = '', change: str = 'all', group_by: str = 'category',
                  sort: str = 'name', province: str = '', page: int = 1, page_size: int = 50, ids: list[str] | None = None) -> dict:
    source, params, previous = _source(province)
    clauses = []
    if ids is not None:
        clauses.append('p.id = ANY(%s)')
        params.append(ids)
    if q.strip():
        # Búsqueda textual literal: % y _ del usuario no son comodines SQL.
        literal = q.strip().replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')
        clauses.append("(p.name ILIKE %s OR COALESCE(p.brand, '') ILIKE %s OR p.id ILIKE %s)")
        params.extend([f'%{literal}%'] * 3)
    for value, expression in [(category, _CATEGORY), (brand, _BRAND), (supermarket, 'p.supermarket')]:
        if value:
            clauses.append(f'{expression} = %s')
            params.append(value)
    conditions = {'down': 'p.price < previous.price', 'up': 'p.price > previous.price',
                  'unknown': 'previous.price IS NULL'}
    if change in conditions:
        clauses.append(conditions[change])
    where = ' WHERE ' + ' AND '.join(clauses) if clauses else ''
    grouping = {'category': _CATEGORY, 'brand': _BRAND, 'supermarket': 'p.supermarket', 'none': ''}[group_by]
    ordering = {'name': 'p.name ASC', 'price_asc': 'p.price ASC NULLS LAST',
                'price_desc': 'p.price DESC NULLS LAST', 'updated': 'p.last_seen DESC',
                'drop': '(p.price - previous.price) / NULLIF(previous.price, 0) ASC NULLS LAST'}[sort]
    order = f'{grouping}, {ordering}, p.id' if grouping else f'{ordering}, p.id'
    with app_conn(user_id) as conn, conn.cursor() as cur:
        cur.execute(f'SELECT count(*) AS total FROM {source} {previous} {where}', params)
        total = cur.fetchone()['total']
        cur.execute(f"""SELECT {_FIELDS}, previous.price AS previous_price
            FROM {source} {previous} {where} ORDER BY {order} LIMIT %s OFFSET %s""",
                    [*params, page_size, (page - 1) * page_size])
        items = [_numbers(dict(row)) for row in cur.fetchall()]
    return {'items': items, 'total': total, 'page': page, 'page_size': page_size}


def get_product(user_id: str, product_id: str, province: str = '') -> dict:
    source, params, previous = _source(province)
    with app_conn(user_id) as conn, conn.cursor() as cur:
        cur.execute(f"""SELECT {_FIELDS}, previous.price AS previous_price
            FROM {source} {previous} WHERE p.id = %s""", [*params,product_id])
        row = cur.fetchone()
    if row is None:
        raise HTTPException(404, 'Producto no encontrado')
    return _numbers(dict(row))


def price_history(user_id: str, product_id: str, days: int = 90, province: str = '') -> dict:
    """Incluye el precio vigente al inicio del intervalo sin inventar observaciones.

    La línea puede extender la última observación hasta last_seen, nunca hasta hoy
    si el scraper no ha vuelto a observar el producto. Los valores nulos se
    conservan para representar los intervalos cuyo precio es desconocido.
    """
    product = get_product(user_id, product_id, province)
    now = datetime.now(timezone.utc)
    start = now - timedelta(days=days)
    if province:
        return _regional_history(user_id, product, days, start, now)
    with app_conn(user_id) as conn, conn.cursor() as cur:
        cur.execute("""(SELECT id, price, price_per_unit, changed_at FROM price_history
            WHERE product_id = %s AND changed_at < %s
              AND (source_metadata->>'price_context') IS NOT DISTINCT FROM %s
            ORDER BY changed_at DESC, id DESC LIMIT 1)
            UNION ALL
            (SELECT id, price, price_per_unit, changed_at FROM price_history
            WHERE product_id = %s AND changed_at >= %s AND changed_at <= %s
              AND (source_metadata->>'price_context') IS NOT DISTINCT FROM %s)
            ORDER BY changed_at, id""", (product_id, start, product.get('price_context'), product_id, start, now, product.get('price_context')))
        points = [dict(r) for r in cur.fetchall()]
        cur.execute("""SELECT count(*) AS count FROM price_history WHERE product_id = %s
            AND (source_metadata->>'price_context') IS NOT DISTINCT FROM %s""", (product_id, product.get('price_context')))
        observation_count = cur.fetchone()['count']
    for point in points:
        point.pop('id')
        for key in ('price', 'price_per_unit'):
            if point[key] is not None:
                point[key] = float(point[key])
    return {'product_id': product_id, 'days': days, 'start': start, 'end': now,
            'last_seen': product['last_seen'], 'observation_count': observation_count, 'points': points}


def _regional_history(user_id, product, days, start, now):
    """La provincia nunca reutiliza el precio ni el histórico de otra zona."""
    scope = product['price_scope']['zone_id']
    params = (product['id'],product['supermarket'],scope)
    with app_conn(user_id) as conn, conn.cursor() as cur:
        cur.execute("""(SELECT id,price,price_per_unit,changed_at FROM regional_price_history
            WHERE product_id=%s AND market=%s AND zone_id=%s AND changed_at<%s
            ORDER BY changed_at DESC,id DESC LIMIT 1) UNION ALL
            (SELECT id,price,price_per_unit,changed_at FROM regional_price_history
            WHERE product_id=%s AND market=%s AND zone_id=%s AND changed_at>=%s AND changed_at<=%s)
            ORDER BY changed_at,id""",(*params,start,*params,start,now))
        points = [dict(r) for r in cur.fetchall()]
        cur.execute('SELECT count(*) AS count FROM regional_price_history WHERE product_id=%s AND market=%s AND zone_id=%s',params)
        count = cur.fetchone()['count']
    for point in points:
        point.pop('id')
        for key in ('price','price_per_unit'):
            if point[key] is not None:
                point[key] = float(point[key])
    return {'product_id':product['id'],'days':days,'start':start,'end':now,
            'last_seen':product['last_seen'],'observation_count':count,'points':points}
