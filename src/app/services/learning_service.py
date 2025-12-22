"""
Learning Service - Synthesize user feedback into behavioral adjustments.

Part of the Feedback & Learning System. This service:
1. Analyzes corrections from negative feedback
2. Identifies patterns in what users want
3. Generates "learnings" that adjust Friday's behavior
4. Stores learnings for injection into system prompts
"""
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field, asdict

from app.core.config import settings
from app.core.logging import logger


@dataclass
class Learning:
    """A single learned behavior adjustment."""
    id: str
    created_at: str
    pattern: str  # What we learned (human readable)
    prompt_adjustment: str  # How to adjust behavior
    confidence: float  # 0.0 to 1.0
    source_corrections: List[int] = field(default_factory=list)  # Correction IDs
    category: str = "general"  # Category: general, tone, format, content, etc.
    active: bool = True  # Whether this learning is currently applied
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Learning":
        return cls(**data)


class LearningService:
    """Service for synthesizing and managing learned behaviors."""
    
    def __init__(self, learnings_path: Optional[Path] = None):
        """Initialize learning service."""
        if learnings_path is None:
            learnings_path = Path(settings.friday_path) / "data" / "learnings.json"
        
        self.learnings_path = learnings_path
        self.learnings_path.parent.mkdir(parents=True, exist_ok=True)
        
        self._learnings: List[Learning] = []
        self._enabled: bool = True
        self._load_learnings()
    
    def _load_learnings(self) -> None:
        """Load learnings from disk."""
        if self.learnings_path.exists():
            try:
                with open(self.learnings_path, 'r') as f:
                    data = json.load(f)
                    self._learnings = [Learning.from_dict(l) for l in data.get("learnings", [])]
                    self._enabled = data.get("enabled", True)
                logger.info(f"Loaded {len(self._learnings)} learnings")
            except Exception as e:
                logger.error(f"Error loading learnings: {e}")
                self._learnings = []
    
    def _save_learnings(self) -> None:
        """Save learnings to disk."""
        try:
            data = {
                "enabled": self._enabled,
                "learnings": [l.to_dict() for l in self._learnings],
                "last_updated": datetime.now().isoformat()
            }
            with open(self.learnings_path, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving learnings: {e}")
    
    def _generate_learning_id(self) -> str:
        """Generate a unique learning ID."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        count = len(self._learnings) + 1
        return f"learn_{timestamp}_{count:03d}"
    
    async def synthesize_learnings(self) -> List[Learning]:
        """
        Analyze unprocessed corrections and generate new learnings.
        
        Uses LLM to identify patterns and generate prompt adjustments.
        Returns list of newly generated learnings.
        """
        from app.services.feedback_store import get_feedback_store
        from app.services.llm import llm_service
        
        feedback_store = get_feedback_store()
        corrections = feedback_store.get_unprocessed_corrections(limit=50)
        
        if not corrections:
            logger.info("No unprocessed corrections to synthesize")
            return []
        
        # Format corrections for LLM analysis
        corrections_text = "\n\n".join([
            f"### Correction {i+1}\n"
            f"**User asked:** {c['user_message'][:200]}\n"
            f"**Friday said:** {c['ai_response'][:300]}...\n"
            f"**User correction:** {c['correction_text']}\n"
            f"**Intent:** {c.get('intent_action', 'unknown')}"
            for i, c in enumerate(corrections)
        ])
        
        # Use LLM to identify patterns
        prompt = f"""Analyze these user corrections to Friday AI and identify patterns in what users want.

{corrections_text}

Based on these corrections, identify 1-3 clear patterns and generate learnings.
For each learning, provide:
1. A brief pattern description (what users consistently want)
2. A specific prompt adjustment (instruction to add to system prompt)
3. A confidence score (0.0-1.0) based on how consistent the pattern is
4. A category (tone, format, content, accuracy, or general)

Respond in this exact JSON format:
```json
{{
  "learnings": [
    {{
      "pattern": "Brief description of what users want",
      "prompt_adjustment": "Specific instruction for the system prompt",
      "confidence": 0.85,
      "category": "general"
    }}
  ]
}}
```

Only include learnings with confidence >= 0.6. If no clear patterns emerge, return an empty learnings array."""

        try:
            response = llm_service.call(
                system_prompt="You are analyzing user feedback to improve an AI assistant. Be precise and actionable.",
                user_content=prompt
            )
            
            # Parse JSON from response
            import re
            json_match = re.search(r'```json\s*(.*?)\s*```', response, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group(1))
            else:
                # Try parsing the whole response as JSON
                result = json.loads(response)
            
            new_learnings = []
            correction_ids = [c["correction_id"] for c in corrections]
            
            for learning_data in result.get("learnings", []):
                if learning_data.get("confidence", 0) < 0.6:
                    continue
                
                learning = Learning(
                    id=self._generate_learning_id(),
                    created_at=datetime.now().isoformat(),
                    pattern=learning_data["pattern"],
                    prompt_adjustment=learning_data["prompt_adjustment"],
                    confidence=learning_data["confidence"],
                    category=learning_data.get("category", "general"),
                    source_corrections=correction_ids
                )
                
                new_learnings.append(learning)
                self._learnings.append(learning)
            
            if new_learnings:
                self._save_learnings()
                
                # Mark corrections as processed
                for learning in new_learnings:
                    feedback_store.mark_corrections_processed(
                        correction_ids, 
                        learning_id=learning.id
                    )
                
                logger.info(f"Synthesized {len(new_learnings)} new learnings from {len(corrections)} corrections")
            
            return new_learnings
            
        except Exception as e:
            logger.error(f"Error synthesizing learnings: {e}", exc_info=True)
            return []
    
    def get_active_learnings(self, min_confidence: float = 0.7) -> List[Learning]:
        """Get learnings that should be applied to prompts."""
        if not self._enabled:
            return []
        
        return [
            l for l in self._learnings 
            if l.active and l.confidence >= min_confidence
        ]
    
    def get_prompt_adjustments(self, min_confidence: float = 0.7) -> str:
        """
        Get formatted prompt adjustments for injection into system prompts.
        
        Returns a formatted string ready to append to system prompts.
        """
        active = self.get_active_learnings(min_confidence)
        
        if not active:
            return ""
        
        adjustments = [f"- {l.prompt_adjustment}" for l in active]
        
        return "\n\n**User Preferences (Learned from feedback):**\n" + "\n".join(adjustments)
    
    def add_manual_learning(self, pattern: str, prompt_adjustment: str, confidence: float = 1.0, category: str = "manual") -> Learning:
        """
        Add a learning manually (from user command).
        
        Manual learnings have high confidence since they're explicit user preferences.
        """
        learning = Learning(
            id=self._generate_learning_id(),
            created_at=datetime.now().isoformat(),
            pattern=pattern,
            prompt_adjustment=prompt_adjustment,
            confidence=confidence,
            category=category,
            source_corrections=[]  # No corrections, manually added
        )
        
        self._learnings.append(learning)
        self._save_learnings()
        
        logger.info(f"Added manual learning: {learning.id}")
        return learning
    
    def remove_learning(self, learning_id: str) -> bool:
        """Remove a learning by ID."""
        for i, learning in enumerate(self._learnings):
            if learning.id == learning_id:
                del self._learnings[i]
                self._save_learnings()
                logger.info(f"Removed learning: {learning_id}")
                return True
        return False
    
    def toggle_learning(self, learning_id: str, active: bool) -> bool:
        """Enable or disable a specific learning."""
        for learning in self._learnings:
            if learning.id == learning_id:
                learning.active = active
                self._save_learnings()
                return True
        return False
    
    def enable_all(self) -> None:
        """Enable the learning system."""
        self._enabled = True
        self._save_learnings()
        logger.info("Learning system enabled")
    
    def disable_all(self) -> None:
        """Disable the learning system (learnings won't be applied)."""
        self._enabled = False
        self._save_learnings()
        logger.info("Learning system disabled")
    
    def is_enabled(self) -> bool:
        """Check if learning system is enabled."""
        return self._enabled
    
    def get_all_learnings(self) -> List[Learning]:
        """Get all learnings."""
        return self._learnings.copy()
    
    def get_learning(self, learning_id: str) -> Optional[Learning]:
        """Get a specific learning by ID."""
        for learning in self._learnings:
            if learning.id == learning_id:
                return learning
        return None
    
    def get_stats(self) -> Dict[str, Any]:
        """Get learning system statistics."""
        active = [l for l in self._learnings if l.active]
        by_category = {}
        for l in self._learnings:
            by_category[l.category] = by_category.get(l.category, 0) + 1
        
        return {
            "enabled": self._enabled,
            "total_learnings": len(self._learnings),
            "active_learnings": len(active),
            "by_category": by_category,
            "avg_confidence": sum(l.confidence for l in self._learnings) / len(self._learnings) if self._learnings else 0
        }


# Singleton instance
_learning_service: Optional[LearningService] = None

def get_learning_service() -> LearningService:
    """Get learning service singleton."""
    global _learning_service
    if _learning_service is None:
        _learning_service = LearningService()
    return _learning_service
