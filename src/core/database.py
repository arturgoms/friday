"""
Centralized Database Module

Provides a single point of access for all SQLite database operations.
Handles schema creation, migrations, and provides connection utilities.
"""

import logging
from pathlib import Path
from typing import Optional, Dict, Any, List
from contextlib import contextmanager

from sqlalchemy import create_engine, text, Engine
from sqlalchemy.pool import StaticPool

from settings import settings

logger = logging.getLogger(__name__)


class Database:
    """Centralized database manager for Friday."""
    
    def __init__(self, db_path: Optional[Path] = None, in_memory: bool = False):
        """
        Initialize database connection.
        
        Args:
            db_path: Path to SQLite database file. If None, uses settings.PATHS["data"] / "friday.db"
            in_memory: If True, creates an in-memory database (useful for testing)
        """
        if in_memory:
            self.db_path = ":memory:"
            # Use StaticPool for in-memory databases to persist across connections
            self.engine = create_engine(
                "sqlite:///:memory:",
                connect_args={"check_same_thread": False},
                poolclass=StaticPool
            )
        else:
            self.db_path = db_path or settings.PATHS["data"] / "friday.db"
            self.engine = create_engine(f"sqlite:///{str(self.db_path)}")
        
        # Initialize schema if needed
        self._initialize_schema()
    
    def _initialize_schema(self):
        """Create database tables if they don't exist."""
        try:
            with self.engine.connect() as conn:
                # Conversation history table
                conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS conversation_history (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        conversation_id TEXT NOT NULL,
                        timestamp TEXT NOT NULL,
                        role TEXT NOT NULL,
                        content TEXT NOT NULL,
                        metadata TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """))
                
                # Index for faster queries
                conn.execute(text("""
                    CREATE INDEX IF NOT EXISTS idx_conversation_history_lookup 
                    ON conversation_history(conversation_id, timestamp DESC)
                """))
                
                # Facts/knowledge table
                conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS facts (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        category TEXT NOT NULL,
                        subject TEXT NOT NULL,
                        content TEXT NOT NULL,
                        confidence REAL DEFAULT 1.0,
                        source TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        tags TEXT,
                        metadata TEXT
                    )
                """))
                
                # Index for facts
                conn.execute(text("""
                    CREATE INDEX IF NOT EXISTS idx_facts_category 
                    ON facts(category, subject)
                """))
                
                # Insights/awareness tables
                # Snapshots: Point-in-time data captures
                conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS snapshots (
                        id TEXT PRIMARY KEY,
                        collector TEXT NOT NULL,
                        timestamp TEXT NOT NULL,
                        data TEXT NOT NULL,
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP
                    )
                """))
                conn.execute(text("""
                    CREATE INDEX IF NOT EXISTS idx_snapshots_collector ON snapshots(collector)
                """))
                conn.execute(text("""
                    CREATE INDEX IF NOT EXISTS idx_snapshots_timestamp ON snapshots(timestamp)
                """))
                
                # Insights: Generated observations/alerts
                conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS insights (
                        id TEXT PRIMARY KEY,
                        type TEXT NOT NULL,
                        category TEXT NOT NULL,
                        priority TEXT NOT NULL,
                        title TEXT NOT NULL,
                        message TEXT NOT NULL,
                        confidence REAL DEFAULT 1.0,
                        data TEXT,
                        source_analyzer TEXT,
                        dedupe_key TEXT,
                        created_at TEXT NOT NULL,
                        expires_at TEXT,
                        delivered INTEGER DEFAULT 0
                    )
                """))
                conn.execute(text("""
                    CREATE INDEX IF NOT EXISTS idx_insights_created ON insights(created_at)
                """))
                conn.execute(text("""
                    CREATE INDEX IF NOT EXISTS idx_insights_dedupe ON insights(dedupe_key)
                """))
                conn.execute(text("""
                    CREATE INDEX IF NOT EXISTS idx_insights_delivered ON insights(delivered)
                """))
                
                # Deliveries: Record of sent notifications
                conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS deliveries (
                        id TEXT PRIMARY KEY,
                        insight_id TEXT NOT NULL,
                        channel TEXT NOT NULL,
                        delivered_at TEXT NOT NULL,
                        success INTEGER DEFAULT 1,
                        error TEXT
                    )
                """))
                conn.execute(text("""
                    CREATE INDEX IF NOT EXISTS idx_deliveries_insight ON deliveries(insight_id)
                """))
                conn.execute(text("""
                    CREATE INDEX IF NOT EXISTS idx_deliveries_date ON deliveries(delivered_at)
                """))
                
                # Budget: Daily reach-out tracking
                conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS reach_out_budget (
                        date TEXT PRIMARY KEY,
                        count INTEGER DEFAULT 0,
                        max_per_day INTEGER DEFAULT 5,
                        deliveries TEXT DEFAULT '[]'
                    )
                """))
                
                # Journal threads: Daily journal thread messages
                conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS journal_threads (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        date TEXT UNIQUE NOT NULL,
                        message_id INTEGER NOT NULL,
                        created_at TEXT NOT NULL
                    )
                """))
                conn.execute(text("""
                    CREATE INDEX IF NOT EXISTS idx_journal_threads_date ON journal_threads(date)
                """))
                
                # Journal entries: User journal entries from Telegram
                conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS journal_entries (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        date TEXT NOT NULL,
                        timestamp TEXT NOT NULL,
                        entry_type TEXT NOT NULL,
                        content TEXT NOT NULL,
                        thread_message_id INTEGER
                    )
                """))
                conn.execute(text("""
                    CREATE INDEX IF NOT EXISTS idx_journal_entries_date ON journal_entries(date)
                """))
                conn.execute(text("""
                    CREATE INDEX IF NOT EXISTS idx_journal_entries_timestamp ON journal_entries(timestamp)
                """))
                
                conn.commit()
                logger.info(f"Database schema initialized: {self.db_path}")
                
        except Exception as e:
            logger.error(f"Error initializing database schema: {e}")
            raise
    
    @contextmanager
    def get_connection(self):
        """
        Get a database connection context manager.
        
        Usage:
            with db.get_connection() as conn:
                result = conn.execute(text("SELECT * FROM table"))
        """
        conn = self.engine.connect()
        try:
            yield conn
        finally:
            conn.close()
    
    def execute(self, sql: str, params: Optional[Dict[str, Any]] = None) -> Any:
        """
        Execute a SQL statement and return results.
        
        Args:
            sql: SQL statement to execute
            params: Optional parameters for the query
            
        Returns:
            Query result
        """
        with self.get_connection() as conn:
            result = conn.execute(text(sql), params or {})
            return result
    
    def fetchall(self, sql: str, params: Optional[Dict[str, Any]] = None) -> List[tuple]:
        """
        Execute a query and fetch all results.
        
        Args:
            sql: SQL query to execute
            params: Optional parameters for the query
            
        Returns:
            List of result tuples
        """
        with self.get_connection() as conn:
            result = conn.execute(text(sql), params or {})
            return result.fetchall()
    
    def fetchone(self, sql: str, params: Optional[Dict[str, Any]] = None) -> Optional[tuple]:
        """
        Execute a query and fetch one result.
        
        Args:
            sql: SQL query to execute
            params: Optional parameters for the query
            
        Returns:
            Single result tuple or None
        """
        with self.get_connection() as conn:
            result = conn.execute(text(sql), params or {})
            return result.fetchone()
    
    def insert(self, table: str, data: Dict[str, Any]) -> int:
        """
        Insert a row into a table.
        
        Args:
            table: Table name
            data: Dictionary of column: value pairs
            
        Returns:
            ID of inserted row
        """
        columns = ", ".join(data.keys())
        placeholders = ", ".join(f":{key}" for key in data.keys())
        sql = f"INSERT INTO {table} ({columns}) VALUES ({placeholders})"
        
        with self.get_connection() as conn:
            result = conn.execute(text(sql), data)
            conn.commit()
            return result.lastrowid
    
    def update(self, table: str, data: Dict[str, Any], where: str, where_params: Dict[str, Any]) -> int:
        """
        Update rows in a table.
        
        Args:
            table: Table name
            data: Dictionary of column: value pairs to update
            where: WHERE clause (without the WHERE keyword)
            where_params: Parameters for the WHERE clause
            
        Returns:
            Number of rows updated
        """
        set_clause = ", ".join(f"{key} = :{key}" for key in data.keys())
        sql = f"UPDATE {table} SET {set_clause} WHERE {where}"
        
        params = {**data, **where_params}
        
        with self.get_connection() as conn:
            result = conn.execute(text(sql), params)
            conn.commit()
            return result.rowcount
    
    def delete(self, table: str, where: str, where_params: Dict[str, Any]) -> int:
        """
        Delete rows from a table.
        
        Args:
            table: Table name
            where: WHERE clause (without the WHERE keyword)
            where_params: Parameters for the WHERE clause
            
        Returns:
            Number of rows deleted
        """
        sql = f"DELETE FROM {table} WHERE {where}"
        
        with self.get_connection() as conn:
            result = conn.execute(text(sql), where_params)
            conn.commit()
            return result.rowcount
    
    def exists(self) -> bool:
        """Check if the database file exists."""
        if self.db_path == ":memory:":
            return True
        return Path(self.db_path).exists()
    
    def close(self):
        """Close the database connection."""
        self.engine.dispose()


# Global database instance (lazily initialized)
_db_instance: Optional[Database] = None


def get_db(db_path: Optional[Path] = None, in_memory: bool = False) -> Database:
    """
    Get the global database instance.
    
    Args:
        db_path: Optional custom database path
        in_memory: If True, creates in-memory database (for testing)
        
    Returns:
        Database instance
    """
    global _db_instance
    
    # For in-memory or custom path, always create new instance
    if in_memory or db_path:
        return Database(db_path=db_path, in_memory=in_memory)
    
    # Use global instance for default database
    if _db_instance is None:
        _db_instance = Database()
    
    return _db_instance


def reset_db():
    """Reset the global database instance. Useful for testing."""
    global _db_instance
    if _db_instance:
        _db_instance.close()
    _db_instance = None
