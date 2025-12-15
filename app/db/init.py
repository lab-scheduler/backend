"""
Database initialization module.
Import this module to ensure all models are loaded before creating tables.
"""

from app.db.session import create_db_and_tables

# Initialize database on import
create_db_and_tables()