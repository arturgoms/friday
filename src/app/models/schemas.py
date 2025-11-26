"""Pydantic schemas."""
from typing import List, Optional
from pydantic import BaseModel


class ChatRequest(BaseModel):
    """Chat request schema."""
    message: str
    use_rag: bool = True
    use_web: bool = False
    use_memory: bool = True
    save_memory: bool = True
    session_id: Optional[str] = None
    stream: bool = False


class RememberRequest(BaseModel):
    """Remember request schema."""
    content: str
    title: Optional[str] = None
    tags: Optional[List[str]] = None


class RetrievedChunk(BaseModel):
    """Retrieved document chunk."""
    path: Optional[str]
    chunk_idx: Optional[int]
    text: str


class MemoryItem(BaseModel):
    """Memory item."""
    text: str
    label: Optional[str] = None


class ChatResponse(BaseModel):
    """Chat response schema."""
    answer: str
    used_rag: bool
    used_web: bool
    used_memory: bool
    context: Optional[List[RetrievedChunk]] = None
    memory_context: Optional[List[MemoryItem]] = None
    session_id: Optional[str] = None


class TaskCreate(BaseModel):
    """Task creation schema."""
    title: str
    description: Optional[str] = None
    due_date: Optional[str] = None  # Natural language: "tomorrow", "next Friday", "2024-12-01"
    priority: Optional[str] = "Medium"  # Low, Medium, High, Urgent
    context: Optional[str] = None  # home, work, gym, etc.
    energy_level: Optional[str] = None  # Low, Medium, High
    project: Optional[str] = None
    people: Optional[List[str]] = None


class TaskUpdate(BaseModel):
    """Task update schema."""
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None  # pending, in_progress, completed, cancelled
    due_date: Optional[str] = None
    priority: Optional[str] = None
    context: Optional[str] = None
    energy_level: Optional[str] = None
    project: Optional[str] = None
    people: Optional[List[str]] = None


class TaskResponse(BaseModel):
    """Task response schema."""
    id: int
    title: str
    description: Optional[str]
    status: str
    priority: str
    context: Optional[str]
    energy_level: Optional[str]
    due_date: Optional[str]
    created_at: str
    updated_at: str
    project: Optional[str]
    people: Optional[str]  # JSON string
