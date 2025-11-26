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
