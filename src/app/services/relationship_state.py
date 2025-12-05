"""
Relationship State Service for Friday AI.

Tracks the relationship dynamics between Friday and the user,
including:
- Interaction frequency and patterns
- Emotional tone of conversations
- User's apparent mood/stress level
- Trust indicators (is user sharing more personal info?)
- Engagement quality (is user responding positively?)

This helps Friday calibrate its behavior appropriately.
"""
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field, asdict
from enum import Enum

from app.core.config import settings
from app.core.logging import logger


class RelationshipPhase(Enum):
    """Phases of the Friday-user relationship."""
    NEW = "new"                    # Just started, being cautious
    BUILDING = "building"         # Getting to know each other
    ESTABLISHED = "established"   # Comfortable, regular interactions
    TRUSTED = "trusted"           # User shares personal stuff, relies on Friday
    STRAINED = "strained"         # User seems annoyed/frustrated with Friday


class UserMood(Enum):
    """Detected user mood states."""
    UNKNOWN = "unknown"
    NEUTRAL = "neutral"
    HAPPY = "happy"
    STRESSED = "stressed"
    FRUSTRATED = "frustrated"
    SAD = "sad"
    ENERGETIC = "energetic"
    TIRED = "tired"


@dataclass
class InteractionRecord:
    """Record of a single interaction."""
    timestamp: str
    message_length: int
    sentiment: str  # positive, neutral, negative
    topic_category: str  # health, calendar, personal, task, general
    user_initiated: bool
    response_time_seconds: Optional[float] = None
    
    def to_dict(self) -> Dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict) -> "InteractionRecord":
        return cls(**data)


@dataclass
class RelationshipState:
    """Current state of the relationship."""
    phase: RelationshipPhase = RelationshipPhase.NEW
    user_mood: UserMood = UserMood.UNKNOWN
    
    # Interaction metrics
    total_interactions: int = 0
    interactions_today: int = 0
    interactions_this_week: int = 0
    
    # Engagement metrics
    positive_interactions: int = 0
    negative_interactions: int = 0
    corrections_received: int = 0
    
    # Trust indicators
    personal_topics_discussed: int = 0  # Family, feelings, health concerns
    proactive_messages_welcomed: int = 0
    proactive_messages_ignored: int = 0
    
    # Timing patterns
    average_response_length: float = 0.0
    preferred_interaction_hours: List[int] = field(default_factory=list)
    days_since_last_interaction: int = 0
    
    # Last updated
    last_interaction: Optional[str] = None
    last_updated: Optional[str] = None
    
    def to_dict(self) -> Dict:
        data = asdict(self)
        data["phase"] = self.phase.value
        data["user_mood"] = self.user_mood.value
        return data
    
    @classmethod
    def from_dict(cls, data: Dict) -> "RelationshipState":
        if "phase" in data:
            data["phase"] = RelationshipPhase(data["phase"])
        if "user_mood" in data:
            data["user_mood"] = UserMood(data["user_mood"])
        return cls(**data)


