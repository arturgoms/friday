"""General intent handler - RAG, memory, greetings, and general conversation."""
import asyncio
import threading
from datetime import datetime
from typing import List, Optional, Tuple

from app.core.config import settings
from app.core.logging import logger
from app.services.chat.handlers.base import IntentHandler, ChatContext, ChatResponse
from app.services.llm import llm_service
from app.services.vector_store import vector_store
from app.services.conversation_memory import conversation_memory
from app.services.correction_detector import correction_detector
from app.services.obsidian_knowledge import obsidian_knowledge
from app.services.relationship_state import relationship_tracker, opinion_store
from app.services.post_chat_processor import post_chat_processor


class GeneralHandler(IntentHandler):
    """Handle general intent - RAG, memory, greetings, and general conversation.
    
    This is the most complex handler as it handles:
    - Greetings and small talk
    - Questions about Obsidian notes (RAG)
    - Questions about personal info (memory)
    - General conversation with personality
    - Correction detection and learning
    - Post-chat memory extraction
    """
    
    actions = ['general']
    
    def handle(self, context: ChatContext) -> ChatResponse:
        """Handle general queries with RAG, memory, and personality."""
        try:
            # Extract intent flags
            use_rag = context.intent.get('use_rag', False)
            use_memory = context.intent.get('use_memory', False)
            
            # Fetch context based on intent
            rag_context, obsidian_chunks, memory_items = self._fetch_context(
                context.message, use_rag, use_memory
            )
            
            # Generate system prompt with all personality and context
            system_prompt = self._generate_system_prompt(context.message)
            
            # Build user content
            if rag_context:
                user_content = f"User question:\n{context.message}\n\nContext:\n{rag_context}"
            else:
                user_content = context.message
            
            # Call LLM to generate response
            answer = llm_service.call(
                system_prompt=system_prompt,
                user_content=user_content,
                history=context.history,
                stream=False,
            )
            
            # Background: Check for corrections and track interaction
            self._background_processing(context, answer)
            
            return ChatResponse(
                session_id=context.session_id,
                message=context.message,
                answer=answer,
                used_rag=len(obsidian_chunks) > 0,
                used_memory=len(memory_items) > 0,
                obsidian_chunks=obsidian_chunks,
                memory_items=memory_items,
                is_final=True,
            )
            
        except Exception as e:
            logger.error(f"General handler error: {e}", exc_info=True)
            return self._error_response(context, f"Something went wrong: {str(e)}")
    
    def _fetch_context(
        self, 
        message: str, 
        use_rag: bool, 
        use_memory: bool
    ) -> Tuple[str, List, List]:
        """Fetch RAG and memory context based on intent flags.
        
        Returns:
            Tuple of (context_string, obsidian_chunks, memory_items)
        """
        context_parts = []
        obsidian_chunks = []
        memory_items = []
        
        # Check for identity queries - these need special handling
        message_lower = message.lower()
        is_user_identity_query = any(phrase in message_lower for phrase in [
            'who am i', 'tell me about myself', 'what do you know about me',
            'my profile', 'my information', 'about me'
        ])
        
        # RAG/Obsidian notes
        if use_rag:
            if is_user_identity_query:
                # For "Who am I?" queries, always load the user's profile file first
                user_profile_ctx = self._load_user_profile()
                if user_profile_ctx:
                    context_parts.append("### Your profile (from Artur Gomes.md)\n" + user_profile_ctx)
                # Also do regular RAG but with better query
                obsidian_ctx, obsidian_chunks = vector_store.query_obsidian("Artur Gomes personal information")
                if obsidian_ctx:
                    context_parts.append("### Additional notes\n" + obsidian_ctx)
            else:
                obsidian_ctx, obsidian_chunks = vector_store.query_obsidian(message)
                if obsidian_ctx:
                    context_parts.append("### From your notes\n" + obsidian_ctx)
        
        # Memory - search BOTH markdown memories AND user profile
        if use_memory:
            from app.services.memory_store import MemoryStore
            memory_store = MemoryStore()
            
            # 1. Always load user profile for personal queries (authoritative source)
            if not use_rag:  # Don't load twice if already loaded via RAG
                user_profile_ctx = self._load_user_profile()
                if user_profile_ctx:
                    context_parts.append("### From your profile (Artur Gomes.md)\n" + user_profile_ctx)
                    memory_items.append({"id": "profile", "content": "User profile loaded"})
            
            # 2. Also search memories for recently learned facts
            markdown_memories = memory_store.search_memories(message, limit=5)
            
            if markdown_memories:
                memory_parts = []
                for mem in markdown_memories:
                    content = mem.get('full_content', '')
                    if content:
                        # Clean up: remove the header and context sections
                        lines = content.split('\n')
                        clean_lines = []
                        for line in lines:
                            if line.strip().startswith('## Context'):
                                break
                            if line.strip() and not line.startswith('#'):
                                clean_lines.append(line.strip())
                        clean_content = ' '.join(clean_lines)
                        if clean_content:
                            memory_parts.append(f"[Memory] {clean_content}")
                            memory_items.append(mem)
                
                if memory_parts:
                    context_parts.append("### From your memories\n" + "\n\n".join(memory_parts))
        
        # Conversation memory - add context from past conversations on this topic
        conv_memory_ctx = conversation_memory.get_context_for_message(message)
        if conv_memory_ctx:
            context_parts.append(conv_memory_ctx)
        
        combined_context = "\n\n".join(context_parts) if context_parts else ""
        return combined_context, obsidian_chunks, memory_items
    
    def _load_user_profile(self) -> str:
        """Load the user's profile file (Artur Gomes.md) for identity queries."""
        try:
            profile_path = settings.vault_path / settings.user_profile_file
            if profile_path.exists():
                content = profile_path.read_text(encoding="utf-8")
                logger.info(f"Loaded user profile from {profile_path}")
                return content
            else:
                logger.warning(f"User profile not found: {profile_path}")
                return ""
        except Exception as e:
            logger.error(f"Failed to load user profile: {e}")
            return ""
    
    def _generate_system_prompt(self, message: str) -> str:
        """Generate system prompt with personality, corrections, and context."""
        user_tz = settings.user_timezone
        now = datetime.now(user_tz)
        today = now.strftime("%A, %B %d, %Y")
        current_time = now.strftime("%I:%M %p")
        
        # Load personality from file
        personality = self._load_personality()
        
        # Build base prompt
        base = f"Today is {today}, {current_time}.\n\n"
        
        if personality:
            base += f"{personality}\n\n"
        else:
            base += "You are Friday, a personal AI assistant for Artur Gomes.\n\n"
        
        # Always add critical context
        base += (
            f"CRITICAL: The user speaking to you is Artur Gomes ({settings.authorized_user}). "
            f"All notes in the vault were written by Artur - they are HIS ideas, projects, and knowledge. "
            f"Do NOT confuse Artur with other people mentioned in his notes."
        )
        
        # Add corrections awareness
        corrections_context = conversation_memory.get_all_corrections_context()
        corrections_note = ""
        if corrections_context:
            corrections_note = f"\n\n{corrections_context}\n"
        
        # Add Obsidian knowledge for note-related queries
        obsidian_context = obsidian_knowledge.get_context_for_llm()
        
        # Add relationship context for tone/behavior adjustment
        relationship_context = relationship_tracker.get_context_for_llm()
        
        # Add opinions context - Friday's learned views and patterns
        opinions_context = opinion_store.get_context_for_llm(message)
        
        # Add learnings from feedback system
        learnings_context = self._get_learnings_context()
        
        return (
            f"{base}\n\n"
            f"{corrections_note}"
            f"{relationship_context}\n\n"
            f"{opinions_context}\n\n"
            f"{learnings_context}\n\n"
            f"{obsidian_context}\n\n"
            "Rules:\n"
            "- For GREETINGS and SMALL TALK (hey, what's up, how are you): respond naturally and briefly like a friend would. Don't dump information or context.\n"
            "- Use provided context (notes/memory) ONLY if the user is actually asking about something in their notes\n"
            "- If you've been corrected on a topic before, use the CORRECT information\n"
            "- Express your opinions when relevant - you have views based on our interactions\n"
            "- Push back if you think something is a bad idea - be honest\n"
            "- When creating or suggesting notes, follow the Obsidian note system above\n"
            "- Adjust your tone based on relationship context and user's apparent mood\n"
            "- Be concise and conversational, not robotic or overly structured\n"
            "- Use Markdown formatting only when helpful: *bold*, `code`, bullets"
        )
    
    def _load_personality(self) -> str:
        """Load Friday's personality from 5.0 About/Who is Friday.md"""
        try:
            personality_path = settings.about_path / "Who is Friday.md"
            if personality_path.exists():
                content = personality_path.read_text(encoding="utf-8")
                # Remove frontmatter (between --- markers)
                if content.startswith("---"):
                    end_frontmatter = content.find("---", 3)
                    if end_frontmatter != -1:
                        content = content[end_frontmatter + 3:].strip()
                logger.debug(f"Loaded Friday personality from {personality_path}")
                return content
            else:
                logger.warning(f"Personality file not found: {personality_path}")
                return ""
        except Exception as e:
            logger.error(f"Failed to load personality: {e}")
            return ""
    
    def _get_learnings_context(self) -> str:
        """Get learned preferences from the feedback system.
        
        Returns prompt adjustments based on user feedback patterns.
        """
        try:
            from app.services.learning_service import get_learning_service
            learning_service = get_learning_service()
            return learning_service.get_prompt_adjustments(min_confidence=0.7)
        except Exception as e:
            logger.debug(f"Could not load learnings: {e}")
            return ""
    
    def _background_processing(self, context: ChatContext, answer: str) -> None:
        """Run background processing for corrections and relationship tracking.
        
        This runs in background threads to not block the response.
        """
        # Check for corrections
        if context.history and len(context.history) >= 2:
            last_friday_response = None
            for msg in reversed(context.history):
                if msg.get('role') == 'assistant':
                    last_friday_response = msg.get('content', '')
                    break
            
            if last_friday_response:
                # Quick check first (cheap), then LLM analysis if needed
                if correction_detector.quick_check(context.message):
                    def check_correction_async():
                        try:
                            analysis = correction_detector.analyze(last_friday_response, context.message)
                            if analysis.is_correction and analysis.confidence > 0.7:
                                if not analysis.needs_clarification:
                                    # Record the correction
                                    conversation_memory.add_correction(
                                        topic=analysis.topic or "general",
                                        user_message=context.message,
                                        friday_response=last_friday_response[:500],
                                        what_was_wrong=analysis.what_was_wrong or "Unknown",
                                        correct_answer=analysis.correct_answer or context.message,
                                        lesson_learned=f"Remember: {analysis.correct_answer}" if analysis.correct_answer else None,
                                    )
                                    logger.info(f"Recorded correction: {analysis.topic}")
                        except Exception as e:
                            logger.error(f"Error in correction detection: {e}")
                    
                    thread = threading.Thread(target=check_correction_async, daemon=True)
                    thread.start()
        
        # Track interaction for relationship state
        try:
            mood = relationship_tracker.detect_mood(context.message)
            sentiment = "neutral"
            if mood.value in ["happy", "energetic"]:
                sentiment = "positive"
            elif mood.value in ["frustrated", "sad", "stressed"]:
                sentiment = "negative"
            
            relationship_tracker.record_interaction(
                message=context.message,
                sentiment=sentiment,
                topic_category="general",
                user_initiated=True,
            )
        except Exception as e:
            logger.error(f"Error tracking interaction: {e}")
        
        # Post-chat processing: Extract memories and tasks in background
        def run_async_processor():
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(
                    post_chat_processor.process_conversation(context.message, answer, context.history)
                )
                loop.close()
            except Exception as e:
                logger.error(f"Post-chat processing error: {e}", exc_info=True)
        
        thread = threading.Thread(target=run_async_processor, daemon=True)
        thread.start()
        logger.debug("Started post-chat processing thread (memory & task extraction)")
