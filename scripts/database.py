"""
Módulo para manejar operaciones de base de datos PostgreSQL.
"""
import os
import psycopg2
from psycopg2.extras import RealDictCursor
from psycopg2 import sql
from datetime import datetime
from config import get_db_config

# Variable global para la conexión
_connection = None


def get_connection():
    """
    Obtiene una conexión a la base de datos PostgreSQL.
    Si ya existe una conexión activa, la reutiliza.
    
    Returns:
        psycopg2.connection: Conexión a la base de datos
    
    Raises:
        psycopg2.OperationalError: Si no se puede conectar a la base de datos
    """
    global _connection
    
    if _connection is None or _connection.closed:
        config = get_db_config()
        try:
            _connection = psycopg2.connect(**config)
            print("✓ Conexión a la base de datos establecida")
        except psycopg2.OperationalError as e:
            print(f"✗ Error al conectar a la base de datos: {e}")
            print("\n⚠ Verifica que:")
            print("  1. PostgreSQL esté instalado y ejecutándose")
            print("  2. La base de datos exista (CREATE DATABASE stalviapp;)")
            print("  3. El archivo .env esté configurado correctamente")
            print("  4. Las credenciales en .env sean correctas")
            raise
        except psycopg2.Error as e:
            print(f"✗ Error de base de datos: {e}")
            raise
    
    return _connection


def close_connection():
    """
    Cierra la conexión a la base de datos.
    """
    global _connection
    
    if _connection and not _connection.closed:
        _connection.close()
        _connection = None
        print("✓ Conexión a la base de datos cerrada")


def init_database():
    """
    Inicializa la base de datos ejecutando el script de esquema.
    Lee el archivo database_schema.sql y ejecuta las sentencias SQL.
    """
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Leer el archivo de esquema
        schema_path = os.path.join(os.path.dirname(__file__), 'database_schema.sql')
        with open(schema_path, 'r', encoding='utf-8') as f:
            schema_sql = f.read()
        
        # Ejecutar el esquema
        cursor.execute(schema_sql)
        conn.commit()
        cursor.close()
        
        print("✓ Base de datos inicializada correctamente")
        return True
        
    except FileNotFoundError:
        print(f"✗ No se encontró el archivo database_schema.sql")
        return False
    except psycopg2.Error as e:
        print(f"✗ Error al inicializar la base de datos: {e}")
        if conn:
            conn.rollback()
        return False
    except Exception as e:
        print(f"✗ Error inesperado al inicializar la base de datos: {e}")
        if conn:
            conn.rollback()
        return False


def insert_or_update_category(
    external_id,
    name,
    link=None,
    parent_category=None,
    market="unknown",
    master_category_id=None,
):
    """
    Inserta o actualiza una categoría en la base de datos.
    
    Args:
        external_id (str): ID externo de la categoría (de la API)
        name (str): Nombre de la categoría
        link (str, optional): Link de la categoría
        parent_category (str, optional): Nombre de la categoría padre
    
    Returns:
        int: ID de la categoría insertada o actualizada, None si hay error
    """
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Intentar insertar o actualizar usando ON CONFLICT
        query = """
            INSERT INTO categories (external_id, market, name, link, parent_category, master_category_id)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (market, external_id) 
            DO UPDATE SET 
                name = EXCLUDED.name,
                link = EXCLUDED.link,
                parent_category = EXCLUDED.parent_category,
                master_category_id = COALESCE(EXCLUDED.master_category_id, categories.master_category_id)
            RETURNING id
        """
        
        cursor.execute(
            query,
            (
                external_id,
                market,
                name,
                link,
                parent_category,
                master_category_id,
            ),
        )
        category_id = cursor.fetchone()[0]
        conn.commit()
        cursor.close()
        
        return category_id
        
    except psycopg2.Error as e:
        print(f"✗ Error al insertar/actualizar categoría: {e}")
        if conn:
            conn.rollback()
        return None
    except Exception as e:
        print(f"✗ Error inesperado al insertar/actualizar categoría: {e}")
        if conn:
            conn.rollback()
        return None


