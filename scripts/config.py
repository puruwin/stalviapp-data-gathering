"""
Configuración de la base de datos usando variables de entorno.
"""
import os
from dotenv import load_dotenv

# Cargar variables de entorno desde .env
load_dotenv()


def get_db_config():
    """
    Obtiene la configuración de la base de datos desde variables de entorno.
    
    Returns:
        dict: Diccionario con los parámetros de conexión a PostgreSQL
    """
    return {
        'host': os.getenv('DB_HOST', 'localhost'),
        'port': os.getenv('DB_PORT', '5432'),
        'database': os.getenv('DB_NAME', 'stalviapp'),
        'user': os.getenv('DB_USER', 'postgres'),
        'password': os.getenv('DB_PASSWORD', '')
    }

