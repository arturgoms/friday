"""Note intent handlers - create, update, search, get Obsidian notes."""
from datetime import datetime
from typing import Optional

from app.core.logging import logger
from app.services.chat.handlers.base import IntentHandler, ChatContext, ChatResponse
from app.services.obsidian import obsidian_service


class NoteCreateHandler(IntentHandler):
    """Handle note_create intent - create new Obsidian notes."""
    
    actions = ['note_create']
    
    def handle(self, context: ChatContext) -> ChatResponse:
        """Create a new note in Obsidian vault."""
        note_data = context.note_data
        
        if not note_data:
            return self._error_response(context, "No note data provided")
        
        try:
            title = note_data.get('title', 'Untitled')
            content = note_data.get('content', '')
            folder = note_data.get('folder')
            tags = note_data.get('tags', [])
            
            filepath = obsidian_service.create_note(
                title=title,
                content=content,
                folder=folder,
                tags=tags
            )
            
            # Escape underscores for Telegram markdown
            safe_title = title.replace('_', '\\_')
            answer = f"Created note: {safe_title}"
            
            return ChatResponse(
                session_id=context.session_id,
                message=context.message,
                answer=answer,
                is_final=True,
            )
            
        except Exception as e:
            logger.error(f"Note creation error: {e}", exc_info=True)
            return self._error_response(context, f"Failed to create note: {str(e)}")


class NoteUpdateHandler(IntentHandler):
    """Handle note_update intent - update/append to existing notes."""
    
    actions = ['note_update']
    
    def handle(self, context: ChatContext) -> ChatResponse:
        """Update an existing note in Obsidian vault."""
        note_data = context.note_data
        
        if not note_data:
            return self._error_response(context, "No note data provided")
        
        try:
            title = note_data.get('title', '')
            content = note_data.get('content', '')
            append = note_data.get('append', True)
            add_date_header = note_data.get('add_date_header', False)
            
            if not title:
                return self._error_response(context, "Please specify which note to update")
            
            # Add date header if requested
            if add_date_header:
                today_str = datetime.now().strftime("%d/%m/%y")
                content = f"### {today_str}\n\n{content}"
            
            filepath = obsidian_service.update_note(
                title=title,
                new_content=content,
                append=append
            )
            
            if filepath:
                action_word = "Added to" if append else "Updated"
                safe_title = title.replace('_', '\\_')
                answer = f"{action_word} note: {safe_title}"
            else:
                answer = f"Note not found: '{title}'"
            
            return ChatResponse(
                session_id=context.session_id,
                message=context.message,
                answer=answer,
                is_final=True,
            )
            
        except Exception as e:
            logger.error(f"Note update error: {e}", exc_info=True)
            return self._error_response(context, f"Failed to update note: {str(e)}")


class NoteSearchHandler(IntentHandler):
    """Handle note_search intent - search/list notes."""
    
    actions = ['note_search']
    
    def handle(self, context: ChatContext) -> ChatResponse:
        """Search or list notes in Obsidian vault."""
        note_data = context.note_data
        
        try:
            query = note_data.get('title', '') if note_data else ''
            
            if query:
                # Search by query
                results = obsidian_service.search_notes(query, limit=10)
                if results:
                    safe_query = query.replace('_', '\\_')
                    answer = f"Found {len(results)} note(s) matching '{safe_query}':\n\n"
                    for i, note in enumerate(results, 1):
                        safe_title = note['title'].replace('_', '\\_')
                        answer += f"{i}. {safe_title}\n"
                        if note.get('preview'):
                            safe_preview = note['preview'][:100].replace('_', '\\_')
                            answer += f"   {safe_preview}...\n"
                else:
                    answer = f"No notes found matching '{query}'"
            else:
                # List recent notes
                results = obsidian_service.list_notes(limit=10)
                if results:
                    answer = "Recent notes:\n\n"
                    for i, note in enumerate(results, 1):
                        safe_title = note['title'].replace('_', '\\_')
                        answer += f"{i}. {safe_title}\n"
                else:
                    answer = "No notes found in your vault"
            
            return ChatResponse(
                session_id=context.session_id,
                message=context.message,
                answer=answer,
                is_final=True,
            )
            
        except Exception as e:
            logger.error(f"Note search error: {e}", exc_info=True)
            return self._error_response(context, f"Failed to search notes: {str(e)}")


class NoteGetHandler(IntentHandler):
    """Handle note_get intent - retrieve full note content."""
    
    actions = ['note_get']
    
    def handle(self, context: ChatContext) -> ChatResponse:
        """Get the full content of a note."""
        note_data = context.note_data
        
        try:
            title = note_data.get('title', '') if note_data else ''
            
            if not title:
                return self._error_response(context, "Please specify which note you want to see")
            
            result = obsidian_service.get_note(title)
            
            if result:
                content = result['content']
                # Strip frontmatter for cleaner display
                if "---" in content:
                    parts = content.split("---", 2)
                    if len(parts) >= 3:
                        content = parts[2].strip()
                
                # Escape underscores for Telegram markdown
                safe_title = result['title'].replace('_', '\\_')
                safe_content = content.replace('_', '\\_')
                answer = f"{safe_title}\n\n{safe_content}"
            else:
                answer = f"Note not found: '{title}'"
            
            return ChatResponse(
                session_id=context.session_id,
                message=context.message,
                answer=answer,
                is_final=True,
            )
            
        except Exception as e:
            logger.error(f"Note get error: {e}", exc_info=True)
            return self._error_response(context, f"Failed to get note: {str(e)}")
