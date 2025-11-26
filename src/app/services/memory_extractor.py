"""Automatic memory extraction from conversations."""
import re
from datetime import datetime
from typing import List, Dict, Any, Optional
from app.core.logging import logger
from app.core.config import settings


class MemoryExtraction:
    """Extracted memory from conversation."""
    
    def __init__(
        self,
        content: str,
        memory_type: str,  # fact, preference, person, project, event
        entities: List[str],
        confidence: float,
        metadata: Optional[Dict[str, Any]] = None
    ):
        self.content = content
        self.memory_type = memory_type
        self.entities = entities  # People, projects, topics mentioned
        self.confidence = confidence
        self.metadata = metadata or {}
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "content": self.content,
            "type": self.memory_type,
            "entities": self.entities,
            "confidence": self.confidence,
            "metadata": self.metadata
        }


class MemoryExtractor:
    """Extracts memorable information from conversations."""
    
    def __init__(self):
        self._llm_service = None
    
    @property
    def llm_service(self):
        """Lazy load LLM service."""
        if self._llm_service is None:
            from app.services.llm import llm_service
            self._llm_service = llm_service
        return self._llm_service
    
    async def extract_from_conversation(
        self,
        user_message: str,
        assistant_response: str,
        conversation_history: Optional[List[Dict]] = None
    ) -> List[MemoryExtraction]:
        """
        Extract memorable information from a conversation turn.
        
        Args:
            user_message: What the user said
            assistant_response: How Friday responded
            conversation_history: Recent conversation context
            
        Returns:
            List of memory extractions
        """
        # Build context
        context = ""
        if conversation_history:
            recent = conversation_history[-4:]  # Last 2 turns
            for msg in recent:
                role = msg.get("role", "user")
                content = msg.get("content", "")
                context += f"{role.upper()}: {content}\n"
        
        context += f"USER: {user_message}\nASSISTANT: {assistant_response}"
        
        # Extraction prompt
        extraction_prompt = f"""Analyze this conversation and extract memorable information.

CONVERSATION:
{context}

Extract the following types of information:

1. FACTS: New factual information about the user or their world
   Example: "I work at Counterpart", "My birthday is March 30"

2. PREFERENCES: Likes, dislikes, habits, routines
   Example: "I prefer running in the morning", "I love pizza"

3. PEOPLE: Names and relationships
   Example: "Maria (colleague)", "Camila (wife)", "Julian (friend from work)"

4. PROJECTS: Work or personal projects being undertaken
   Example: "Working on authentication system", "Learning Rust"

5. EVENTS: Important events or milestones mentioned
   Example: "Meeting tomorrow at 10 AM", "Started new job"

For each extraction, provide:
- Type: fact/preference/person/project/event
- Content: The actual information (concise, 1-2 sentences max)
- Entities: People/projects/topics mentioned (comma-separated)
- Confidence: 0.0-1.0 (how certain this is worth remembering)

Format as JSON array:
[
  {{
    "type": "person",
    "content": "Maria is a colleague working on the authentication system",
    "entities": ["Maria", "authentication system"],
    "confidence": 0.9
  }},
  ...
]

IMPORTANT:
- Only extract NEW information not already obviously known
- Skip casual conversation that isn't memorable
- Confidence < 0.5 means probably not worth saving
- If nothing memorable, return empty array []

JSON OUTPUT:"""

        try:
            # Call LLM for extraction
            response = self.llm_service.call(
                system_prompt="You are a memory extraction assistant. Extract memorable information from conversations and format as JSON.",
                user_content=extraction_prompt,
                history=[],
                stream=False
            )
            
            # Parse JSON response
            import json
            
            # Extract JSON from response (handle markdown code blocks)
            json_match = re.search(r'```(?:json)?\s*(\[.*?\])\s*```', response, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
            else:
                # Try to find JSON array directly
                json_match = re.search(r'(\[.*?\])', response, re.DOTALL)
                if json_match:
                    json_str = json_match.group(1)
                else:
                    logger.warning(f"Could not find JSON in extraction response: {response[:200]}")
                    return []
            
            extractions_data = json.loads(json_str)
            
            # Convert to MemoryExtraction objects
            extractions = []
            for data in extractions_data:
                if data.get("confidence", 0) >= 0.5:  # Only keep confident extractions
                    extraction = MemoryExtraction(
                        content=data["content"],
                        memory_type=data["type"],
                        entities=data.get("entities", []),
                        confidence=data["confidence"],
                        metadata={"extracted_at": datetime.now().isoformat()}
                    )
                    extractions.append(extraction)
            
            logger.info(f"Extracted {len(extractions)} memories from conversation")
            return extractions
            
        except Exception as e:
            logger.error(f"Error extracting memories: {e}")
            return []
    
    def should_save_extraction(self, extraction: MemoryExtraction) -> bool:
        """Determine if an extraction should be saved as a memory."""
        # High confidence threshold
        if extraction.confidence < 0.7:
            return False
        
        # Don't save very short or generic content
        if len(extraction.content) < 10:
            return False
        
        # Don't save if it looks like a question or command
        if extraction.content.strip().endswith('?'):
            return False
        
        return True
    
    def format_as_obsidian_note(self, extraction: MemoryExtraction) -> Dict[str, Any]:
        """
        Format extraction as an Obsidian note.
        
        Returns:
            Dict with 'content', 'title', 'tags' for note creation
        """
        user_tz = settings.user_timezone
        now = datetime.now(user_tz)
        
        # Generate title based on type and content
        if extraction.memory_type == "person":
            # Extract name
            entities = extraction.entities
            if entities:
                title = entities[0]
            else:
                title = f"Person - {now.strftime('%Y-%m-%d')}"
        elif extraction.memory_type == "project":
            entities = extraction.entities
            if entities:
                title = entities[0]
            else:
                title = f"Project - {now.strftime('%Y-%m-%d')}"
        else:
            # Generate title from content (first few words)
            words = extraction.content.split()[:5]
            title = ' '.join(words)
            if len(extraction.content.split()) > 5:
                title += "..."
        
        # Build note content
        note_content = f"""---
type: {extraction.memory_type}
entities: {', '.join(extraction.entities)}
confidence: {extraction.confidence}
extracted_at: {extraction.metadata.get('extracted_at', now.isoformat())}
tags:
  - memory/auto-extracted
  - memory/{extraction.memory_type}
---

# {title}

{extraction.content}

## Context
Automatically extracted from conversation on {now.strftime('%Y-%m-%d %H:%M')}.

## Related
{self._generate_links(extraction.entities)}
"""
        
        # Determine tags
        tags = [
            "memory",
            "auto-extracted",
            extraction.memory_type
        ]
        
        return {
            "content": note_content,
            "title": title,
            "tags": tags
        }
    
    def _generate_links(self, entities: List[str]) -> str:
        """Generate Obsidian links for entities."""
        if not entities:
            return "_No specific entities._"
        
        links = []
        for entity in entities:
            # Create wiki-style link
            links.append(f"- [[{entity}]]")
        
        return '\n'.join(links)


# Singleton instance
memory_extractor = MemoryExtractor()
