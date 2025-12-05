"""Chat intent handlers."""
from app.services.chat.handlers.base import IntentHandler, ChatResponse, ChatContext

# Memory handlers
from app.services.chat.handlers.memory import (
    MemorySaveHandler,
    MemoryAmbiguousHandler,
    MemoryListHandler,
    MemoryDeleteHandler,
)

# Reminder handlers
from app.services.chat.handlers.reminder import (
    ReminderCreateHandler,
    ReminderQueryHandler,
    ReminderDeleteHandler,
)

# Note handlers
from app.services.chat.handlers.note import (
    NoteCreateHandler,
    NoteUpdateHandler,
    NoteSearchHandler,
    NoteGetHandler,
)

__all__ = [
    # Base classes
    'IntentHandler',
    'ChatResponse',
    'ChatContext',
    # Memory handlers
    'MemorySaveHandler',
    'MemoryAmbiguousHandler',
    'MemoryListHandler',
    'MemoryDeleteHandler',
    # Reminder handlers
    'ReminderCreateHandler',
    'ReminderQueryHandler',
    'ReminderDeleteHandler',
    # Note handlers
    'NoteCreateHandler',
    'NoteUpdateHandler',
    'NoteSearchHandler',
    'NoteGetHandler',
]
