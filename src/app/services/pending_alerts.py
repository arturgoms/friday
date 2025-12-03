"""
Pending Alerts Store - Track unacknowledged proactive alerts.

Alerts are stored until the user acknowledges them (clicks "Got it").
If not acknowledged, they will be resent on the next check cycle.
"""
import json
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any
from app.core.logging import logger
from app.core.config import settings


class PendingAlertsStore:
    """Store and manage pending (unacknowledged) alerts."""
    
    def __init__(self, db_path: str = None):
        """Initialize pending alerts store."""
        if db_path is None:
            db_path = Path(__file__).parent.parent.parent.parent / "data" / "pending_alerts.db"
        
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
        
        # Configuration
        self.resend_interval_minutes = 30  # Resend unacked alerts every 30 min
        self.max_resends = 5  # Stop resending after 5 attempts
        self.quiet_hours_start = 22  # Don't send alerts after 10 PM
        self.quiet_hours_end = 7     # Don't send alerts before 7 AM
    
    def _init_db(self):
        """Initialize database schema."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS pending_alerts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    alert_key TEXT UNIQUE NOT NULL,
                    category TEXT NOT NULL,
                    title TEXT NOT NULL,
                    message TEXT NOT NULL,
                    priority TEXT DEFAULT 'medium',
                    created_at TEXT NOT NULL,
                    last_sent_at TEXT,
                    send_count INTEGER DEFAULT 0,
                    acknowledged INTEGER DEFAULT 0,
                    acknowledged_at TEXT,
                    telegram_message_id TEXT,
                    metadata TEXT
                )
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_pending_alerts_key 
                ON pending_alerts(alert_key)
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_pending_alerts_acked 
                ON pending_alerts(acknowledged)
            """)
            
            conn.commit()
    
    def is_quiet_hours(self) -> bool:
        """Check if current time is within quiet hours."""
        now = datetime.now(settings.user_timezone)
        hour = now.hour
        
        if self.quiet_hours_start > self.quiet_hours_end:
            # Quiet hours span midnight (e.g., 22:00 - 07:00)
            return hour >= self.quiet_hours_start or hour < self.quiet_hours_end
        else:
            # Quiet hours within same day
            return self.quiet_hours_start <= hour < self.quiet_hours_end
    
    def add_alert(
        self,
        alert_key: str,
        category: str,
        title: str,
        message: str,
        priority: str = "medium",
        metadata: Dict[str, Any] = None
    ) -> bool:
        """
        Add a new pending alert.
        
        Returns True if alert was added (new), False if it already exists.
        """
        now = datetime.now(settings.user_timezone).isoformat()
        metadata_json = json.dumps(metadata) if metadata else None
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                # Check if alert already exists and is not acknowledged
                existing = conn.execute("""
                    SELECT id, acknowledged FROM pending_alerts 
                    WHERE alert_key = ?
                """, (alert_key,)).fetchone()
                
                if existing:
                    if existing[1] == 1:
                        # Already acknowledged, don't re-add
                        return False
                    else:
                        # Exists but not acknowledged - don't duplicate
                        return False
                
                # Add new alert
                conn.execute("""
                    INSERT INTO pending_alerts 
                    (alert_key, category, title, message, priority, created_at, metadata)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (alert_key, category, title, message, priority, now, metadata_json))
                conn.commit()
                
                logger.info(f"Added pending alert: {alert_key}")
                return True
                
        except sqlite3.IntegrityError:
            # Alert key already exists
            return False
        except Exception as e:
            logger.error(f"Error adding pending alert: {e}")
            return False
    
    def get_alerts_to_send(self) -> List[Dict[str, Any]]:
        """
        Get alerts that should be sent now.
        
        Returns alerts that are:
        - Not acknowledged
        - Either never sent, or last sent more than resend_interval ago
        - Not exceeding max_resends
        """
        if self.is_quiet_hours():
            return []
        
        now = datetime.now(settings.user_timezone)
        cutoff = (now - timedelta(minutes=self.resend_interval_minutes)).isoformat()
        
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            
            rows = conn.execute("""
                SELECT * FROM pending_alerts
                WHERE acknowledged = 0
                AND send_count < ?
                AND (last_sent_at IS NULL OR last_sent_at < ?)
                ORDER BY 
                    CASE priority 
                        WHEN 'urgent' THEN 1 
                        WHEN 'high' THEN 2 
                        WHEN 'medium' THEN 3 
                        ELSE 4 
                    END,
                    created_at ASC
            """, (self.max_resends, cutoff)).fetchall()
            
            return [dict(row) for row in rows]
    
    def mark_sent(self, alert_key: str, telegram_message_id: str = None):
        """Mark an alert as sent (increment send count, update timestamp)."""
        now = datetime.now(settings.user_timezone).isoformat()
        
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                UPDATE pending_alerts
                SET last_sent_at = ?, send_count = send_count + 1, telegram_message_id = ?
                WHERE alert_key = ?
            """, (now, telegram_message_id, alert_key))
            conn.commit()
    
    def acknowledge(self, alert_key: str) -> bool:
        """
        Acknowledge an alert (user clicked "Got it").
        
        Returns True if alert was found and acknowledged.
        """
        now = datetime.now(settings.user_timezone).isoformat()
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                UPDATE pending_alerts
                SET acknowledged = 1, acknowledged_at = ?
                WHERE alert_key = ? AND acknowledged = 0
            """, (now, alert_key))
            conn.commit()
            
            if cursor.rowcount > 0:
                logger.info(f"Alert acknowledged: {alert_key}")
                return True
            return False
    
    def acknowledge_by_message_id(self, telegram_message_id: str) -> Optional[str]:
        """
        Acknowledge an alert by its telegram message ID.
        
        Returns the alert_key if found.
        """
        now = datetime.now(settings.user_timezone).isoformat()
        
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            
            # Find the alert
            row = conn.execute("""
                SELECT alert_key FROM pending_alerts
                WHERE telegram_message_id = ?
            """, (telegram_message_id,)).fetchone()
            
            if row:
                alert_key = row["alert_key"]
                conn.execute("""
                    UPDATE pending_alerts
                    SET acknowledged = 1, acknowledged_at = ?
                    WHERE telegram_message_id = ?
                """, (now, telegram_message_id))
                conn.commit()
                
                logger.info(f"Alert acknowledged by message ID: {alert_key}")
                return alert_key
            
            return None
    
    def get_pending_count(self) -> int:
        """Get count of pending (unacknowledged) alerts."""
        with sqlite3.connect(self.db_path) as conn:
            result = conn.execute("""
                SELECT COUNT(*) FROM pending_alerts
                WHERE acknowledged = 0 AND send_count < ?
            """, (self.max_resends,)).fetchone()
            return result[0] if result else 0
    
    def cleanup_old_alerts(self, days: int = 7):
        """Remove old acknowledged alerts."""
        cutoff = (datetime.now(settings.user_timezone) - timedelta(days=days)).isoformat()
        
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                DELETE FROM pending_alerts
                WHERE acknowledged = 1 AND acknowledged_at < ?
            """, (cutoff,))
            
            # Also remove alerts that exceeded max resends and are old
            conn.execute("""
                DELETE FROM pending_alerts
                WHERE send_count >= ? AND created_at < ?
            """, (self.max_resends, cutoff))
            
            conn.commit()
    
    def get_stats(self) -> Dict[str, Any]:
        """Get alert statistics."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            
            total = conn.execute("SELECT COUNT(*) as cnt FROM pending_alerts").fetchone()["cnt"]
            pending = conn.execute(
                "SELECT COUNT(*) as cnt FROM pending_alerts WHERE acknowledged = 0"
            ).fetchone()["cnt"]
            acknowledged = conn.execute(
                "SELECT COUNT(*) as cnt FROM pending_alerts WHERE acknowledged = 1"
            ).fetchone()["cnt"]
            
            by_category = conn.execute("""
                SELECT category, COUNT(*) as cnt, 
                       SUM(CASE WHEN acknowledged = 1 THEN 1 ELSE 0 END) as acked
                FROM pending_alerts
                GROUP BY category
            """).fetchall()
            
            return {
                "total": total,
                "pending": pending,
                "acknowledged": acknowledged,
                "by_category": [
                    {"category": r["category"], "total": r["cnt"], "acknowledged": r["acked"]}
                    for r in by_category
                ]
            }


# Singleton instance
_pending_alerts_store = None

def get_pending_alerts_store() -> PendingAlertsStore:
    """Get pending alerts store singleton."""
    global _pending_alerts_store
    if _pending_alerts_store is None:
        _pending_alerts_store = PendingAlertsStore()
    return _pending_alerts_store