class RelationshipTracker:
    """
    Tracks and manages the relationship state between Friday and the user.
    
    This helps Friday understand:
    - How the relationship is developing
    - When to be more/less proactive
    - How to adjust tone and approach
    """
    
    def __init__(self):
        """Initialize relationship tracker."""
        self.data_path = settings.conversations_path
        self.state_file = self.data_path / "relationship_state.json"
        self.interactions_file = self.data_path / "interactions_log.json"
        
        self.state = self._load_state()
        self.recent_interactions: List[InteractionRecord] = self._load_interactions()
        
        logger.info(f"Relationship tracker initialized: phase={self.state.phase.value}")
    
    def _load_state(self) -> RelationshipState:
        """Load relationship state from file."""
        try:
            if self.state_file.exists():
                with open(self.state_file, 'r') as f:
                    data = json.load(f)
                return RelationshipState.from_dict(data)
        except Exception as e:
            logger.error(f"Error loading relationship state: {e}")
        
        return RelationshipState()
    
    def _save_state(self):
        """Save relationship state to file."""
        try:
            self.data_path.mkdir(parents=True, exist_ok=True)
            with open(self.state_file, 'w') as f:
                json.dump(self.state.to_dict(), f, indent=2)
        except Exception as e:
            logger.error(f"Error saving relationship state: {e}")
    
    def _load_interactions(self) -> List[InteractionRecord]:
        """Load recent interactions from file."""
        try:
            if self.interactions_file.exists():
                with open(self.interactions_file, 'r') as f:
                    data = json.load(f)
                return [InteractionRecord.from_dict(i) for i in data[-100:]]  # Keep last 100
        except Exception as e:
            logger.error(f"Error loading interactions: {e}")
        
        return []
    
    def _save_interactions(self):
        """Save recent interactions to file."""
        try:
            self.data_path.mkdir(parents=True, exist_ok=True)
            # Keep only last 100 interactions
            recent = self.recent_interactions[-100:]
            with open(self.interactions_file, 'w') as f:
                json.dump([i.to_dict() for i in recent], f, indent=2)
        except Exception as e:
            logger.error(f"Error saving interactions: {e}")
    
    def record_interaction(
        self,
        message: str,
        sentiment: str = "neutral",
        topic_category: str = "general",
        user_initiated: bool = True,
    ):
        """
        Record an interaction with the user.
        
        Args:
            message: The user's message
            sentiment: Detected sentiment (positive/neutral/negative)
            topic_category: Category of the topic
            user_initiated: Whether user started the conversation
        """
        now = datetime.now(settings.user_timezone)
        
        interaction = InteractionRecord(
            timestamp=now.isoformat(),
            message_length=len(message),
            sentiment=sentiment,
            topic_category=topic_category,
            user_initiated=user_initiated,
        )
        
        self.recent_interactions.append(interaction)
        self._save_interactions()
        
        # Update state
        self.state.total_interactions += 1
        self.state.last_interaction = now.isoformat()
        self.state.last_updated = now.isoformat()
        
        # Update interaction counts
        self._update_interaction_counts()
        
        # Update sentiment tracking
        if sentiment == "positive":
            self.state.positive_interactions += 1
        elif sentiment == "negative":
            self.state.negative_interactions += 1
        
        # Track personal topics
        personal_keywords = ["family", "wife", "husband", "feeling", "worried", "scared", 
                          "happy", "sad", "anxious", "stressed", "health", "therapy",
                          "relationship", "love", "friend"]
        if any(kw in message.lower() for kw in personal_keywords):
            self.state.personal_topics_discussed += 1
        
        # Update preferred hours
        hour = now.hour
        if hour not in self.state.preferred_interaction_hours:
            self.state.preferred_interaction_hours.append(hour)
            self.state.preferred_interaction_hours = sorted(self.state.preferred_interaction_hours)[-10:]
        
        # Recalculate relationship phase
        self._update_relationship_phase()
        
        self._save_state()
    
    def _update_interaction_counts(self):
        """Update daily/weekly interaction counts from recent interactions."""
        now = datetime.now(settings.user_timezone)
        today = now.date()
        week_ago = now - timedelta(days=7)
        
        today_count = 0
        week_count = 0
        
        for interaction in self.recent_interactions:
            try:
                ts = datetime.fromisoformat(interaction.timestamp)
                if ts.date() == today:
                    today_count += 1
                if ts > week_ago:
                    week_count += 1
            except:
                pass
        
        self.state.interactions_today = today_count
        self.state.interactions_this_week = week_count
        
        # Calculate days since last interaction
        if self.state.last_interaction:
            try:
                last = datetime.fromisoformat(self.state.last_interaction)
                self.state.days_since_last_interaction = (now - last).days
            except:
                self.state.days_since_last_interaction = 0
    
    def _update_relationship_phase(self):
        """Update the relationship phase based on metrics."""
        state = self.state
        
        # Calculate trust ratio
        total_proactive = state.proactive_messages_welcomed + state.proactive_messages_ignored
        proactive_acceptance_rate = (
            state.proactive_messages_welcomed / total_proactive
            if total_proactive > 0 else 0.5
        )
        
        # Calculate sentiment ratio
        total_sentiment = state.positive_interactions + state.negative_interactions
        positive_ratio = (
            state.positive_interactions / total_sentiment
            if total_sentiment > 0 else 0.5
        )
        
        # Determine phase
        if state.total_interactions < 10:
            new_phase = RelationshipPhase.NEW
        elif state.total_interactions < 50:
            if state.corrections_received > state.total_interactions * 0.3:
                new_phase = RelationshipPhase.STRAINED
            else:
                new_phase = RelationshipPhase.BUILDING
        else:
            # Established or beyond
            if positive_ratio < 0.3 or proactive_acceptance_rate < 0.3:
                new_phase = RelationshipPhase.STRAINED
            elif state.personal_topics_discussed > 10 and positive_ratio > 0.6:
                new_phase = RelationshipPhase.TRUSTED
            else:
                new_phase = RelationshipPhase.ESTABLISHED
        
        if new_phase != state.phase:
            logger.info(f"Relationship phase changed: {state.phase.value} -> {new_phase.value}")
            state.phase = new_phase
    
    def record_correction(self):
        """Record that user corrected Friday."""
        self.state.corrections_received += 1
        self._update_relationship_phase()
        self._save_state()
    
    def record_proactive_response(self, welcomed: bool):
        """Record user's response to proactive message."""
        if welcomed:
            self.state.proactive_messages_welcomed += 1
        else:
            self.state.proactive_messages_ignored += 1
        
        self._update_relationship_phase()
        self._save_state()
    
    def detect_mood(self, message: str) -> UserMood:
        """
        Detect user's mood from their message.
        
        This is a simple heuristic - could be enhanced with LLM.
        """
        message_lower = message.lower()
        
        # Stressed indicators
        stress_words = ["stressed", "overwhelmed", "too much", "can't handle", 
                       "anxious", "worried", "deadline", "pressure"]
        if any(w in message_lower for w in stress_words):
            self.state.user_mood = UserMood.STRESSED
            return UserMood.STRESSED
        
        # Frustrated indicators
        frustration_words = ["annoying", "frustrated", "ugh", "dammit", "stupid",
                           "not working", "broken", "hate"]
        if any(w in message_lower for w in frustration_words):
            self.state.user_mood = UserMood.FRUSTRATED
            return UserMood.FRUSTRATED
        
        # Happy indicators
        happy_words = ["great", "awesome", "wonderful", "excited", "happy",
                      "love it", "perfect", "amazing", "fantastic"]
        if any(w in message_lower for w in happy_words):
            self.state.user_mood = UserMood.HAPPY
            return UserMood.HAPPY
        
        # Sad indicators
        sad_words = ["sad", "depressed", "down", "lonely", "miss", "crying"]
        if any(w in message_lower for w in sad_words):
            self.state.user_mood = UserMood.SAD
            return UserMood.SAD
        
        # Tired indicators
        tired_words = ["tired", "exhausted", "sleepy", "drained", "no energy"]
        if any(w in message_lower for w in tired_words):
            self.state.user_mood = UserMood.TIRED
            return UserMood.TIRED
        
        # Default to neutral
        self.state.user_mood = UserMood.NEUTRAL
        return UserMood.NEUTRAL
    
    def get_behavior_recommendations(self) -> Dict[str, Any]:
        """
        Get recommendations for Friday's behavior based on relationship state.
        
        Returns guidance on tone, proactivity level, etc.
        """
        state = self.state
        phase = state.phase
        mood = state.user_mood
        
        recommendations = {
            "tone": "friendly",
            "proactivity_level": "medium",  # low, medium, high
            "message_length": "moderate",   # brief, moderate, detailed
            "formality": "casual",          # formal, balanced, casual
            "check_in_frequency": "normal", # rarely, normal, often
            "notes": [],
        }
        
        # Adjust for relationship phase
        if phase == RelationshipPhase.NEW:
            recommendations["tone"] = "helpful_professional"
            recommendations["proactivity_level"] = "low"
            recommendations["formality"] = "balanced"
            recommendations["notes"].append("User is new - be helpful but not overwhelming")
        
        elif phase == RelationshipPhase.BUILDING:
            recommendations["proactivity_level"] = "medium"
            recommendations["notes"].append("Building rapport - show personality but stay professional")
        
        elif phase == RelationshipPhase.ESTABLISHED:
            recommendations["tone"] = "friendly"
            recommendations["proactivity_level"] = "medium"
            recommendations["formality"] = "casual"
            recommendations["notes"].append("Established relationship - can be more casual")
        
        elif phase == RelationshipPhase.TRUSTED:
            recommendations["tone"] = "warm"
            recommendations["proactivity_level"] = "high"
            recommendations["message_length"] = "detailed"
            recommendations["formality"] = "casual"
            recommendations["check_in_frequency"] = "often"
            recommendations["notes"].append("Trusted relationship - can be proactive and personal")
        
        elif phase == RelationshipPhase.STRAINED:
            recommendations["tone"] = "helpful_apologetic"
            recommendations["proactivity_level"] = "low"
            recommendations["message_length"] = "brief"
            recommendations["formality"] = "balanced"
            recommendations["check_in_frequency"] = "rarely"
            recommendations["notes"].append("Relationship strained - be helpful but back off")
        
        # Adjust for current mood
        if mood == UserMood.STRESSED:
            recommendations["tone"] = "calm_supportive"
            recommendations["message_length"] = "brief"
            recommendations["notes"].append("User seems stressed - be calm, don't add to overwhelm")
        
        elif mood == UserMood.FRUSTRATED:
            recommendations["tone"] = "patient"
            recommendations["proactivity_level"] = "low"
            recommendations["notes"].append("User seems frustrated - be patient, focus on solutions")
        
        elif mood == UserMood.SAD:
            recommendations["tone"] = "gentle_empathetic"
            recommendations["check_in_frequency"] = "often"
            recommendations["notes"].append("User seems down - be gentle, offer support")
        
        elif mood == UserMood.TIRED:
            recommendations["message_length"] = "brief"
            recommendations["notes"].append("User seems tired - keep messages short")
        
        elif mood == UserMood.HAPPY:
            recommendations["tone"] = "enthusiastic"
            recommendations["notes"].append("User seems happy - match their energy")
        
        return recommendations
    
    def get_context_for_llm(self) -> str:
        """
        Get relationship context to include in LLM prompts.
        
        Returns a brief context string about the relationship.
        """
        state = self.state
        recs = self.get_behavior_recommendations()
        
        lines = []
        
        # Relationship phase context
        phase_descriptions = {
            RelationshipPhase.NEW: "This is a new user - still getting to know each other",
            RelationshipPhase.BUILDING: "Building rapport with this user",
            RelationshipPhase.ESTABLISHED: "Established relationship with regular interactions",
            RelationshipPhase.TRUSTED: "Trusted relationship - user shares personal topics",
            RelationshipPhase.STRAINED: "Relationship needs care - user may be frustrated",
        }
        lines.append(f"## Relationship Context")
        lines.append(phase_descriptions.get(state.phase, ""))
        
        # Current mood if known
        if state.user_mood != UserMood.UNKNOWN:
            mood_descriptions = {
                UserMood.STRESSED: "User seems stressed right now - be supportive and concise",
                UserMood.FRUSTRATED: "User seems frustrated - focus on solutions, be patient",
                UserMood.SAD: "User seems down - be gentle and empathetic",
                UserMood.TIRED: "User seems tired - keep responses brief",
                UserMood.HAPPY: "User seems in good spirits - match their energy",
                UserMood.NEUTRAL: "",
            }
            mood_note = mood_descriptions.get(state.user_mood, "")
            if mood_note:
                lines.append(mood_note)
        
        # Behavior notes
        if recs["notes"]:
            for note in recs["notes"][:2]:  # Max 2 notes
                lines.append(f"- {note}")
        
        return "\n".join(lines) if lines else ""
    
    def get_stats(self) -> Dict[str, Any]:
        """Get relationship statistics."""
        return {
            "phase": self.state.phase.value,
            "user_mood": self.state.user_mood.value,
            "total_interactions": self.state.total_interactions,
            "interactions_today": self.state.interactions_today,
            "interactions_this_week": self.state.interactions_this_week,
            "positive_ratio": (
                self.state.positive_interactions / 
                max(1, self.state.positive_interactions + self.state.negative_interactions)
            ),
            "corrections_received": self.state.corrections_received,
            "personal_topics": self.state.personal_topics_discussed,
            "preferred_hours": self.state.preferred_interaction_hours,
        }


