"""
Conversation Memory Store for Friday AI.

Stores Friday's own memories - what it said, advice given, corrections received.
This gives Friday continuity and the ability to learn from mistakes.
"""
import json
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional, Dict, Any
from dataclasses import dataclass, asdict
from enum import Enum

from app.core.config import settings
from app.core.logging import logger


class ConversationEventType(Enum):
    """Types of conversation events Friday remembers."""
    ADVICE_GIVEN = "advice_given"           # Friday gave advice/recommendation
    CORRECTION_RECEIVED = "correction"       # User corrected Friday
    IMPORTANT_MOMENT = "important_moment"    # Emotionally significant exchange
    COMMITMENT_MADE = "commitment"           # User or Friday made a commitment
    TOPIC_DISCUSSED = "topic_discussed"      # Significant topic was discussed
    FEEDBACK_RECEIVED = "feedback"           # User gave explicit feedback (good/bad)


@dataclass
class ConversationEvent:
    """A memorable event from a conversation."""
    id: str
    event_type: ConversationEventType
    timestamp: datetime
    
    # What was discussed
    topic: str
    user_message: str
    friday_response: str
    
    # Context and learning
    context: Optional[str] = None  # Additional context
    lesson_learned: Optional[str] = None  # What Friday learned from this
    follow_up_date: Optional[datetime] = None  # When to follow up
    followed_up: bool = False
    
    # For corrections
    what_was_wrong: Optional[str] = None
    correct_answer: Optional[str] = None
    
    # Metadata
    tags: Optional[List[str]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON storage."""
        data = asdict(self)
        data['event_type'] = self.event_type.value
        data['timestamp'] = self.timestamp.isoformat()
        if self.follow_up_date:
            data['follow_up_date'] = self.follow_up_date.isoformat()
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ConversationEvent':
        """Create from dictionary."""
        data['event_type'] = ConversationEventType(data['event_type'])
        data['timestamp'] = datetime.fromisoformat(data['timestamp'])
        if data.get('follow_up_date'):
            data['follow_up_date'] = datetime.fromisoformat(data['follow_up_date'])
        return cls(**data)
    
    def to_context_string(self) -> str:
        """Format as context for LLM."""
        date_str = self.timestamp.strftime("%Y-%m-%d")
        
        if self.event_type == ConversationEventType.CORRECTION_RECEIVED:
            return (
                f"[{date_str}] CORRECTION: When discussing '{self.topic}', "
                f"I said something wrong. What was wrong: {self.what_was_wrong}. "
                f"The correct answer: {self.correct_answer}. "
                f"Lesson: {self.lesson_learned or 'Be more careful about this topic.'}"
            )
        elif self.event_type == ConversationEventType.ADVICE_GIVEN:
            return (
                f"[{date_str}] ADVICE I GAVE: On '{self.topic}', "
                f"I advised: {self.friday_response[:200]}..."
            )
        elif self.event_type == ConversationEventType.COMMITMENT_MADE:
            return (
                f"[{date_str}] COMMITMENT: Regarding '{self.topic}', "
                f"commitment made: {self.context}"
            )
        elif self.event_type == ConversationEventType.IMPORTANT_MOMENT:
            return (
                f"[{date_str}] IMPORTANT: Discussion about '{self.topic}'. "
                f"Context: {self.context}"
            )
        else:
            return f"[{date_str}] {self.topic}: {self.context or self.friday_response[:100]}"


class ConversationMemoryStore:
    """
    Stores and retrieves Friday's conversation memories.
    
    This enables:
    - Remembering advice given (to track outcomes)
    - Learning from corrections
    - Following up on commitments
    - Maintaining emotional context
    """
    
    def __init__(self):
        """Initialize conversation memory store."""
        self.storage_path = settings.friday_path / "5.5 Conversations"
        self.storage_path.mkdir(parents=True, exist_ok=True)
        
        # Separate files for different event types
        self.corrections_file = self.storage_path / "corrections.json"
        self.advice_file = self.storage_path / "advice_given.json"
        self.moments_file = self.storage_path / "important_moments.json"
        self.commitments_file = self.storage_path / "commitments.json"
        
        # In-memory cache
        self._corrections: List[ConversationEvent] = []
        self._advice: List[ConversationEvent] = []
        self._moments: List[ConversationEvent] = []
        self._commitments: List[ConversationEvent] = []
        
        self._load_all()
        logger.info(f"Conversation memory initialized: {self.storage_path}")
    
    def _load_all(self):
        """Load all conversation memories from disk."""
        self._corrections = self._load_file(self.corrections_file)
        self._advice = self._load_file(self.advice_file)
        self._moments = self._load_file(self.moments_file)
        self._commitments = self._load_file(self.commitments_file)
        
        total = len(self._corrections) + len(self._advice) + len(self._moments) + len(self._commitments)
        if total > 0:
            logger.info(f"Loaded {total} conversation memories")
    
    def _load_file(self, filepath: Path) -> List[ConversationEvent]:
        """Load events from a JSON file."""
        if not filepath.exists():
            return []
        
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)
            return [ConversationEvent.from_dict(item) for item in data]
        except Exception as e:
            logger.error(f"Error loading {filepath}: {e}")
            return []
    
    def _save_file(self, filepath: Path, events: List[ConversationEvent]):
        """Save events to a JSON file."""
        try:
            with open(filepath, 'w') as f:
                json.dump([e.to_dict() for e in events], f, indent=2)
        except Exception as e:
            logger.error(f"Error saving {filepath}: {e}")
    
    def add_correction(
        self,
        topic: str,
        user_message: str,
        friday_response: str,
        what_was_wrong: str,
        correct_answer: str,
        lesson_learned: Optional[str] = None,
    ) -> ConversationEvent:
        """
        Record a correction from the user.
        
        Called when user says something like "that's wrong", "actually it's X",
        "no, you're mistaken".
        """
        event = ConversationEvent(
            id=str(uuid.uuid4())[:8],
            event_type=ConversationEventType.CORRECTION_RECEIVED,
            timestamp=datetime.now(settings.user_timezone),
            topic=topic,
            user_message=user_message,
            friday_response=friday_response,
            what_was_wrong=what_was_wrong,
            correct_answer=correct_answer,
            lesson_learned=lesson_learned or f"Remember: {correct_answer}",
        )
        
        self._corrections.append(event)
        self._save_file(self.corrections_file, self._corrections)
        
        logger.info(f"Recorded correction: {topic} - {what_was_wrong[:50]}")
        return event
    
    def add_advice(
        self,
        topic: str,
        user_message: str,
        friday_response: str,
        follow_up_days: Optional[int] = None,
        tags: Optional[List[str]] = None,
    ) -> ConversationEvent:
        """
        Record advice given by Friday.
        
        Allows tracking whether advice was helpful and following up.
        """
        follow_up_date = None
        if follow_up_days:
            follow_up_date = datetime.now(settings.user_timezone) + timedelta(days=follow_up_days)
        
        event = ConversationEvent(
            id=str(uuid.uuid4())[:8],
            event_type=ConversationEventType.ADVICE_GIVEN,
            timestamp=datetime.now(settings.user_timezone),
            topic=topic,
            user_message=user_message,
            friday_response=friday_response,
            follow_up_date=follow_up_date,
            tags=tags,
        )
        
        self._advice.append(event)
        self._save_file(self.advice_file, self._advice)
        
        logger.info(f"Recorded advice: {topic}")
        return event
    
    def add_important_moment(
        self,
        topic: str,
        user_message: str,
        friday_response: str,
        context: str,
        tags: Optional[List[str]] = None,
    ) -> ConversationEvent:
        """
        Record an emotionally significant or important conversation moment.
        """
        event = ConversationEvent(
            id=str(uuid.uuid4())[:8],
            event_type=ConversationEventType.IMPORTANT_MOMENT,
            timestamp=datetime.now(settings.user_timezone),
            topic=topic,
            user_message=user_message,
            friday_response=friday_response,
            context=context,
            tags=tags,
        )
        
        self._moments.append(event)
        self._save_file(self.moments_file, self._moments)
        
        logger.info(f"Recorded important moment: {topic}")
        return event
    
    def add_commitment(
        self,
        topic: str,
        user_message: str,
        friday_response: str,
        commitment: str,
        follow_up_days: int = 7,
        tags: Optional[List[str]] = None,
    ) -> ConversationEvent:
        """
        Record a commitment made by user or Friday.
        
        E.g., "I'll talk to Camila about this" or "I'll check on this tomorrow"
        """
        follow_up_date = datetime.now(settings.user_timezone) + timedelta(days=follow_up_days)
        
        event = ConversationEvent(
            id=str(uuid.uuid4())[:8],
            event_type=ConversationEventType.COMMITMENT_MADE,
            timestamp=datetime.now(settings.user_timezone),
            topic=topic,
            user_message=user_message,
            friday_response=friday_response,
            context=commitment,
            follow_up_date=follow_up_date,
            tags=tags,
        )
        
        self._commitments.append(event)
        self._save_file(self.commitments_file, self._commitments)
        
        logger.info(f"Recorded commitment: {commitment}")
        return event
    
    def get_corrections_for_topic(self, topic: str, limit: int = 5) -> List[ConversationEvent]:
        """Get corrections related to a topic."""
        topic_lower = topic.lower()
        relevant = [
            c for c in self._corrections
            if topic_lower in c.topic.lower() or 
               topic_lower in (c.what_was_wrong or "").lower() or
               topic_lower in (c.correct_answer or "").lower()
        ]
        return sorted(relevant, key=lambda x: x.timestamp, reverse=True)[:limit]
    
    def get_recent_corrections(self, days: int = 30, limit: int = 10) -> List[ConversationEvent]:
        """Get recent corrections."""
        cutoff = datetime.now(settings.user_timezone) - timedelta(days=days)
        recent = [c for c in self._corrections if c.timestamp > cutoff]
        return sorted(recent, key=lambda x: x.timestamp, reverse=True)[:limit]
    
    def get_advice_on_topic(self, topic: str, limit: int = 5) -> List[ConversationEvent]:
        """Get past advice given on a topic."""
        topic_lower = topic.lower()
        relevant = [
            a for a in self._advice
            if topic_lower in a.topic.lower() or
               topic_lower in a.friday_response.lower() or
               (a.tags and any(topic_lower in t.lower() for t in a.tags))
        ]
        return sorted(relevant, key=lambda x: x.timestamp, reverse=True)[:limit]
    
    def get_pending_follow_ups(self) -> List[ConversationEvent]:
        """Get commitments and advice that need follow-up."""
        now = datetime.now(settings.user_timezone)
        pending = []
        
        for event in self._commitments + self._advice:
            if event.follow_up_date and not event.followed_up:
                if event.follow_up_date <= now:
                    pending.append(event)
        
        return sorted(pending, key=lambda x: x.follow_up_date)
    
    def mark_followed_up(self, event_id: str) -> bool:
        """Mark an event as followed up."""
        for collection in [self._commitments, self._advice]:
            for event in collection:
                if event.id == event_id:
                    event.followed_up = True
                    # Save the appropriate file
                    if event.event_type == ConversationEventType.COMMITMENT_MADE:
                        self._save_file(self.commitments_file, self._commitments)
                    else:
                        self._save_file(self.advice_file, self._advice)
                    return True
        return False
    
    def get_context_for_message(self, message: str, limit: int = 5) -> str:
        """
        Get relevant conversation memory context for a user message.
        
        Returns formatted string to include in LLM context.
        """
        message_lower = message.lower()
        # Extract meaningful words (> 2 chars to be more inclusive)
        # Strip punctuation from words
        import re
        message_words = [re.sub(r'[^\w]', '', w) for w in message_lower.split()]
        message_words = [w for w in message_words if len(w) > 2]
        relevant_events = []
        
        # Check for relevant corrections
        for correction in self._corrections:
            searchable = f"{correction.topic} {correction.what_was_wrong or ''} {correction.correct_answer or ''}".lower()
            if any(word in searchable for word in message_words):
                relevant_events.append((correction, 3))  # High priority for corrections
        
        # Check for relevant past advice
        for advice in self._advice:
            searchable = f"{advice.topic} {advice.friday_response}".lower()
            if any(word in searchable for word in message_words):
                relevant_events.append((advice, 2))
        
        # Check for relevant moments
        for moment in self._moments:
            searchable = f"{moment.topic} {moment.context or ''}".lower()
            if any(word in searchable for word in message_words):
                relevant_events.append((moment, 1))
        
        if not relevant_events:
            return ""
        
        # Sort by priority and take top results
        relevant_events.sort(key=lambda x: (-x[1], x[0].timestamp), reverse=False)
        top_events = [e[0] for e in relevant_events[:limit]]
        
        context_parts = [
            "## My Previous Interactions on This Topic",
            "(Remember these when responding - especially any corrections!)",
            ""
        ]
        
        for event in top_events:
            context_parts.append(event.to_context_string())
        
        return "\n".join(context_parts)
    
    def get_all_corrections_context(self) -> str:
        """Get all corrections as context (for general awareness)."""
        if not self._corrections:
            return ""
        
        # Get recent corrections (last 30 days) and all-time important ones
        recent = self.get_recent_corrections(days=30, limit=10)
        
        if not recent:
            return ""
        
        lines = [
            "## Things I've Been Corrected On",
            "(I should be careful about these topics)",
            ""
        ]
        
        for correction in recent:
            lines.append(f"- {correction.topic}: {correction.lesson_learned}")
        
        return "\n".join(lines)
    
    def search_memories(self, query: str, limit: int = 10) -> List[ConversationEvent]:
        """Search all conversation memories."""
        query_lower = query.lower()
        query_words = [w for w in query_lower.split() if len(w) > 2]
        
        scored_results = []
        
        all_events = self._corrections + self._advice + self._moments + self._commitments
        
        for event in all_events:
            score = 0
            searchable = f"{event.topic} {event.user_message} {event.friday_response} {event.context or ''}"
            searchable_lower = searchable.lower()
            
            for word in query_words:
                if word in searchable_lower:
                    score += 1
            
            if score > 0:
                scored_results.append((event, score))
        
        scored_results.sort(key=lambda x: (-x[1], x[0].timestamp))
        return [e[0] for e in scored_results[:limit]]
    
    def get_stats(self) -> Dict[str, int]:
        """Get statistics about conversation memories."""
        return {
            "corrections": len(self._corrections),
            "advice_given": len(self._advice),
            "important_moments": len(self._moments),
            "commitments": len(self._commitments),
            "pending_follow_ups": len(self.get_pending_follow_ups()),
        }


# Singleton instance
conversation_memory = ConversationMemoryStore()