def insert_or_update_product(display_name, price, price_per_unit, measure_unit, 
                             category_id, brand=None):
    """
    Inserta o actualiza un producto en la base de datos.
    Si el producto ya existe, actualiza el precio y registra el cambio en el historial.
    Si es nuevo, lo inserta y crea el primer registro en el historial.
    
    Args:
        display_name (str): Nombre del producto
        price (float): Precio actual
        price_per_unit (float): Precio por unidad
        measure_unit (str): Unidad de medida
        category_id (int): ID de la categoría
        brand (str, optional): Marca del producto
    
    Returns:
        int: ID del producto insertado o actualizado, None si hay error
    """
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Verificar si el producto ya existe
        check_query = """
            SELECT id, current_price, current_price_per_unit
            FROM products
            WHERE display_name = %s 
            AND (brand = %s OR (brand IS NULL AND %s IS NULL))
            AND category_id = %s
        """
        
        cursor.execute(check_query, (display_name, brand, brand, category_id))
        existing = cursor.fetchone()
        
        now = datetime.now()
        
        if existing:
            # Producto existe - actualizar
            product_id, old_price, old_price_per_unit = existing
            
            # Solo actualizar historial si el precio cambió
            if old_price != price or old_price_per_unit != price_per_unit:
                # Insertar en historial
                history_query = """
                    INSERT INTO price_history (product_id, price, price_per_unit, recorded_at)
                    VALUES (%s, %s, %s, %s)
                """
                cursor.execute(history_query, (product_id, price, price_per_unit, now))
            
            # Actualizar producto
            update_query = """
                UPDATE products
                SET current_price = %s,
                    current_price_per_unit = %s,
                    measure_unit = %s,
                    last_updated = %s
                WHERE id = %s
            """
            cursor.execute(update_query, (price, price_per_unit, measure_unit, now, product_id))
            
        else:
            # Producto nuevo - insertar
            insert_query = """
                INSERT INTO products (display_name, brand, category_id, current_price, 
                                    current_price_per_unit, measure_unit, first_seen, last_updated)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            """
            cursor.execute(insert_query, (display_name, brand, category_id, price, 
                                        price_per_unit, measure_unit, now, now))
            product_id = cursor.fetchone()[0]
            
            # Insertar primer registro en historial
            history_query = """
                INSERT INTO price_history (product_id, price, price_per_unit, recorded_at)
                VALUES (%s, %s, %s, %s)
            """
            cursor.execute(history_query, (product_id, price, price_per_unit, now))
        
        conn.commit()
        cursor.close()
        
        return product_id
        
    except psycopg2.Error as e:
        print(f"✗ Error al insertar/actualizar producto: {e}")
        if conn:
            conn.rollback()
        return None
    except Exception as e:
        print(f"✗ Error inesperado al insertar/actualizar producto: {e}")
        if conn:
            conn.rollback()
        return None


def upsert_master_category(code, name, parent_code=None, level=0, needs_review=False):
    """
    Inserta o actualiza una categoría maestra.
    """
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()

        parent_id = None
        if parent_code:
            cursor.execute(
                "SELECT id FROM master_categories WHERE code = %s",
                (parent_code,),
            )
            parent_row = cursor.fetchone()
            if parent_row:
                parent_id = parent_row[0]

        query = """
            INSERT INTO master_categories (code, name, parent_id, level, needs_review)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (code)
            DO UPDATE SET
                name = EXCLUDED.name,
                parent_id = EXCLUDED.parent_id,
                level = EXCLUDED.level,
                needs_review = EXCLUDED.needs_review
            RETURNING id
        """
        cursor.execute(query, (code, name, parent_id, level, needs_review))
        master_id = cursor.fetchone()[0]
        conn.commit()
        cursor.close()
        return master_id
    except psycopg2.Error as e:
        print(f"✗ Error al insertar/actualizar categoría maestra: {e}")
        if conn:
            conn.rollback()
        return None


def get_master_category_by_code(code):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id FROM master_categories WHERE code = %s",
        (code,),
    )
    row = cursor.fetchone()
    cursor.close()
    if row:
        return row[0]
    return None


def get_market_category_mapping(market, external_id):
    conn = get_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    query = """
        SELECT *
        FROM market_category_mappings
        WHERE market = %s AND external_id = %s
    """
    cursor.execute(query, (market, external_id))
    row = cursor.fetchone()
    cursor.close()
    return row


def ensure_market_category_mapping(
    market,
    external_id,
    external_name=None,
    external_parent=None,
    master_category_id=None,
    status="pending",
    confidence=None,
    notes=None,
):
    """
    Obtiene el mapping de categoría para un mercado y external_id.
    Si no existe, lo crea con los datos proporcionados.
    Devuelve el registro (dict).
    """
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        existing = get_market_category_mapping(market, external_id)
        if existing:
            cursor.close()
            return existing

        insert_query = """
            INSERT INTO market_category_mappings (
                market, external_id, external_name, external_parent,
                master_category_id, status, confidence, notes
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING *
        """
        cursor.execute(
            insert_query,
            (
                market,
                external_id,
                external_name,
                external_parent,
                master_category_id,
                status,
                confidence,
                notes,
            ),
        )
        row = cursor.fetchone()
        conn.commit()
        cursor.close()
        return row
    except psycopg2.Error as e:
        print(f"✗ Error al asegurar mapping de categoría: {e}")
        if conn:
            conn.rollback()
        return None


def update_market_category_mapping_master(
    market,
    external_id,
    master_category_id,
    status="confirmed",
    confidence=None,
    notes=None,
):
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        update_query = """
            UPDATE market_category_mappings
            SET master_category_id = %s,
                status = %s,
                confidence = COALESCE(%s, confidence),
                notes = COALESCE(%s, notes),
                last_reviewed = NOW()
            WHERE market = %s AND external_id = %s
        """
        cursor.execute(
            update_query,
            (
                master_category_id,
                status,
                confidence,
                notes,
                market,
                external_id,
            ),
        )
        conn.commit()
        cursor.close()
        return True
    except psycopg2.Error as e:
        print(f"✗ Error al actualizar mapping de categoría: {e}")
        if conn:
            conn.rollback()
        return False


def set_category_master_reference(category_id, master_category_id):
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE categories
            SET master_category_id = %s
            WHERE id = %s
            """,
            (master_category_id, category_id),
        )
        conn.commit()
        cursor.close()
        return True
    except psycopg2.Error as e:
        print(f"✗ Error al vincular categoría con master: {e}")
        if conn:
            conn.rollback()
        return False