class OpinionStore:
    """
    Stores and manages Friday's opinions and learned patterns.
    
    Friday forms opinions based on:
    - Observed patterns in user behavior
    - Advice that worked vs didn't work
    - User preferences and corrections
    - Health/calendar/task outcomes
    """
    
    def __init__(self):
        """Initialize opinion store."""
        self.data_path = settings.conversations_path
        self.opinions_file = self.data_path / "opinions.json"
        
        self.opinions: Dict[str, Any] = self._load_opinions()
        
        logger.info(f"Opinion store initialized: {len(self.opinions.get('opinions', []))} opinions")
    
    def _load_opinions(self) -> Dict[str, Any]:
        """Load opinions from file."""
        try:
            if self.opinions_file.exists():
                with open(self.opinions_file, 'r') as f:
                    return json.load(f)
        except Exception as e:
            logger.error(f"Error loading opinions: {e}")
        
        return {
            "opinions": [],
            "learned_patterns": [],
            "advice_outcomes": [],
            "last_updated": None,
        }
    
    def _save_opinions(self):
        """Save opinions to file."""
        try:
            self.data_path.mkdir(parents=True, exist_ok=True)
            self.opinions["last_updated"] = datetime.now().isoformat()
            with open(self.opinions_file, 'w') as f:
                json.dump(self.opinions, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving opinions: {e}")
    
    def add_opinion(
        self,
        topic: str,
        opinion: str,
        confidence: float,
        evidence: str,
        category: str = "general",
    ):
        """
        Add or update an opinion.
        
        Args:
            topic: What the opinion is about (e.g., "sleep", "coffee", "morning routine")
            opinion: The actual opinion/view
            confidence: How confident (0.0-1.0)
            evidence: What led to this opinion
            category: Category (health, productivity, preferences, etc.)
        """
        # Check if we already have an opinion on this topic
        existing = None
        for op in self.opinions["opinions"]:
            if op["topic"].lower() == topic.lower():
                existing = op
                break
        
        if existing:
            # Update existing opinion
            existing["opinion"] = opinion
            existing["confidence"] = (existing["confidence"] + confidence) / 2  # Average
            existing["evidence"].append(evidence)
            existing["evidence"] = existing["evidence"][-5:]  # Keep last 5 pieces of evidence
            existing["updated"] = datetime.now().isoformat()
        else:
            # Add new opinion
            self.opinions["opinions"].append({
                "topic": topic,
                "opinion": opinion,
                "confidence": confidence,
                "evidence": [evidence],
                "category": category,
                "created": datetime.now().isoformat(),
                "updated": datetime.now().isoformat(),
            })
        
        self._save_opinions()
        logger.info(f"Recorded opinion on '{topic}': {opinion[:50]}...")
    
    def add_learned_pattern(
        self,
        pattern: str,
        occurrences: int = 1,
        category: str = "general",
    ):
        """
        Record a learned pattern.
        
        Args:
            pattern: The observed pattern
            occurrences: How many times observed
            category: Category (health, behavior, productivity, etc.)
        """
        # Check for existing pattern
        existing = None
        for p in self.opinions["learned_patterns"]:
            if p["pattern"].lower() == pattern.lower():
                existing = p
                break
        
        if existing:
            existing["occurrences"] += occurrences
            existing["last_seen"] = datetime.now().isoformat()
        else:
            self.opinions["learned_patterns"].append({
                "pattern": pattern,
                "occurrences": occurrences,
                "category": category,
                "first_seen": datetime.now().isoformat(),
                "last_seen": datetime.now().isoformat(),
            })
        
        self._save_opinions()
    
    def record_advice_outcome(
        self,
        advice: str,
        topic: str,
        outcome: str,  # "positive", "neutral", "negative"
        notes: str = "",
    ):
        """
        Record the outcome of advice Friday gave.
        
        This helps Friday learn what advice works.
        """
        self.opinions["advice_outcomes"].append({
            "advice": advice,
            "topic": topic,
            "outcome": outcome,
            "notes": notes,
            "timestamp": datetime.now().isoformat(),
        })
        
        # Keep last 50 outcomes
        self.opinions["advice_outcomes"] = self.opinions["advice_outcomes"][-50:]
        
        self._save_opinions()
        
        # If advice had positive outcome, strengthen related opinions
        if outcome == "positive":
            self.add_opinion(
                topic=topic,
                opinion=f"Advice about {topic} tends to help",
                confidence=0.6,
                evidence=f"Positive outcome: {advice[:100]}",
                category="advice",
            )
    
    def get_opinion(self, topic: str) -> Optional[Dict]:
        """Get Friday's opinion on a topic."""
        topic_lower = topic.lower()
        
        for op in self.opinions["opinions"]:
            if topic_lower in op["topic"].lower() or op["topic"].lower() in topic_lower:
                return op
        
        return None
    
    def get_relevant_opinions(self, message: str, limit: int = 3) -> List[Dict]:
        """Get opinions relevant to a message."""
        message_lower = message.lower()
        relevant = []
        
        for op in self.opinions["opinions"]:
            # Check if topic appears in message
            topic_words = op["topic"].lower().split()
            if any(word in message_lower for word in topic_words if len(word) > 3):
                relevant.append(op)
        
        # Sort by confidence
        relevant.sort(key=lambda x: x.get("confidence", 0), reverse=True)
        
        return relevant[:limit]
    
    def get_context_for_llm(self, message: str = "") -> str:
        """
        Get opinion context to include in LLM prompts.
        
        Returns Friday's relevant opinions for the conversation.
        """
        lines = []
        
        # Get relevant opinions if message provided
        if message:
            relevant = self.get_relevant_opinions(message, limit=2)
            if relevant:
                lines.append("## My Opinions")
                lines.append("(These are opinions I've formed based on our interactions - I should express them when relevant)")
                for op in relevant:
                    conf_str = "strongly believe" if op["confidence"] > 0.7 else "think"
                    lines.append(f"- On {op['topic']}: I {conf_str} that {op['opinion']}")
        
        # Get learned patterns (top 3 most observed)
        patterns = sorted(
            self.opinions.get("learned_patterns", []),
            key=lambda x: x.get("occurrences", 0),
            reverse=True
        )[:3]
        
        if patterns:
            lines.append("\n## Patterns I've Noticed")
            for p in patterns:
                if p["occurrences"] >= 3:  # Only mention patterns seen 3+ times
                    lines.append(f"- {p['pattern']} (noticed {p['occurrences']} times)")
        
        return "\n".join(lines) if lines else ""
    
    def get_stats(self) -> Dict[str, Any]:
        """Get opinion store statistics."""
        return {
            "total_opinions": len(self.opinions.get("opinions", [])),
            "learned_patterns": len(self.opinions.get("learned_patterns", [])),
            "advice_outcomes": len(self.opinions.get("advice_outcomes", [])),
            "positive_outcomes": len([
                a for a in self.opinions.get("advice_outcomes", [])
                if a.get("outcome") == "positive"
            ]),
        }


# Singleton instances
relationship_tracker = RelationshipTracker()
opinion_store = OpinionStore()
