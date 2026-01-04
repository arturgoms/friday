"""
Friday Insights Engine - Data Store

SQLite-based storage for snapshots, insights, and deliveries.
Provides historical data for correlation analysis.
"""

import json
import logging
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List, Optional, Dict, Any

from src.insights.models import (
    Insight, Snapshot, Delivery, ReachOutBudget,
    InsightType, Priority, Category, DeliveryChannel)

from src.core.config import get_brt

logger = logging.getLogger(__name__)


class InsightsStore:
    """
    SQLite storage for the insights engine.
    
    Stores:
    - Snapshots: Historical data from collectors
    - Insights: Generated insights from analyzers
    - Deliveries: Record of what was sent when
    - Budget: Daily reach-out tracking
    """
    
    def __init__(self, db_path: Optional[Path] = None):
        """Initialize the store.
        
        Args:
            db_path: Path to SQLite database. Defaults to data/insights.db
        """
        if db_path is None:
            db_path = Path(__file__).parent.parent.parent / "data" / "insights.db"
        
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        self._init_db()
    
    def _get_conn(self) -> sqlite3.Connection:
        """Get a database connection."""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn
    
    def _init_db(self):
        """Initialize database schema."""
        conn = self._get_conn()
        try:
            conn.executescript("""
                -- Snapshots: Point-in-time data captures
                CREATE TABLE IF NOT EXISTS snapshots (
                    id TEXT PRIMARY KEY,
                    collector TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    data TEXT NOT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                );
                CREATE INDEX IF NOT EXISTS idx_snapshots_collector ON snapshots(collector);
                CREATE INDEX IF NOT EXISTS idx_snapshots_timestamp ON snapshots(timestamp);
                
                -- Insights: Generated observations/alerts
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
                );
                CREATE INDEX IF NOT EXISTS idx_insights_created ON insights(created_at);
                CREATE INDEX IF NOT EXISTS idx_insights_dedupe ON insights(dedupe_key);
                CREATE INDEX IF NOT EXISTS idx_insights_delivered ON insights(delivered);
                
                -- Deliveries: Record of sent notifications
                CREATE TABLE IF NOT EXISTS deliveries (
                    id TEXT PRIMARY KEY,
                    insight_id TEXT NOT NULL,
                    channel TEXT NOT NULL,
                    delivered_at TEXT NOT NULL,
                    success INTEGER DEFAULT 1,
                    error TEXT,
                    FOREIGN KEY (insight_id) REFERENCES insights(id)
                );
                CREATE INDEX IF NOT EXISTS idx_deliveries_insight ON deliveries(insight_id);
                CREATE INDEX IF NOT EXISTS idx_deliveries_date ON deliveries(delivered_at);
                
                -- Budget: Daily reach-out tracking
                CREATE TABLE IF NOT EXISTS reach_out_budget (
                    date TEXT PRIMARY KEY,
                    count INTEGER DEFAULT 0,
                    max_per_day INTEGER DEFAULT 5,
                    deliveries TEXT DEFAULT '[]'
                );
                
                -- Journal threads: Daily journal thread messages
                CREATE TABLE IF NOT EXISTS journal_threads (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date TEXT UNIQUE NOT NULL,
                    message_id INTEGER NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_journal_threads_date ON journal_threads(date);
                
                -- Journal entries: User journal entries from Telegram
                CREATE TABLE IF NOT EXISTS journal_entries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    entry_type TEXT NOT NULL,
                    content TEXT NOT NULL,
                    thread_message_id INTEGER,
                    FOREIGN KEY (thread_message_id) REFERENCES journal_threads(message_id)
                );
                CREATE INDEX IF NOT EXISTS idx_journal_entries_date ON journal_entries(date);
                CREATE INDEX IF NOT EXISTS idx_journal_entries_timestamp ON journal_entries(timestamp);
            """)
            conn.commit()
            logger.info(f"Insights database initialized at {self.db_path}")
        finally:
            conn.close()
    
    # =========================================================================
    # Snapshot Operations
    # =========================================================================
    
    def save_snapshot(self, snapshot: Snapshot):
        """Save a snapshot to the database."""
        conn = self._get_conn()
        try:
            conn.execute(
                """INSERT INTO snapshots (id, collector, timestamp, data)
                   VALUES (?, ?, ?, ?)""",
                (snapshot.id, snapshot.collector, 
                 snapshot.timestamp.isoformat(), json.dumps(snapshot.data))
            )
            conn.commit()
        finally:
            conn.close()
    
    def get_snapshots(
        self, 
        collector: str, 
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
        hours: Optional[int] = None,
        limit: int = 100
    ) -> List[Snapshot]:
        """Get snapshots for a collector within a time range.
        
        Args:
            collector: Collector name to filter by
            since: Start time (inclusive)
            until: End time (inclusive)
            hours: Alternative to 'since' - get snapshots from last N hours
            limit: Maximum number of snapshots to return
            
        Returns:
            List of Snapshot objects, newest first
        """
        # Convert hours to since if provided
        if hours is not None and since is None:
            since = datetime.now(get_brt()) - timedelta(hours=hours)
        
        conn = self._get_conn()
        try:
            query = "SELECT * FROM snapshots WHERE collector = ?"
            params: List[Any] = [collector]
            
            if since:
                query += " AND timestamp >= ?"
                params.append(since.isoformat())
            if until:
                query += " AND timestamp <= ?"
                params.append(until.isoformat())
            
            query += " ORDER BY timestamp DESC LIMIT ?"
            params.append(limit)
            
            rows = conn.execute(query, params).fetchall()
            return [
                Snapshot(
                    id=row["id"],
                    collector=row["collector"],
                    timestamp=datetime.fromisoformat(row["timestamp"]),
                    data=json.loads(row["data"])
                )
                for row in rows
            ]
        finally:
            conn.close()
    
    def get_latest_snapshot(self, collector: str) -> Optional[Snapshot]:
        """Get the most recent snapshot for a collector."""
        snapshots = self.get_snapshots(collector, limit=1)
        return snapshots[0] if snapshots else None
    
    def cleanup_old_snapshots(self, retention_days: int = 90):
        """Delete snapshots older than retention period."""
        cutoff = datetime.now(get_brt()) - timedelta(days=retention_days)
        conn = self._get_conn()
        try:
            result = conn.execute(
                "DELETE FROM snapshots WHERE timestamp < ?",
                (cutoff.isoformat(),)
            )
            conn.commit()
            if result.rowcount > 0:
                logger.info(f"[STORE] Cleaned up {result.rowcount} old snapshots (retention={retention_days} days)")
        finally:
            conn.close()
    
    # =========================================================================
    # Insight Operations
    # =========================================================================
    
    def save_insight(self, insight: Insight):
        """Save an insight to the database."""
        conn = self._get_conn()
        try:
            conn.execute(
                """INSERT INTO insights 
                   (id, type, category, priority, title, message, confidence,
                    data, source_analyzer, dedupe_key, created_at, expires_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (insight.id, insight.type.value, insight.category.value,
                 insight.priority.value, insight.title, insight.message,
                 insight.confidence, json.dumps(insight.data),
                 insight.source_analyzer, insight.dedupe_key,
                 insight.created_at.isoformat(),
                 insight.expires_at.isoformat() if insight.expires_at else None)
            )
            conn.commit()
        finally:
            conn.close()
    
    def get_pending_insights(self, priority: Optional[Priority] = None) -> List[Insight]:
        """Get insights that haven't been delivered yet."""
        conn = self._get_conn()
        try:
            query = "SELECT * FROM insights WHERE delivered = 0"
            params: List[Any] = []
            
            if priority:
                query += " AND priority = ?"
                params.append(priority.value)
            
            query += " ORDER BY created_at DESC"
            
            rows = conn.execute(query, params).fetchall()
            return [self._row_to_insight(row) for row in rows]
        finally:
            conn.close()
    
    def get_recent_insights(
        self, 
        hours: int = 24,
        category: Optional[Category] = None
    ) -> List[Insight]:
        """Get insights from the last N hours."""
        since = datetime.now(get_brt()) - timedelta(hours=hours)
        conn = self._get_conn()
        try:
            query = "SELECT * FROM insights WHERE created_at >= ?"
            params: List[Any] = [since.isoformat()]
            
            if category:
                query += " AND category = ?"
                params.append(category.value)
            
            query += " ORDER BY created_at DESC"
            
            rows = conn.execute(query, params).fetchall()
            return [self._row_to_insight(row) for row in rows]
        finally:
            conn.close()
    
    def check_duplicate(self, dedupe_key: str, hours: int = 4) -> bool:
        """Check if a similar insight was recently created."""
        since = datetime.now(get_brt()) - timedelta(hours=hours)
        conn = self._get_conn()
        try:
            row = conn.execute(
                """SELECT COUNT(*) as cnt FROM insights 
                   WHERE dedupe_key = ? AND created_at >= ?""",
                (dedupe_key, since.isoformat())
            ).fetchone()
            return row["cnt"] > 0
        finally:
            conn.close()
    
    def mark_delivered(self, insight_id: str):
        """Mark an insight as delivered."""
        conn = self._get_conn()
        try:
            conn.execute(
                "UPDATE insights SET delivered = 1 WHERE id = ?",
                (insight_id,)
            )
            conn.commit()
        finally:
            conn.close()
    
    def _row_to_insight(self, row: sqlite3.Row) -> Insight:
        """Convert a database row to an Insight object."""
        return Insight(
            id=row["id"],
            type=InsightType(row["type"]),
            category=Category(row["category"]),
            priority=Priority(row["priority"]),
            title=row["title"],
            message=row["message"],
            confidence=row["confidence"],
            data=json.loads(row["data"]) if row["data"] else {},
            source_analyzer=row["source_analyzer"] or "",
            dedupe_key=row["dedupe_key"],
            created_at=datetime.fromisoformat(row["created_at"]),
            expires_at=datetime.fromisoformat(row["expires_at"]) if row["expires_at"] else None
        )
    
    # =========================================================================
    # Delivery Operations
    # =========================================================================
    
    def save_delivery(self, delivery: Delivery):
        """Record a delivery."""
        conn = self._get_conn()
        try:
            conn.execute(
                """INSERT INTO deliveries 
                   (id, insight_id, channel, delivered_at, success, error)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (delivery.id, delivery.insight_id, delivery.channel.value,
                 delivery.delivered_at.isoformat(), int(delivery.success),
                 delivery.error)
            )
            conn.commit()
        finally:
            conn.close()
    
    def get_deliveries_today(self) -> List[Delivery]:
        """Get all deliveries from today."""
        today = datetime.now(get_brt()).strftime("%Y-%m-%d")
        conn = self._get_conn()
        try:
            rows = conn.execute(
                """SELECT * FROM deliveries 
                   WHERE delivered_at LIKE ? || '%'
                   ORDER BY delivered_at DESC""",
                (today,)
            ).fetchall()
            return [
                Delivery(
                    id=row["id"],
                    insight_id=row["insight_id"],
                    channel=DeliveryChannel(row["channel"]),
                    delivered_at=datetime.fromisoformat(row["delivered_at"]),
                    success=bool(row["success"]),
                    error=row["error"]
                )
                for row in rows
            ]
        finally:
            conn.close()
    
    # =========================================================================
    # Budget Operations
    # =========================================================================
    
    def get_today_budget(self, max_per_day: int = 5) -> ReachOutBudget:
        """Get or create today's reach-out budget."""
        today = datetime.now(get_brt()).strftime("%Y-%m-%d")
        conn = self._get_conn()
        try:
            row = conn.execute(
                "SELECT * FROM reach_out_budget WHERE date = ?",
                (today,)
            ).fetchone()
            
            if row:
                return ReachOutBudget(
                    date=row["date"],
                    count=row["count"],
                    max_per_day=row["max_per_day"],
                    deliveries=json.loads(row["deliveries"])
                )
            else:
                # Create new budget for today
                budget = ReachOutBudget(date=today, max_per_day=max_per_day)
                conn.execute(
                    """INSERT INTO reach_out_budget (date, count, max_per_day, deliveries)
                       VALUES (?, ?, ?, ?)""",
                    (budget.date, budget.count, budget.max_per_day, 
                     json.dumps(budget.deliveries))
                )
                conn.commit()
                return budget
        finally:
            conn.close()
    
    def increment_budget(self, insight_id: str):
        """Increment today's reach-out count."""
        today = datetime.now(get_brt()).strftime("%Y-%m-%d")
        conn = self._get_conn()
        try:
            # Get current deliveries
            row = conn.execute(
                "SELECT deliveries FROM reach_out_budget WHERE date = ?",
                (today,)
            ).fetchone()
            
            deliveries = json.loads(row["deliveries"]) if row else []
            deliveries.append(insight_id)
            
            conn.execute(
                """UPDATE reach_out_budget 
                   SET count = count + 1, deliveries = ?
                   WHERE date = ?""",
                (json.dumps(deliveries), today)
            )
            conn.commit()
        finally:
            conn.close()
    
    # =========================================================================
    # Journal Operations
    # =========================================================================
    
    def save_journal_thread(self, date: str, message_id: int) -> bool:
        """Save a journal thread message ID for a date.
        
        Args:
            date: Date in YYYY-MM-DD format
            message_id: Telegram message ID
            
        Returns:
            True if saved, False if already exists
        """
        conn = self._get_conn()
        try:
            conn.execute(
                """INSERT INTO journal_threads (date, message_id, created_at)
                   VALUES (?, ?, ?)""",
                (date, message_id, datetime.now(get_brt()).isoformat())
            )
            conn.commit()
            return True
        except sqlite3.IntegrityError:
            # Date already has a thread
            return False
        finally:
            conn.close()
    
    def get_journal_thread(self, date: str) -> Optional[int]:
        """Get the thread message ID for a date.
        
        Args:
            date: Date in YYYY-MM-DD format
            
        Returns:
            Message ID or None if not found
        """
        conn = self._get_conn()
        try:
            row = conn.execute(
                "SELECT message_id FROM journal_threads WHERE date = ?",
                (date,)
            ).fetchone()
            return row["message_id"] if row else None
        finally:
            conn.close()
    
    def save_journal_entry(
        self, 
        date: str, 
        timestamp: datetime,
        entry_type: str,
        content: str,
        thread_message_id: Optional[int] = None
    ):
        """Save a journal entry.
        
        Args:
            date: Date in YYYY-MM-DD format
            timestamp: When the entry was created
            entry_type: 'text' or 'voice'
            content: Entry content or transcription
            thread_message_id: Optional reference to the thread message
        """
        conn = self._get_conn()
        try:
            conn.execute(
                """INSERT INTO journal_entries 
                   (date, timestamp, entry_type, content, thread_message_id)
                   VALUES (?, ?, ?, ?, ?)""",
                (date, timestamp.isoformat(), entry_type, content, thread_message_id)
            )
            conn.commit()
        finally:
            conn.close()
    
    def get_journal_entries(self, date: str) -> List[Dict[str, Any]]:
        """Get all journal entries for a date.
        
        Args:
            date: Date in YYYY-MM-DD format
            
        Returns:
            List of journal entry dicts
        """
        conn = self._get_conn()
        try:
            rows = conn.execute(
                """SELECT * FROM journal_entries 
                   WHERE date = ? 
                   ORDER BY timestamp ASC""",
                (date,)
            ).fetchall()
            return [
                {
                    "id": row["id"],
                    "date": row["date"],
                    "timestamp": datetime.fromisoformat(row["timestamp"]),
                    "entry_type": row["entry_type"],
                    "content": row["content"],
                    "thread_message_id": row["thread_message_id"]
                }
                for row in rows
            ]
        finally:
            conn.close()
