"""
Friday Insights Engine - Data Store

SQLite-based storage for snapshots, insights, and deliveries.
Provides historical data for correlation analysis.
"""

import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List, Optional, Dict, Any

from src.awareness.models import (
    Insight, Snapshot, Delivery, ReachOutBudget,
    InsightType, Priority, Category, DeliveryChannel)
from src.core.database import get_db, Database

from settings import settings
def get_brt():
    return settings.TIMEZONE

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
    
    def __init__(self, db: Optional[Database] = None):
        """Initialize the store.
        
        Args:
            db: Database instance. If None, uses centralized database via get_db().
        """
        if db is None:
            self.db = get_db()
        else:
            self.db = db
        
        logger.info(f"InsightsStore initialized with database: {self.db.db_path}")
    
    # =========================================================================
    # Snapshot Operations
    # =========================================================================
    
    def save_snapshot(self, snapshot: Snapshot):
        """Save a snapshot to the database."""
        self.db.insert('snapshots', {
            'id': snapshot.id,
            'collector': snapshot.collector,
            'timestamp': snapshot.timestamp.isoformat(),
            'data': json.dumps(snapshot.data)
        })
    
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
        
        query = "SELECT * FROM snapshots WHERE collector = :collector"
        params: Dict[str, Any] = {'collector': collector}
        
        if since:
            query += " AND timestamp >= :since"
            params['since'] = since.isoformat()
        if until:
            query += " AND timestamp <= :until"
            params['until'] = until.isoformat()
        
        query += " ORDER BY timestamp DESC LIMIT :limit"
        params['limit'] = limit
        
        rows = self.db.fetchall(query, params)
        return [
            Snapshot(
                id=row[0],  # id
                collector=row[1],  # collector
                timestamp=datetime.fromisoformat(row[2]),  # timestamp
                data=json.loads(row[3])  # data
            )
            for row in rows
        ]
    
    def get_latest_snapshot(self, collector: str) -> Optional[Snapshot]:
        """Get the most recent snapshot for a collector."""
        snapshots = self.get_snapshots(collector, limit=1)
        return snapshots[0] if snapshots else None
    
    def cleanup_old_snapshots(self, retention_days: int = 90):
        """Delete snapshots older than retention period."""
        cutoff = datetime.now(get_brt()) - timedelta(days=retention_days)
        
        with self.db.get_connection() as conn:
            result = conn.execute(
                self.db.engine.dialect.preparer(self.db.engine.dialect).format_column(
                    "DELETE FROM snapshots WHERE timestamp < :cutoff"
                ),
                {"cutoff": cutoff.isoformat()}
            )
            conn.commit()
            if result.rowcount > 0:
                logger.info(f"[STORE] Cleaned up {result.rowcount} old snapshots (retention={retention_days} days)")
    
    # =========================================================================
    # Insight Operations
    # =========================================================================
    
    def save_insight(self, insight: Insight):
        """Save an insight to the database."""
        self.db.insert('insights', {
            'id': insight.id,
            'type': insight.type.value,
            'category': insight.category.value,
            'priority': insight.priority.value,
            'title': insight.title,
            'message': insight.message,
            'confidence': insight.confidence,
            'data': json.dumps(insight.data),
            'source_analyzer': insight.source_analyzer,
            'dedupe_key': insight.dedupe_key,
            'created_at': insight.created_at.isoformat(),
            'expires_at': insight.expires_at.isoformat() if insight.expires_at else None
        })
    
    def get_pending_insights(self, priority: Optional[Priority] = None) -> List[Insight]:
        """Get insights that haven't been delivered yet."""
        query = "SELECT * FROM insights WHERE delivered = 0"
        params: Dict[str, Any] = {}
        
        if priority:
            query += " AND priority = :priority"
            params['priority'] = priority.value
        
        query += " ORDER BY created_at DESC"
        
        rows = self.db.fetchall(query, params)
        return [self._row_to_insight(row) for row in rows]
    
    def get_recent_insights(
        self, 
        hours: int = 24,
        category: Optional[Category] = None
    ) -> List[Insight]:
        """Get insights from the last N hours."""
        since = datetime.now(get_brt()) - timedelta(hours=hours)
        query = "SELECT * FROM insights WHERE created_at >= :since"
        params: Dict[str, Any] = {'since': since.isoformat()}
        
        if category:
            query += " AND category = :category"
            params['category'] = category.value
        
        query += " ORDER BY created_at DESC"
        
        rows = self.db.fetchall(query, params)
        return [self._row_to_insight(row) for row in rows]
    
    def check_duplicate(self, dedupe_key: str, hours: int = 4) -> bool:
        """Check if a similar insight was recently created."""
        since = datetime.now(get_brt()) - timedelta(hours=hours)
        row = self.db.fetchone(
            """SELECT COUNT(*) as cnt FROM insights 
               WHERE dedupe_key = :dedupe_key AND created_at >= :since""",
            {'dedupe_key': dedupe_key, 'since': since.isoformat()}
        )
        return row[0] > 0 if row else False
    
    def mark_delivered(self, insight_id: str):
        """Mark an insight as delivered."""
        self.db.update(
            'insights',
            {'delivered': 1},
            'id = :id',
            {'id': insight_id}
        )
    
    def _row_to_insight(self, row: tuple) -> Insight:
        """Convert a database row tuple to an Insight object.
        
        Row format: (id, type, category, priority, title, message, confidence,
                     data, source_analyzer, dedupe_key, created_at, expires_at, delivered)
        """
        return Insight(
            id=row[0],
            type=InsightType(row[1]),
            category=Category(row[2]),
            priority=Priority(row[3]),
            title=row[4],
            message=row[5],
            confidence=row[6],
            data=json.loads(row[7]) if row[7] else {},
            source_analyzer=row[8] or "",
            dedupe_key=row[9],
            created_at=datetime.fromisoformat(row[10]),
            expires_at=datetime.fromisoformat(row[11]) if row[11] else None
        )
    
    # =========================================================================
    # Delivery Operations
    # =========================================================================
    
    def save_delivery(self, delivery: Delivery):
        """Record a delivery."""
        self.db.insert('deliveries', {
            'id': delivery.id,
            'insight_id': delivery.insight_id,
            'channel': delivery.channel.value,
            'delivered_at': delivery.delivered_at.isoformat(),
            'success': int(delivery.success),
            'error': delivery.error
        })
    
    def get_deliveries_today(self) -> List[Delivery]:
        """Get all deliveries from today."""
        today = datetime.now(get_brt()).strftime("%Y-%m-%d")
        rows = self.db.fetchall(
            """SELECT * FROM deliveries 
               WHERE delivered_at LIKE :today || '%'
               ORDER BY delivered_at DESC""",
            {'today': today}
        )
        return [
            Delivery(
                id=row[0],
                insight_id=row[1],
                channel=DeliveryChannel(row[2]),
                delivered_at=datetime.fromisoformat(row[3]),
                success=bool(row[4]),
                error=row[5]
            )
            for row in rows
        ]
    
    # =========================================================================
    # Budget Operations
    # =========================================================================
    
    def get_today_budget(self, max_per_day: int = 5) -> ReachOutBudget:
        """Get or create today's reach-out budget."""
        today = datetime.now(get_brt()).strftime("%Y-%m-%d")
        row = self.db.fetchone(
            "SELECT * FROM reach_out_budget WHERE date = :date",
            {'date': today}
        )
        
        if row:
            return ReachOutBudget(
                date=row[0],
                count=row[1],
                max_per_day=row[2],
                deliveries=json.loads(row[3])
            )
        else:
            # Create new budget for today
            budget = ReachOutBudget(date=today, max_per_day=max_per_day)
            self.db.insert('reach_out_budget', {
                'date': budget.date,
                'count': budget.count,
                'max_per_day': budget.max_per_day,
                'deliveries': json.dumps(budget.deliveries)
            })
            return budget
    
    def increment_budget(self, insight_id: str):
        """Increment today's reach-out count."""
        today = datetime.now(get_brt()).strftime("%Y-%m-%d")
        
        # Get current deliveries
        row = self.db.fetchone(
            "SELECT deliveries FROM reach_out_budget WHERE date = :date",
            {'date': today}
        )
        
        deliveries = json.loads(row[0]) if row else []
        deliveries.append(insight_id)
        
        self.db.update(
            'reach_out_budget',
            {'count': 'count + 1', 'deliveries': json.dumps(deliveries)},
            'date = :date',
            {'date': today}
        )
    
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
        try:
            self.db.insert('journal_threads', {
                'date': date,
                'message_id': message_id,
                'created_at': datetime.now(get_brt()).isoformat()
            })
            return True
        except Exception:
            # Date already has a thread (unique constraint)
            return False
    
    def get_journal_thread(self, date: str) -> Optional[int]:
        """Get the thread message ID for a date.
        
        Args:
            date: Date in YYYY-MM-DD format
            
        Returns:
            Message ID or None if not found
        """
        row = self.db.fetchone(
            "SELECT message_id FROM journal_threads WHERE date = :date",
            {'date': date}
        )
        return row[0] if row else None
    
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
        self.db.insert('journal_entries', {
            'date': date,
            'timestamp': timestamp.isoformat(),
            'entry_type': entry_type,
            'content': content,
            'thread_message_id': thread_message_id
        })
    
    def get_journal_entries(self, date: str) -> List[Dict[str, Any]]:
        """Get all journal entries for a date.
        
        Args:
            date: Date in YYYY-MM-DD format
            
        Returns:
            List of journal entry dicts
        """
        rows = self.db.fetchall(
            """SELECT * FROM journal_entries 
               WHERE date = :date 
               ORDER BY timestamp ASC""",
            {'date': date}
        )
        return [
            {
                "id": row[0],
                "date": row[1],
                "timestamp": datetime.fromisoformat(row[2]),
                "entry_type": row[3],
                "content": row[4],
                "thread_message_id": row[5]
            }
            for row in rows
        ]
