"""Context-aware task management system."""
import uuid
import sqlite3
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from pathlib import Path
from enum import Enum
from app.core.logging import logger
from app.core.config import settings


class TaskPriority(Enum):
    """Task priority levels."""
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    URGENT = 4


class TaskStatus(Enum):
    """Task status."""
    TODO = "todo"
    IN_PROGRESS = "in_progress"
    BLOCKED = "blocked"
    DONE = "done"
    CANCELLED = "cancelled"


class TaskContext(Enum):
    """Task context/location."""
    ANY = "any"
    HOME = "home"
    WORK = "work"
    GYM = "gym"
    ERRANDS = "errands"


class TaskEnergyLevel(Enum):
    """Energy level required for task."""
    ANY = 0
    LOW = 1      # Can do when tired
    MEDIUM = 2   # Need normal energy
    HIGH = 3     # Need to be fresh/focused


class Task:
    """Task model."""
    
    def __init__(
        self,
        id: str,
        title: str,
        description: Optional[str] = None,
        priority: TaskPriority = TaskPriority.MEDIUM,
        status: TaskStatus = TaskStatus.TODO,
        context: TaskContext = TaskContext.ANY,
        energy_level: TaskEnergyLevel = TaskEnergyLevel.MEDIUM,
        estimated_minutes: Optional[int] = None,
        due_date: Optional[datetime] = None,
        scheduled_for: Optional[datetime] = None,
        tags: Optional[List[str]] = None,
        related_project: Optional[str] = None,
        related_people: Optional[List[str]] = None,
        created_at: Optional[datetime] = None,
        completed_at: Optional[datetime] = None
    ):
        self.id = id
        self.title = title
        self.description = description
        self.priority = priority if isinstance(priority, TaskPriority) else TaskPriority[priority]
        self.status = status if isinstance(status, TaskStatus) else TaskStatus[status]
        self.context = context if isinstance(context, TaskContext) else TaskContext[context]
        self.energy_level = energy_level if isinstance(energy_level, TaskEnergyLevel) else TaskEnergyLevel[energy_level]
        self.estimated_minutes = estimated_minutes
        self.due_date = due_date
        self.scheduled_for = scheduled_for
        self.tags = tags or []
        self.related_project = related_project
        self.related_people = related_people or []
        self.created_at = created_at or datetime.now(settings.user_timezone)
        self.completed_at = completed_at
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "priority": self.priority.name,
            "status": self.status.value,
            "context": self.context.name,
            "energy_level": self.energy_level.name,
            "estimated_minutes": self.estimated_minutes,
            "due_date": self.due_date.isoformat() if self.due_date else None,
            "scheduled_for": self.scheduled_for.isoformat() if self.scheduled_for else None,
            "tags": self.tags,
            "related_project": self.related_project,
            "related_people": self.related_people,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Task':
        """Create from dictionary."""
        return cls(
            id=data["id"],
            title=data["title"],
            description=data.get("description"),
            priority=TaskPriority[data.get("priority", "MEDIUM")],
            status=TaskStatus(data.get("status", "todo")),
            context=TaskContext[data.get("context", "ANY")],
            energy_level=TaskEnergyLevel[data.get("energy_level", "MEDIUM")],
            estimated_minutes=data.get("estimated_minutes"),
            due_date=datetime.fromisoformat(data["due_date"]) if data.get("due_date") else None,
            scheduled_for=datetime.fromisoformat(data["scheduled_for"]) if data.get("scheduled_for") else None,
            tags=data.get("tags", []),
            related_project=data.get("related_project"),
            related_people=data.get("related_people", []),
            created_at=datetime.fromisoformat(data["created_at"]) if data.get("created_at") else None,
            completed_at=datetime.fromisoformat(data["completed_at"]) if data.get("completed_at") else None
        )


