"""
Dynamic Alert Store - Persistent storage for Friday's self-created alerts.

Alerts are stored as markdown files in brain/5. Friday/5.2 Alerts/
so they can be viewed and edited in Obsidian.
"""
import os
import re
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional, Dict, Any
from enum import Enum
import yaml

from app.core.config import settings
from app.core.logging import logger


class AlertType(Enum):
    """Types of dynamic alerts Friday can create."""
    DATE_REMINDER = "date_reminder"      # Specific date/time reminder
    RECURRING = "recurring"               # Daily/weekly checks
    CONDITION = "condition"               # When condition is met
    FOLLOW_UP = "follow_up"              # Follow up on something
    BIRTHDAY = "birthday"                 # Birthday reminder
    HEALTH_WATCH = "health_watch"         # Monitor health metric
    DEADLINE = "deadline"                 # Project/task deadline


class DynamicAlert:
    """A dynamic alert created by Friday from conversations."""
    
    def __init__(
        self,
        alert_id: str,
        title: str,
        description: str,
        alert_type: AlertType,
        trigger_date: Optional[datetime] = None,
        trigger_condition: Optional[str] = None,
        recurring_pattern: Optional[str] = None,  # daily, weekly, monthly
        priority: str = "medium",
        source_context: Optional[str] = None,
        created_at: Optional[datetime] = None,
        last_triggered: Optional[datetime] = None,
        active: bool = True,
        tags: Optional[List[str]] = None,
    ):
        self.alert_id = alert_id
        self.title = title
        self.description = description
        self.alert_type = alert_type
        self.trigger_date = trigger_date
        self.trigger_condition = trigger_condition
        self.recurring_pattern = recurring_pattern
        self.priority = priority
        self.source_context = source_context
        self.created_at = created_at or datetime.now(settings.user_timezone)
        self.last_triggered = last_triggered
        self.active = active
        self.tags = tags or []
    
    def should_trigger(self, now: Optional[datetime] = None) -> bool:
        """Check if this alert should trigger now."""
        if not self.active:
            return False
        
        now = now or datetime.now(settings.user_timezone)
        
        # Date-based trigger
        if self.trigger_date:
            # Make timezone-aware if needed
            trigger = self.trigger_date
            if trigger.tzinfo is None:
                trigger = trigger.replace(tzinfo=settings.user_timezone)
            
            # Check if we're past the trigger date
            if now >= trigger:
                # For non-recurring, only trigger once
                if not self.recurring_pattern:
                    if self.last_triggered is None:
                        return True
                else:
                    # For recurring, check if enough time has passed
                    if self.last_triggered is None:
                        return True
                    
                    time_since_last = now - self.last_triggered
                    if self.recurring_pattern == "daily" and time_since_last >= timedelta(days=1):
                        return True
                    elif self.recurring_pattern == "weekly" and time_since_last >= timedelta(weeks=1):
                        return True
                    elif self.recurring_pattern == "monthly" and time_since_last >= timedelta(days=30):
                        return True
        
        return False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "alert_id": self.alert_id,
            "title": self.title,
            "description": self.description,
            "alert_type": self.alert_type.value,
            "trigger_date": self.trigger_date.isoformat() if self.trigger_date else None,
            "trigger_condition": self.trigger_condition,
            "recurring_pattern": self.recurring_pattern,
            "priority": self.priority,
            "source_context": self.source_context,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "last_triggered": self.last_triggered.isoformat() if self.last_triggered else None,
            "active": self.active,
            "tags": self.tags,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'DynamicAlert':
        """Create from dictionary."""
        return cls(
            alert_id=data["alert_id"],
            title=data["title"],
            description=data["description"],
            alert_type=AlertType(data["alert_type"]),
            trigger_date=datetime.fromisoformat(data["trigger_date"]) if data.get("trigger_date") else None,
            trigger_condition=data.get("trigger_condition"),
            recurring_pattern=data.get("recurring_pattern"),
            priority=data.get("priority", "medium"),
            source_context=data.get("source_context"),
            created_at=datetime.fromisoformat(data["created_at"]) if data.get("created_at") else None,
            last_triggered=datetime.fromisoformat(data["last_triggered"]) if data.get("last_triggered") else None,
            active=data.get("active", True),
            tags=data.get("tags", []),
        )


