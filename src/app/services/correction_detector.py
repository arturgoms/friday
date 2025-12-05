"""
Correction Detector for Friday AI.

Detects when a user is correcting Friday and extracts the correction details.
Uses LLM to understand the nuance of corrections.
"""
from typing import Optional, Dict, Any, Tuple
from dataclasses import dataclass

from app.services.llm import llm_service
from app.core.logging import logger


@dataclass
class CorrectionAnalysis:
    """Result of analyzing a potential correction."""
    is_correction: bool
    confidence: float  # 0.0 to 1.0
    what_was_wrong: Optional[str] = None
    correct_answer: Optional[str] = None
    topic: Optional[str] = None
    needs_clarification: bool = False
    clarification_question: Optional[str] = None


CORRECTION_DETECTION_PROMPT = """You are analyzing a conversation to detect if the user is correcting an AI assistant named Friday.

A correction is when:
- User says something is wrong/incorrect/mistaken
- User provides the correct information after Friday said something incorrect
- User expresses disagreement with a factual claim Friday made
- User says "actually", "no", "that's not right", "you're wrong", etc.

NOT a correction:
- User expressing a preference or opinion
- User adding new information (not contradicting)
- User asking a follow-up question
- User disagreeing with advice (subjective, not factual error)

Analyze this exchange:

FRIDAY SAID: {friday_response}

USER REPLIED: {user_message}

Respond with JSON:
{{
    "is_correction": true/false,
    "confidence": 0.0-1.0,
    "what_was_wrong": "what Friday said that was incorrect" or null,
    "correct_answer": "what the correct information is" or null,
    "topic": "the topic/subject of the correction" or null,
    "needs_clarification": true/false,
    "clarification_question": "question to ask user to understand the correction better" or null
}}

If the user seems to be correcting but it's not clear what exactly is wrong, set needs_clarification=true and provide a clarification_question.

Respond ONLY with valid JSON."""


class CorrectionDetector:
    """Detects and analyzes corrections from users."""
    
    # Keywords that often indicate corrections
    CORRECTION_KEYWORDS = [
        "wrong", "incorrect", "mistaken", "not right", "that's not",
        "actually", "no,", "nope", "you're wrong", "that's false",
        "not true", "isn't true", "wasn't", "aren't", "isn't",
        "i said", "i meant", "i didn't say", "i never said",
        "the correct", "it's actually", "it should be",
    ]
    
    # Keywords that suggest NOT a correction
    NON_CORRECTION_KEYWORDS = [
        "i think", "in my opinion", "i prefer", "i'd rather",
        "could you", "can you", "would you", "please",
        "thanks", "thank you", "great", "good", "nice",
    ]
    
    def quick_check(self, user_message: str) -> bool:
        """
        Quick heuristic check if message might be a correction.
        Used to decide if we should do full LLM analysis.
        """
        message_lower = user_message.lower()
        
        # Check for correction keywords
        has_correction_keyword = any(kw in message_lower for kw in self.CORRECTION_KEYWORDS)
        
        # Check for non-correction keywords (reduces false positives)
        has_non_correction_keyword = any(kw in message_lower for kw in self.NON_CORRECTION_KEYWORDS)
        
        # Short negative responses often indicate disagreement
        is_short_negative = len(user_message.split()) <= 5 and any(
            word in message_lower for word in ["no", "wrong", "nope", "false", "incorrect"]
        )
        
        return (has_correction_keyword or is_short_negative) and not has_non_correction_keyword
    
    def analyze(
        self,
        friday_response: str,
        user_message: str,
    ) -> CorrectionAnalysis:
        """
        Analyze if the user message is correcting Friday.
        
        Args:
            friday_response: What Friday said
            user_message: User's reply
            
        Returns:
            CorrectionAnalysis with details
        """
        # First do quick check
        if not self.quick_check(user_message):
            return CorrectionAnalysis(is_correction=False, confidence=0.9)
        
        # Use LLM for detailed analysis
        try:
            prompt = CORRECTION_DETECTION_PROMPT.format(
                friday_response=friday_response[:500],  # Limit length
                user_message=user_message[:500],
            )
            
            response = llm_service.call(
                system_prompt="You are a correction detection assistant. Respond only with valid JSON.",
                user_content=prompt,
                history=[],
                stream=False,
            )
            
            # Parse response
            import json
            
            response = response.strip()
            if response.startswith("```json"):
                response = response[7:]
            if response.startswith("```"):
                response = response[3:]
            if response.endswith("```"):
                response = response[:-3]
            
            data = json.loads(response.strip())
            
            return CorrectionAnalysis(
                is_correction=data.get("is_correction", False),
                confidence=data.get("confidence", 0.5),
                what_was_wrong=data.get("what_was_wrong"),
                correct_answer=data.get("correct_answer"),
                topic=data.get("topic"),
                needs_clarification=data.get("needs_clarification", False),
                clarification_question=data.get("clarification_question"),
            )
            
        except Exception as e:
            logger.error(f"Error analyzing correction: {e}")
            # Fall back to heuristic
            return CorrectionAnalysis(
                is_correction=self.quick_check(user_message),
                confidence=0.5,
            )
    
    def generate_acknowledgment(
        self,
        analysis: CorrectionAnalysis,
    ) -> str:
        """
        Generate an appropriate acknowledgment for a correction.
        
        Returns a message Friday should include in response.
        """
        if analysis.needs_clarification:
            return analysis.clarification_question or "I want to make sure I understand - what exactly did I get wrong?"
        
        if analysis.what_was_wrong and analysis.correct_answer:
            return (
                f"You're right, I was wrong about that. "
                f"I said {analysis.what_was_wrong}, but the correct answer is {analysis.correct_answer}. "
                f"I'll remember this."
            )
        elif analysis.what_was_wrong:
            return f"I apologize for the error about {analysis.what_was_wrong}. Thank you for correcting me."
        else:
            return "Thank you for the correction. I'll update my understanding."


# Singleton
correction_detector = CorrectionDetector()