class TaskManager:
    """Context-aware task management system."""
    
    def __init__(self, db_path: str = None):
        self.db_path = Path(db_path) if db_path else (settings.paths.data / "tasks.db")
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_database()
    
    def _init_database(self):
        """Initialize SQLite database."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                description TEXT,
                priority TEXT NOT NULL,
                status TEXT NOT NULL,
                context TEXT NOT NULL,
                energy_level TEXT NOT NULL,
                estimated_minutes INTEGER,
                due_date TEXT,
                scheduled_for TEXT,
                tags TEXT,
                related_project TEXT,
                related_people TEXT,
                created_at TEXT NOT NULL,
                completed_at TEXT
            )
        """)
        
        conn.commit()
        conn.close()
        logger.info(f"Task database initialized at {self.db_path}")
    
    def create_task(
        self,
        title: str,
        description: Optional[str] = None,
        priority: TaskPriority = TaskPriority.MEDIUM,
        context: TaskContext = TaskContext.ANY,
        energy_level: TaskEnergyLevel = TaskEnergyLevel.MEDIUM,
        estimated_minutes: Optional[int] = None,
        due_date: Optional[datetime] = None,
        tags: Optional[List[str]] = None,
        related_project: Optional[str] = None,
        related_people: Optional[List[str]] = None
    ) -> Task:
        """Create a new task."""
        task = Task(
            id=str(uuid.uuid4()),
            title=title,
            description=description,
            priority=priority,
            context=context,
            energy_level=energy_level,
            estimated_minutes=estimated_minutes,
            due_date=due_date,
            tags=tags,
            related_project=related_project,
            related_people=related_people
        )
        
        self._save_task(task)
        logger.info(f"Created task: {task.title} ({task.id})")
        return task
    
    def _save_task(self, task: Task):
        """Save task to database."""
        import json
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT OR REPLACE INTO tasks
            (id, title, description, priority, status, context, energy_level,
             estimated_minutes, due_date, scheduled_for, tags, related_project,
             related_people, created_at, completed_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            task.id,
            task.title,
            task.description,
            task.priority.name,
            task.status.value,
            task.context.name,
            task.energy_level.name,
            task.estimated_minutes,
            task.due_date.isoformat() if task.due_date else None,
            task.scheduled_for.isoformat() if task.scheduled_for else None,
            json.dumps(task.tags),
            task.related_project,
            json.dumps(task.related_people),
            task.created_at.isoformat() if task.created_at else None,
            task.completed_at.isoformat() if task.completed_at else None
        ))
        
        conn.commit()
        conn.close()
    
    def get_task(self, task_id: str) -> Optional[Task]:
        """Get task by ID."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return self._row_to_task(row)
        return None
    
    def list_tasks(
        self,
        status: Optional[TaskStatus] = None,
        context: Optional[TaskContext] = None,
        priority: Optional[TaskPriority] = None,
        due_before: Optional[datetime] = None,
        limit: int = 100
    ) -> List[Task]:
        """List tasks with filters."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        query = "SELECT * FROM tasks WHERE 1=1"
        params = []
        
        if status:
            query += " AND status = ?"
            params.append(status.value)
        
        if context:
            query += " AND context = ?"
            params.append(context.name)
        
        if priority:
            query += " AND priority = ?"
            params.append(priority.name)
        
        if due_before:
            query += " AND due_date <= ?"
            params.append(due_before.isoformat())
        
        query += " ORDER BY priority DESC, due_date ASC, created_at DESC LIMIT ?"
        params.append(limit)
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()
        
        return [self._row_to_task(row) for row in rows]
    
    def update_task_status(self, task_id: str, status: TaskStatus) -> bool:
        """Update task status."""
        task = self.get_task(task_id)
        if not task:
            return False
        
        task.status = status
        if status == TaskStatus.DONE:
            task.completed_at = datetime.now(settings.user_timezone)
        
        self._save_task(task)
        logger.info(f"Updated task {task_id} status to {status.value}")
        return True
    
    def schedule_task(self, task_id: str, scheduled_for: datetime) -> bool:
        """Schedule a task for specific time."""
        task = self.get_task(task_id)
        if not task:
            return False
        
        task.scheduled_for = scheduled_for
        self._save_task(task)
        logger.info(f"Scheduled task {task_id} for {scheduled_for}")
        return True
    
    def get_tasks_for_today(self) -> List[Task]:
        """Get tasks due or scheduled for today."""
        user_tz = settings.user_timezone
        now = datetime.now(user_tz)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        today_end = today_start + timedelta(days=1)
        
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT * FROM tasks
            WHERE status IN ('todo', 'in_progress')
            AND (
                (due_date >= ? AND due_date < ?)
                OR (scheduled_for >= ? AND scheduled_for < ?)
            )
            ORDER BY priority DESC, due_date ASC
        """, (
            today_start.isoformat(), today_end.isoformat(),
            today_start.isoformat(), today_end.isoformat()
        ))
        
        rows = cursor.fetchall()
        conn.close()
        
        return [self._row_to_task(row) for row in rows]
    
    def _row_to_task(self, row: sqlite3.Row) -> Task:
        """Convert database row to Task object."""
        import json
        
        return Task(
            id=row["id"],
            title=row["title"],
            description=row["description"],
            priority=TaskPriority[row["priority"]],
            status=TaskStatus(row["status"]),
            context=TaskContext[row["context"]],
            energy_level=TaskEnergyLevel[row["energy_level"]],
            estimated_minutes=row["estimated_minutes"],
            due_date=datetime.fromisoformat(row["due_date"]) if row["due_date"] else None,
            scheduled_for=datetime.fromisoformat(row["scheduled_for"]) if row["scheduled_for"] else None,
            tags=json.loads(row["tags"]) if row["tags"] else [],
            related_project=row["related_project"],
            related_people=json.loads(row["related_people"]) if row["related_people"] else [],
            created_at=datetime.fromisoformat(row["created_at"]) if row["created_at"] else None,
            completed_at=datetime.fromisoformat(row["completed_at"]) if row["completed_at"] else None
        )


# Singleton instance
task_manager = TaskManager()