class AlertStore:
    """
    Stores dynamic alerts as markdown files.
    
    Alerts are stored in brain/5. Friday/5.2 Alerts/ so they can be
    viewed and managed in Obsidian.
    """
    
    def __init__(self):
        """Initialize alert store."""
        self.alerts_path = settings.brain_path / "5. Friday" / "5.2 Alerts"
        
        # Ensure directory exists
        if not self.alerts_path.exists():
            self.alerts_path.mkdir(parents=True, exist_ok=True)
            logger.info(f"Created alerts directory: {self.alerts_path}")
        
        logger.info(f"Alert store initialized: {self.alerts_path}")
    
    def _generate_id(self) -> str:
        """Generate unique alert ID."""
        return str(uuid.uuid4())[:8]
    
    def _parse_frontmatter(self, content: str) -> tuple[Dict[str, Any], str]:
        """Parse YAML frontmatter from markdown content."""
        if not content.startswith("---"):
            return {}, content
        
        parts = content.split("---", 2)
        if len(parts) < 3:
            return {}, content
        
        try:
            metadata = yaml.safe_load(parts[1]) or {}
            body = parts[2].strip()
            return metadata, body
        except yaml.YAMLError:
            return {}, content
    
    def _format_alert(self, alert: DynamicAlert) -> str:
        """Format alert as markdown file."""
        # Build tags
        all_tags = ["area/friday", "extra/alert", f"alert/{alert.alert_type.value}"]
        all_tags.extend(alert.tags)
        tags_yaml = "\n".join([f"  - {tag}" for tag in all_tags])
        
        # Format trigger info
        trigger_info = ""
        if alert.trigger_date:
            trigger_info = f"**Trigger Date:** {alert.trigger_date.strftime('%Y-%m-%d %H:%M')}\n"
        if alert.recurring_pattern:
            trigger_info += f"**Recurring:** {alert.recurring_pattern}\n"
        if alert.trigger_condition:
            trigger_info += f"**Condition:** {alert.trigger_condition}\n"
        
        note = f"""---
tags:
{tags_yaml}
alert_id: "{alert.alert_id}"
alert_type: "{alert.alert_type.value}"
priority: "{alert.priority}"
trigger_date: {f'"{alert.trigger_date.isoformat()}"' if alert.trigger_date else 'null'}
recurring_pattern: {f'"{alert.recurring_pattern}"' if alert.recurring_pattern else 'null'}
trigger_condition: {f'"{alert.trigger_condition}"' if alert.trigger_condition else 'null'}
active: {str(alert.active).lower()}
created: "{alert.created_at.strftime('%Y-%m-%d')}"
last_triggered: {f'"{alert.last_triggered.isoformat()}"' if alert.last_triggered else 'null'}
---

# {alert.title}

{alert.description}

---

## Alert Details

{trigger_info}
**Priority:** {alert.priority}
**Status:** {"Active" if alert.active else "Inactive"}

## Source Context

{alert.source_context or "Created by Friday from conversation analysis."}
"""
        return note
    
    def create_alert(
        self,
        title: str,
        description: str,
        alert_type: AlertType,
        trigger_date: Optional[datetime] = None,
        trigger_condition: Optional[str] = None,
        recurring_pattern: Optional[str] = None,
        priority: str = "medium",
        source_context: Optional[str] = None,
        tags: Optional[List[str]] = None,
    ) -> Optional[DynamicAlert]:
        """
        Create a new dynamic alert.
        
        Args:
            title: Alert title
            description: What to alert about
            alert_type: Type of alert
            trigger_date: When to trigger (for date-based alerts)
            trigger_condition: Condition to check (for condition-based alerts)
            recurring_pattern: daily/weekly/monthly for recurring alerts
            priority: low/medium/high/urgent
            source_context: The conversation that led to this alert
            tags: Additional tags
            
        Returns:
            Created DynamicAlert, or None if duplicate
        """
        # Check for duplicates - same title and type within active alerts
        existing = self.find_similar_alert(title, alert_type)
        if existing:
            logger.info(f"Skipping duplicate alert: {title} (existing: {existing.alert_id})")
            return None
        
        alert_id = self._generate_id()
        
        alert = DynamicAlert(
            alert_id=alert_id,
            title=title,
            description=description,
            alert_type=alert_type,
            trigger_date=trigger_date,
            trigger_condition=trigger_condition,
            recurring_pattern=recurring_pattern,
            priority=priority,
            source_context=source_context,
            tags=tags or [],
        )
        
        # Save to file
        filename = f"{alert_id}.md"
        filepath = self.alerts_path / filename
        
        content = self._format_alert(alert)
        filepath.write_text(content, encoding="utf-8")
        
        logger.info(f"Created dynamic alert: {alert_id} - {title}")
        
        return alert
    
    def find_similar_alert(self, title: str, alert_type: AlertType) -> Optional[DynamicAlert]:
        """
        Find an existing active alert with similar title and same type.
        
        Used for deduplication to prevent creating duplicate alerts.
        """
        # Normalize title for comparison
        title_lower = title.lower().strip()
        title_words = set(title_lower.split())
        
        for alert in self.get_active_alerts():
            if alert.alert_type != alert_type:
                continue
            
            existing_lower = alert.title.lower().strip()
            existing_words = set(existing_lower.split())
            
            # Check for exact match
            if title_lower == existing_lower:
                return alert
            
            # Check for high word overlap (>70% of words match)
            if title_words and existing_words:
                overlap = len(title_words & existing_words)
                max_len = max(len(title_words), len(existing_words))
                if overlap / max_len > 0.7:
                    return alert
        
        return None
    
    def get_alert(self, alert_id: str) -> Optional[DynamicAlert]:
        """Get an alert by ID."""
        for filepath in self.alerts_path.glob("*.md"):
            if filepath.stem == alert_id:
                try:
                    content = filepath.read_text(encoding="utf-8")
                    metadata, body = self._parse_frontmatter(content)
                    
                    return DynamicAlert(
                        alert_id=metadata.get("alert_id", alert_id),
                        title=metadata.get("title", filepath.stem),
                        description=body.split("---")[0].strip() if "---" in body else body,
                        alert_type=AlertType(metadata.get("alert_type", "date_reminder")),
                        trigger_date=datetime.fromisoformat(metadata["trigger_date"]) if metadata.get("trigger_date") else None,
                        trigger_condition=metadata.get("trigger_condition"),
                        recurring_pattern=metadata.get("recurring_pattern"),
                        priority=metadata.get("priority", "medium"),
                        source_context=metadata.get("source_context"),
                        created_at=datetime.fromisoformat(metadata["created"]) if metadata.get("created") else None,
                        last_triggered=datetime.fromisoformat(metadata["last_triggered"]) if metadata.get("last_triggered") else None,
                        active=metadata.get("active", True),
                        tags=metadata.get("tags", []),
                    )
                except Exception as e:
                    logger.error(f"Error reading alert {alert_id}: {e}")
                    return None
        return None
    
    def list_active_alerts(self) -> List[DynamicAlert]:
        """List all active alerts."""
        alerts = []
        
        for filepath in self.alerts_path.glob("*.md"):
            try:
                content = filepath.read_text(encoding="utf-8")
                metadata, body = self._parse_frontmatter(content)
                
                if not metadata.get("active", True):
                    continue
                
                # Extract title from body (first # heading)
                title = filepath.stem
                for line in body.split("\n"):
                    if line.startswith("# "):
                        title = line[2:].strip()
                        break
                
                # Extract description (content before first ---)
                description = body.split("---")[0].strip() if "---" in body else body
                # Remove the title from description
                if description.startswith(f"# {title}"):
                    description = description[len(f"# {title}"):].strip()
                
                alert = DynamicAlert(
                    alert_id=metadata.get("alert_id", filepath.stem),
                    title=title,
                    description=description,
                    alert_type=AlertType(metadata.get("alert_type", "date_reminder")),
                    trigger_date=datetime.fromisoformat(metadata["trigger_date"]) if metadata.get("trigger_date") else None,
                    trigger_condition=metadata.get("trigger_condition"),
                    recurring_pattern=metadata.get("recurring_pattern"),
                    priority=metadata.get("priority", "medium"),
                    created_at=datetime.fromisoformat(metadata["created"]) if metadata.get("created") else None,
                    last_triggered=datetime.fromisoformat(metadata["last_triggered"]) if metadata.get("last_triggered") else None,
                    active=True,
                    tags=metadata.get("tags", []),
                )
                alerts.append(alert)
                
            except Exception as e:
                logger.error(f"Error reading alert {filepath}: {e}")
                continue
        
        return alerts
    
    def mark_triggered(self, alert_id: str) -> bool:
        """Mark an alert as triggered (updates last_triggered timestamp)."""
        filepath = self.alerts_path / f"{alert_id}.md"
        
        if not filepath.exists():
            return False
        
        try:
            content = filepath.read_text(encoding="utf-8")
            now = datetime.now(settings.user_timezone)
            
            # Update last_triggered in frontmatter
            if 'last_triggered: null' in content:
                content = content.replace(
                    'last_triggered: null',
                    f'last_triggered: "{now.isoformat()}"'
                )
            else:
                # Replace existing timestamp
                content = re.sub(
                    r'last_triggered: "[^"]*"',
                    f'last_triggered: "{now.isoformat()}"',
                    content
                )
            
            filepath.write_text(content, encoding="utf-8")
            logger.info(f"Marked alert {alert_id} as triggered")
            return True
            
        except Exception as e:
            logger.error(f"Error marking alert triggered: {e}")
            return False
    
    def deactivate_alert(self, alert_id: str) -> bool:
        """Deactivate an alert."""
        filepath = self.alerts_path / f"{alert_id}.md"
        
        if not filepath.exists():
            return False
        
        try:
            content = filepath.read_text(encoding="utf-8")
            content = content.replace("active: true", "active: false")
            filepath.write_text(content, encoding="utf-8")
            logger.info(f"Deactivated alert {alert_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error deactivating alert: {e}")
            return False
    
    def delete_alert(self, alert_id: str) -> bool:
        """Delete an alert."""
        filepath = self.alerts_path / f"{alert_id}.md"
        
        if filepath.exists():
            filepath.unlink()
            logger.info(f"Deleted alert {alert_id}")
            return True
        
        return False


# Singleton instance
alert_store = AlertStore()
